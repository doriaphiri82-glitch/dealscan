"""DealScan - Per-county run runner.

Configured scrapers and dynamically discovered national ArcGIS sources both
flow through the same ETL -> persistence -> scoring -> publishing pipeline.
"""
from __future__ import annotations
import traceback
from typing import Any, Dict, List, Optional
from config.counties.national_registry import PILOT_COUNTIES
from config.counties.registry import get_county, mark_county_run
from database import get_top_deals, save_deal, save_property
from runregistry import record_run, write_bundle
from scoring.deal_scorer import score_and_enrich_deal
from scrapers import arcgis
from scrapers.adapter import BaseScraperAdapter
from scrapers.arcgis_adapter import ArcGISFeatureServerAdapter, ArcGISHubAdapter
from scrapers.counties import COUNTY_SCRAPERS
from scrapers.flatfile_adapter import FlatFileAdapter, CSVAdapter, ExcelAdapter

ADAPTER_MAP={"arcgis":ArcGISFeatureServerAdapter,"arcgis_hub":ArcGISHubAdapter,"flatfile":FlatFileAdapter,"csv":CSVAdapter,"excel":ExcelAdapter,"state_parcel":ArcGISFeatureServerAdapter}

def _adapter_for(cfg: Dict[str,Any])->Optional[BaseScraperAdapter]:
    scraper_type=cfg.get("scraper_type"); data_mode=cfg.get("data_mode","arcgis")
    if scraper_type:
        cls=ADAPTER_MAP.get(scraper_type)
        if cls is None:return None
        if scraper_type in ("arcgis","arcgis_hub","state_parcel") and not cfg.get("arcgis_layer_url"):return None
        return cls()
    if data_mode in ("flatfile","csv","excel"):return ADAPTER_MAP.get(data_mode,FlatFileAdapter)()
    if data_mode in ("arcgis","arcgis_hub","state_parcel") and cfg.get("arcgis_layer_url"):return ADAPTER_MAP.get(data_mode,ArcGISFeatureServerAdapter)()
    return None

def _county_config(county_id:str)->Dict[str,Any]:
    cfg=dict(COUNTY_SCRAPERS.get(county_id) or {})
    if not cfg:
        pilot=PILOT_COUNTIES.get(county_id)
        if pilot: cfg=dict(pilot)
    if not cfg:
        cfg=dict(get_county(county_id) or {})
        if cfg.get("arcgis_layer_url"):cfg["data_mode"]="arcgis"; cfg["scraper_type"]="arcgis"
        if cfg.get("field_mapping"):cfg["fields"]=cfg["field_mapping"]
    if cfg: cfg["county_id"]=county_id
    return cfg

def fetch_parcels(cfg:Dict[str,Any],county_id:str,max_records:int=5000)->List[Dict[str,Any]]:
    adapter=_adapter_for(cfg)
    if adapter:
        result,normalized=adapter.run({**cfg,"county_id":county_id,"max_records":max_records},max_records=max_records)
        if result.errors and not normalized: raise RuntimeError("; ".join(result.errors[:3]))
        return normalized[:max_records]
    if cfg.get("data_mode")=="flatfile":
        from scrapers.flatfile import fetch_el_paso_properties
        return fetch_el_paso_properties(county_id,max_records=max_records)
    if cfg.get("data_mode")=="arcgis" and cfg.get("arcgis_layer_url"):
        layer=cfg["arcgis_layer_url"]; available=arcgis.layer_fields(layer) or []
        configured=list(cfg.get("fields",{}).values()); out_fields=[f for f in configured if f in available]
        return [arcgis.map_attributes(a,cfg.get("fields",{}),county_id,cfg.get("defaults",{})) for a in arcgis.query_layer(layer,cfg.get("where","1=1"),out_fields,max_records=max_records)]
    return []

