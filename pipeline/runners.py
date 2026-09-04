"""DealScan - Per-county run runner."""
from __future__ import annotations
from typing import Any, Dict, Optional
from config.counties.national_registry import PILOT_COUNTIES
from config.counties.registry import get_county, mark_county_run
from database import get_top_deals, save_comps, save_deal, save_property
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
        elif cfg.get("arcgis_root") or cfg.get("parcel_source_url"): cfg["data_mode"]="arcgis"; cfg["scraper_type"]="arcgis"
        if cfg.get("field_mapping"):cfg["fields"]=cfg["field_mapping"]
    if cfg: cfg["county_id"]=county_id
    return cfg

def _resolve_hub_layer(cfg:Dict[str,Any])->Dict[str,Any]:
    if cfg.get("arcgis_layer_url"): return cfg
    root=cfg.get("arcgis_root") or cfg.get("gis_url")
    if not root or "opendata.arcgis.com" not in root:return cfg
    layer=arcgis.find_layer_via_hub(root,["parcel","ownership","tax parcel","cadastral"])
    if not layer:return cfg
    resolved=dict(cfg); resolved["arcgis_layer_url"]=layer; resolved["data_mode"]="arcgis"; resolved["scraper_type"]="arcgis"; return resolved

def fetch_parcels(cfg:Dict[str,Any],county_id:str,max_records:int=5000):
    cfg=_resolve_hub_layer(cfg); adapter=_adapter_for(cfg)
    if adapter:
        result,normalized=adapter.run({**cfg,"county_id":county_id,"max_records":max_records},max_records=max_records)
        if result.errors and not normalized:
            raise RuntimeError(f"source error before usable records: {'; '.join(result.errors[:3])}")
        result.metadata["resolved_layer_url"]=cfg.get("arcgis_layer_url")
        return normalized,result
    if cfg.get("data_mode")=="flatfile":
        from scrapers.flatfile import fetch_el_paso_properties
        props=fetch_el_paso_properties(county_id,max_records=max_records); return props,None
    if cfg.get("data_mode")=="arcgis" and cfg.get("arcgis_layer_url"):
        layer=cfg["arcgis_layer_url"]; available=arcgis.layer_fields(layer) or []
        configured=list(cfg.get("fields",{}).values()); out_fields=[]
        for field in configured:
            if isinstance(field,(list,tuple)):out_fields.extend([f for f in field if f in available])
            elif field in available:out_fields.append(field)
        out_fields=list(dict.fromkeys(out_fields))
        if not out_fields:raise RuntimeError("configured field mapping has no fields present in source layer")
        props=[arcgis.map_attributes(a,cfg.get("fields",{}),county_id,cfg.get("defaults",{})) for a in arcgis.query_layer(layer,cfg.get("where","1=1"),out_fields,max_records=max_records)]
        return props,None
    return [],None

class RunMetrics:
    __slots__=('county_id','discovered','downloaded','parsed','normalized','rejected','rejection_reasons','stored','scored','qualified','published','errors','field_coverage','vacancy_rejection_reasons','comparable_count')
    def __init__(self,county_id:str)->None:
        self.county_id=county_id; self.discovered=self.downloaded=self.parsed=self.normalized=self.rejected=self.stored=self.scored=self.qualified=self.published=0
        self.rejection_reasons={}; self.errors=[]; self.field_coverage={}; self.vacancy_rejection_reasons={}; self.comparable_count=0
    def to_counts(self):return {'discovered':self.discovered,'downloaded':self.downloaded,'parsed':self.parsed,'normalized':self.normalized,'rejected':self.rejected,'stored':self.stored,'scored':self.scored,'qualified':self.qualified,'published':self.published}
    def record_rejection(self,reason):self.rejected+=1; self.rejection_reasons[reason]=self.rejection_reasons.get(reason,0)+1
    def record_vacancy_rejection(self,reason):self.rejected+=1; self.vacancy_rejection_reasons[reason]=self.vacancy_rejection_reasons.get(reason,0)+1; self.rejection_reasons[reason]=self.rejection_reasons.get(reason,0)+1

