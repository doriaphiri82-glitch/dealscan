"""DealScan national county registry with truthful, idempotent coverage state."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

REGISTRY_DIR=os.path.dirname(__file__)
REGISTRY_PATH=os.getenv("DEALSCAN_REGISTRY_PATH",os.path.join(REGISTRY_DIR,"registry.json"))

def _load_registry():
    try:
        with open(REGISTRY_PATH,encoding="utf-8") as f:return json.load(f)
    except FileNotFoundError:return {"counties":{},"meta":{"total":0,"by_state":{}}}

def _save_registry(reg):
    os.makedirs(os.path.dirname(os.path.abspath(REGISTRY_PATH)),exist_ok=True)
    tmp=REGISTRY_PATH+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:json.dump(reg,f,indent=2)
    os.replace(tmp,REGISTRY_PATH)

def _recompute_meta(reg):
    counties=reg.setdefault("counties",{}); by_state={}
    for c in counties.values():
        state=c.get("state","Unknown"); by_state[state]=by_state.get(state,0)+1
    reg["meta"]={**reg.get("meta",{}),"total":len(counties),"by_state":by_state}

def _entry(county_id:str,county_name:str,state:str,state_fips:str,county_fips:str,geoid:str,population:Optional[int]=None,data_source_type:Optional[str]=None,assessor_url:Optional[str]=None,gis_url:Optional[str]=None,parcel_source_url:Optional[str]=None,tax_source_url:Optional[str]=None,delinquent_tax_source_url:Optional[str]=None,zoning_source_url:Optional[str]=None,source_vendor:Optional[str]=None,scraper_type:Optional[str]=None,verification_status="not_implemented",coverage_status="tier_0",last_successful_run:Optional[str]=None,last_record_count:Optional[int]=None,data_freshness:Optional[str]=None,field_mapping:Optional[Dict[str,str]]=None,notes:Optional[str]=None,extra:Optional[Dict[str,Any]]=None):
    entry={"county_id":county_id,"county_name":county_name,"state":state,"state_fips":state_fips,"county_fips":county_fips,"geoid":geoid,"population":population,"data_source_type":data_source_type,"assessor_url":assessor_url,"gis_url":gis_url,"parcel_source_url":parcel_source_url,"tax_source_url":tax_source_url,"delinquent_tax_source_url":delinquent_tax_source_url,"zoning_source_url":zoning_source_url,"source_vendor":source_vendor,"scraper_type":scraper_type,"verification_status":verification_status,"coverage_status":coverage_status,"last_successful_run":last_successful_run,"last_record_count":last_record_count,"last_published_count":None,"data_freshness":data_freshness,"field_mapping":field_mapping or {},"notes":notes or ""}
    entry.update(extra or {}); return entry

def register_county(county_id:str,county_name:str,state:str,state_fips:str,county_fips:str,geoid:str,population:Optional[int]=None,data_source_type:Optional[str]=None,assessor_url:Optional[str]=None,gis_url:Optional[str]=None,parcel_source_url:Optional[str]=None,tax_source_url:Optional[str]=None,delinquent_tax_source_url:Optional[str]=None,zoning_source_url:Optional[str]=None,source_vendor:Optional[str]=None,scraper_type:Optional[str]=None,verification_status="not_implemented",coverage_status="tier_0",last_successful_run:Optional[str]=None,last_record_count:Optional[int]=None,data_freshness:Optional[str]=None,field_mapping:Optional[Dict[str,str]]=None,notes:Optional[str]=None,extra:Optional[Dict[str,Any]]=None,arcgis_layer_url:Optional[str]=None, **source_metadata):
    """Register one county, including ArcGIS layer identity when supplied."""
    reg=_load_registry(); counties=reg.setdefault("counties",{})
    extras={**(extra or {}), **source_metadata}
    if arcgis_layer_url is not None: extras["arcgis_layer_url"]=arcgis_layer_url
    counties[county_id]=_entry(county_id,county_name,state,state_fips,county_fips,geoid,population,data_source_type,assessor_url,gis_url,parcel_source_url,tax_source_url,delinquent_tax_source_url,zoning_source_url,source_vendor,scraper_type,verification_status,coverage_status,last_successful_run,last_record_count,data_freshness,field_mapping,notes,extras)
    _recompute_meta(reg); _save_registry(reg); return counties[county_id]

def register_counties_bulk(entries:List[Dict[str,Any]])->Dict[str,Dict[str,Any]]:
    reg=_load_registry(); counties=reg.setdefault("counties",{})
    for payload in entries:
        cid=payload.get("county_id")
        if not cid: continue
        base={k:payload.get(k) for k in ("county_id","county_name","state","state_fips","county_fips","geoid")}
        if any(base[k] in (None,"") for k in base): continue
        known={"county_id","county_name","state","state_fips","county_fips","geoid","population","data_source_type","assessor_url","gis_url","parcel_source_url","tax_source_url","delinquent_tax_source_url","zoning_source_url","source_vendor","scraper_type","verification_status","coverage_status","last_successful_run","last_record_count","data_freshness","field_mapping","notes"}
        entry=_entry(cid,payload["county_name"],payload["state"],payload["state_fips"],payload["county_fips"],payload["geoid"],payload.get("population"),payload.get("data_source_type"),payload.get("assessor_url"),payload.get("gis_url"),payload.get("parcel_source_url"),payload.get("tax_source_url"),payload.get("delinquent_tax_source_url"),payload.get("zoning_source_url"),payload.get("source_vendor"),payload.get("scraper_type"),payload.get("verification_status","not_implemented"),payload.get("coverage_status","tier_0"),payload.get("last_successful_run"),payload.get("last_record_count"),payload.get("data_freshness"),payload.get("field_mapping",{}),payload.get("notes","") ,extra={k:v for k,v in payload.items() if k not in known})
        counties[cid]=entry
    _recompute_meta(reg); _save_registry(reg); return counties

def get_county(county_id): return _load_registry().get("counties",{}).get(county_id)
def list_counties(state:Optional[str]=None):
    out=list(_load_registry().get("counties",{}).values()); return [c for c in out if not state or c.get("state")==state]
def update_county(county_id,**fields):
    reg=_load_registry(); entry=reg.get("counties",{}).get(county_id)
    if not entry:return None
    identity_keys = {'arcgis_layer_url', 'parcel_source_url', 'data_url', 'field_mapping', 'where', 'acreage_units',
                     'authority_reviewed', 'authority_source_url', 'authority_evidence_url', 'source_county_geoid'}
    if any(key in fields and fields[key] != entry.get(key) for key in identity_keys):
        entry.update(validation_status='pending', ingestion_authorized=False,
                     validated_source_fingerprint=None, authorized_source_fingerprint=None)
    entry.update(fields)
    _recompute_meta(reg); _save_registry(reg); return entry

def mark_county_validation(county_id:str, *, status:str, errors:Optional[List[str]]=None, warnings:Optional[List[str]]=None, source_fields_checked:bool=False, sample_checked:int=0, pagination_checked:bool=False, fingerprint:Optional[str]=None):
    entry=get_county(county_id)
    if not entry:return None
    now=datetime.now(timezone.utc).isoformat()
    return update_county(county_id,last_validated_at=now,validation_status=str(status),validation_errors=(errors or [])[:20],validation_warnings=(warnings or [])[:20],validation_source_fields_checked=bool(source_fields_checked),validation_sample_checked=max(0,int(sample_checked)),validation_pagination_checked=pagination_checked,validated_source_fingerprint=fingerprint if status=='valid' else None,ingestion_authorized=False,authorized_source_fingerprint=None)

def mark_county_run(county_id:str, *, record_count:int, qualified_count:int=0, published_count:int=0, persisted_count:int=0, status:str="ok", error:str=""):
    entry=get_county(county_id)
    if not entry:return None
    now=datetime.now(timezone.utc).isoformat(); record_count=max(0,int(record_count)); persisted_count=max(0,int(persisted_count)); qualified_count=max(0,int(qualified_count)); published_count=max(0,int(published_count))
    fields={"last_record_count":record_count,"last_persisted_count":persisted_count,"last_published_count":published_count,
            "record_count":record_count,"persisted_count":persisted_count,"qualified_count":qualified_count,"published_count":published_count,
            "last_run_at":now,"last_run_status":status,"last_run_error":error or None,
            "ingestion_status":"ingested" if status=="ok" and persisted_count>0 else "completed_no_candidates" if status=="ok" and record_count>0 else status}
    if status=="ok" and persisted_count>0: fields.update({"last_successful_run":now,"verification_status":"verified" if published_count>0 else "source_verified","coverage_status":"tier_5" if published_count>0 else "tier_4"})
    elif status=="ok" and record_count>0: fields.update({"last_successful_run":now,"verification_status":"source_verified","coverage_status":"tier_3"})
    else: fields["verification_status"]="discovered_not_verified" if entry.get("data_source_type") else "not_started"; fields["coverage_status"]=entry.get("coverage_status") or "tier_0"
    note=f"Last ETL: records={record_count}, persisted={persisted_count}, qualified={qualified_count}, published={published_count}, status={status}."
    if error: note+=f" Error: {error[:300]}"
    fields["notes"]=(entry.get("notes","").split(" | Last ETL:")[0].strip()+" | "+note).strip(" |")
    return update_county(county_id,**fields)

def remove_county(county_id):
    reg=_load_registry(); existed=reg.get("counties",{}).pop(county_id,None) is not None
    if existed:_recompute_meta(reg); _save_registry(reg)
    return existed

def county_summary():
    counties=list(_load_registry().get("counties",{}).values()); by_status={}; by_state={}
    for c in counties:
        s=c.get("coverage_status","tier_0"); by_status[s]=by_status.get(s,0)+1; st=c.get("state","Unknown"); by_state[st]=by_state.get(st,0)+1
    return {"total":len(counties),"by_coverage_status":by_status,"by_state":by_state}