class RunMetrics:
    __slots__=('county_id','discovered','downloaded','parsed','normalized','rejected','rejection_reasons','stored','scored','qualified','published','errors')
    def __init__(self,county_id:str)->None:
        self.county_id=county_id; self.discovered=self.downloaded=self.parsed=self.normalized=self.rejected=self.stored=self.scored=self.qualified=self.published=0; self.rejection_reasons={}; self.errors=[]
    def to_counts(self):return {'discovered':self.discovered,'downloaded':self.downloaded,'parsed':self.parsed,'normalized':self.normalized,'rejected':self.rejected,'stored':self.stored,'scored':self.scored,'qualified':self.qualified,'published':self.published}
    def record_rejection(self,reason):self.rejected+=1; self.rejection_reasons[reason]=self.rejection_reasons.get(reason,0)+1

def _shape_for_bundle(row):
    return {k:row.get(k) for k in ('apn','address','county_id','lot_size_acres','asking_price','deal_score','estimated_arv_low','estimated_arv_high','estimated_profit_low','estimated_profit_high','market_velocity','competition_level','owner_state','zoning','tax_delinquent_years','source')}

def run(county_id:str,mode:str="publish",max_records:int=5000,dry_run:bool=False,offline:bool=False)->Dict[str,Any]:
    cfg=_county_config(county_id); m=RunMetrics(county_id); summary={'county_id':county_id,'counts':m.to_counts(),'status':'ok','error':''}
    if not cfg:
        summary.update(status='skipped',error='County has no configured or discovered source'); record_run(county_id,'skipped',summary['counts'],summary['error']); return summary
    try:
        props=fetch_parcels(cfg,county_id,max_records=max_records) if not offline else []
        m.downloaded=m.discovered=m.parsed=len(props)
        vacant=[p for p in props if arcgis.is_vacant_residential(p,county_id)]; m.normalized=len(vacant)
        scored=[]
        for prop in vacant:
            try: deal=score_and_enrich_deal(prop,[],cfg)
            except Exception as exc: m.record_rejection(f'score_error: {exc}'); continue
            if deal is None:m.record_rejection('below_min_profit'); continue
            deal.update(apn=prop.get('apn'),address=prop.get('address'),county_id=county_id)
            if not dry_run:
                try:
                    deal['property_id']=save_property(prop); deal['source']='scrape'; deal['motivation_signals']=','.join(deal.get('motivation_signals',[])); save_deal(deal); m.stored+=1
                except Exception as exc:m.errors.append(f'save_error: {exc}'); m.record_rejection('save_error'); continue
            scored.append(deal); m.scored+=1; m.qualified+=1
        # Only publish deals belonging to this county. This prevents a run for
        # one county from making unrelated global deals count as its coverage.
        if mode=='publish' and not dry_run:
            publish_rows=get_top_deals(limit=25,min_score=0,county_id=county_id)
        else:
            publish_rows=scored[:25]
        publish_deals=[_shape_for_bundle(d) for d in publish_rows]
        m.published=len(publish_deals)
        if mode=='publish' and not dry_run:
            summary['bundle_path']=write_bundle(publish_deals,[county_id],status='ok',error=summary['error'])
        summary['status']='degraded' if m.errors else 'ok'; summary['error']='; '.join(m.errors[:3]); summary['counts']=m.to_counts()
        if m.rejection_reasons: summary['rejection_reasons']=m.rejection_reasons
        record_run(county_id,summary['status'],summary['counts'],summary['error'])
        if not dry_run:
            mark_county_run(county_id,record_count=len(props),qualified_count=m.qualified,published_count=m.published,status=summary['status'],error=summary['error'])
    except Exception as exc:
        summary['status']='error'; summary['error']=f'{exc} | {traceback.format_exc(limit=2)}'; summary['counts']=m.to_counts(); record_run(county_id,'error',summary['counts'],summary['error'])
        if not dry_run: mark_county_run(county_id,record_count=0,status='error',error=summary['error'])
    return summary

class CountyRunner:
    def __init__(self,county_id):self.county_id=county_id
    def run(self,mode='publish',**kw):return run(self.county_id,mode=mode,**kw)
COUNTRY_RUNNERS={cid:CountyRunner(cid) for cid in COUNTY_SCRAPERS}