def _shape_for_bundle(row):return {k:row.get(k) for k in ('apn','address','county_id','lot_size_acres','asking_price','asking_price_basis','deal_score','estimated_arv_low','estimated_arv_high','estimated_profit_low','estimated_profit_high','recommended_offer_low','recommended_offer_high','market_velocity','competition_level','owner_state','zoning','tax_delinquent_years','valuation_basis','valuation_confidence','source','source_url','source_vendor','source_quality','verification_status','data_freshness')}
def _provenance(cfg,county_id):
    county=get_county(county_id) or {}; return {'source_url':cfg.get('arcgis_layer_url') or cfg.get('parcel_source_url') or cfg.get('data_url') or county.get('parcel_source_url'),'source_vendor':cfg.get('source_vendor') or county.get('source_vendor'),'source_quality':cfg.get('source_quality') or county.get('source_quality'),'verification_status':county.get('verification_status'),'data_freshness':cfg.get('source_last_modified') or county.get('data_freshness')}

def _qualification_rejection_reason(prop: Dict[str,Any], comps: list)->str:
    """Explain why scoring returned no deal without changing qualification rules."""
    if not comps:
        market_value=prop.get('market_value') or prop.get('assessed_value') or 0
        asking=prop.get('asking_price')
        try: has_value=float(market_value)>0
        except (TypeError,ValueError): has_value=False
        if not has_value and asking is None:return 'missing_valuation_evidence'
        if asking is not None:
            try:
                if float(asking)<=0 and not has_value:return 'missing_valuation_evidence'
            except (TypeError,ValueError):return 'invalid_asking_price'
    return 'below_min_profit'

def _vacancy_rejection_reason(prop:Dict[str,Any],county_id:str)->str:
    """Return a truthful reason when a parcel lacks a credible vacant signal."""
    imp=prop.get('has_improvements'); lu=str(prop.get('land_use') or '').strip().lower(); zoning=str(prop.get('zoning') or '').strip().lower(); code=str(prop.get('use_code') or prop.get('land_use') or '').strip().upper()
    has_imp=imp is True or imp in (1,'1','Y','YES','Yes','true','True')
    if has_imp:return 'improved_property'
    if any(token in lu for token in ('vacant','unimproved')) or 'vacant' in zoning:return ''
    if imp is False or imp == 0 or imp in ('0','N','NO','No','NONE','false','False'):
        if 'residential' in lu or 'res' in zoning or 'residential' in zoning:return ''
        if code in {str(x).upper() for x in arcgis.VACANT_LAND_USE_CODES.get(county_id, [])}:return ''
        return 'no_supported_vacancy_classification'
    return 'missing_vacancy_signal'

def _field_coverage(props:list)->Dict[str,Dict[str,int]]:
    fields=('apn','lot_size_acres','market_value','assessed_value','asking_price','land_use','use_code','has_improvements','improvement_value','latitude','longitude','owner_name','owner_state','zoning','last_sale_price','last_sale_date')
    return {field:{'populated':sum(1 for p in props if p.get(field) not in (None,'',' ')),'total':len(props)} for field in fields}

def run(county_id:str,mode:str="publish",max_records:int=5000,dry_run:bool=False,offline:bool=False)->Dict[str,Any]:
    cfg=_county_config(county_id); m=RunMetrics(county_id); summary={'county_id':county_id,'counts':m.to_counts(),'status':'ok','error':''}
    if not cfg:summary.update(status='skipped',error='County has no configured or discovered source');record_run(county_id,'skipped',summary['counts'],summary['error']);return summary
    try:
        props,scrape_result=fetch_parcels(cfg,county_id,max_records=max_records) if not offline else ([],None)
        if scrape_result:
            m.discovered=scrape_result.discovered;m.downloaded=scrape_result.downloaded;m.parsed=scrape_result.parsed;m.normalized=scrape_result.normalized;m.rejected=scrape_result.rejected;m.rejection_reasons.update(scrape_result.rejection_reasons);m.errors.extend(scrape_result.errors)
        else:m.downloaded=m.discovered=m.parsed=len(props);m.normalized=len(props)
        if offline:summary.update(status='skipped',error='offline mode: source not queried',counts=m.to_counts());record_run(county_id,'skipped',summary['counts'],summary['error']);return summary
        if cfg.get('arcgis_layer_url') and m.discovered==0:raise RuntimeError('source returned zero records; this is not treated as verified ETL success')
        m.field_coverage=_field_coverage(props)
        vacant=[]
        for p in props:
            reason=_vacancy_rejection_reason(p,county_id)
            if reason:m.record_vacancy_rejection(reason)
            else:vacant.append(p)
        for prop in vacant:
            try:
                scoring_prop={**prop,'_source_comp_pool':props}
                deal=score_and_enrich_deal(scoring_prop,[],cfg)
            except Exception as exc:m.record_rejection(f'score_error: {exc}');continue
            if deal is None:m.record_rejection(_qualification_rejection_reason(prop,[]));continue
            deal.update(apn=prop.get('apn'),address=prop.get('address'),county_id=county_id);deal.update(_provenance(cfg,county_id))
            if not dry_run:
                try:
                    deal['property_id']=save_property(prop)
                    deal['source']='scrape'
                    deal['motivation_signals']=','.join(deal.get('motivation_signals',[]))
                    deal_id=save_deal(deal)
                    save_comps(deal_id,deal.get('comps',[]))
                    m.comparable_count += len(deal.get('comps',[]))
                    m.stored+=1
                except Exception as exc:m.errors.append(f'save_error: {exc}');m.record_rejection('save_error');continue
            else:m.comparable_count += len(deal.get('comps',[]))
            m.scored+=1;m.qualified+=1
        publish_rows=get_top_deals(limit=25,min_score=0,county_id=county_id) if mode=='publish' and not dry_run else []
        publish_deals=[]
        for row in publish_rows:
            shaped=_shape_for_bundle(row)
            try:
                from database import get_deal_comps
                shaped['comps']=get_deal_comps(row['id'])
            except Exception as exc:
                m.errors.append(f'comps_read_error: {exc}')
                shaped['comps']=[]
            publish_deals.append(shaped)
        m.published=len(publish_deals)
        if mode=='publish' and not dry_run:summary['bundle_path']=write_bundle(publish_deals,[county_id],status='ok',error='')
        if m.errors:summary['status']='degraded'
        elif m.normalized and m.qualified==0:summary['status']='degraded';summary['error']='No financially qualified candidates from the normalized source records'
        else:summary['status']='ok'
        if not summary['error']:summary['error']='; '.join(m.errors[:3])
        summary['counts']=m.to_counts();summary['diagnostics']={'field_coverage':m.field_coverage,'vacancy':{'candidates':len(props),'accepted':len(vacant),'rejected':sum(m.vacancy_rejection_reasons.values()),'rejection_reasons':m.vacancy_rejection_reasons},'qualification':{'scored':m.scored,'qualified':m.qualified,'rejection_reasons':{k:v for k,v in m.rejection_reasons.items() if k not in m.vacancy_rejection_reasons}},'comparables':{'source_derived_rows':m.comparable_count}}
        if m.rejection_reasons:summary['rejection_reasons']=m.rejection_reasons
        record_run(county_id,summary['status'],summary['counts'],summary['error'])
        etl_status='ok' if m.normalized>0 and not m.errors else summary['status']
        if not dry_run:mark_county_run(county_id,record_count=len(props),qualified_count=m.qualified,published_count=m.published,persisted_count=m.stored,status=etl_status,error=summary['error'])
    except Exception as exc:
        summary['status']='error';summary['error']=str(exc);summary['counts']=m.to_counts();record_run(county_id,'error',summary['counts'],summary['error'])
        if not dry_run:mark_county_run(county_id,record_count=m.normalized,persisted_count=m.stored,status='error',error=summary['error'])
    return summary

class CountyRunner:
    def __init__(self,county_id):self.county_id=county_id
    def run(self,mode='publish',**kw):return run(self.county_id,mode=mode,**kw)
COUNTRY_RUNNERS={cid:CountyRunner(cid) for cid in COUNTY_SCRAPERS}
