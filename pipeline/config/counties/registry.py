"""DealScan national county registry."""
from __future__ import annotations
import json, os
from typing import Any, Dict, List, Optional
REGISTRY_DIR=os.path.dirname(__file__); REGISTRY_PATH=os.path.join(REGISTRY_DIR,"registry.json")
def _load_registry():
    try:
        with open(REGISTRY_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return {"counties":{},"meta":{"total":0,"by_state":{}}}
def _save_registry(reg):
    os.makedirs(REGISTRY_DIR,exist_ok=True)
    with open(REGISTRY_PATH,"w",encoding="utf-8") as f:json.dump(reg,f,indent=2)
def register_county(county_id:str,county_name:str,state:str,state_fips:str,county_fips:str,geoid:str,population:Optional[int]=None,data_source_type:Optional[str]=None,assessor_url:Optional[str]=None,gis_url:Optional[str]=None,parcel_source_url:Optional[str]=None,tax_source_url:Optional[str]=None,delinquent_tax_source_url:Optional[str]=None,zoning_source_url:Optional[str]=None,source_vendor:Optional[str]=None,scraper_type:Optional[str]=None,verification_status="not_implemented",coverage_status="tier_0",last_successful_run:Optional[str]=None,last_record_count:Optional[int]=None,data_freshness:Optional[str]=None,field_mapping:Optional[Dict[str,str]]=None,notes:Optional[str]=None,extra:Optional[Dict[str,Any]]=None):
    reg=_load_registry(); counties=reg.setdefault("counties",{}); entry={"county_id":county_id,"county_name":county_name,"state":state,"state_fips":state_fips,"county_fips":county_fips,"geoid":geoid,"population":population,"data_source_type":data_source_type,"assessor_url":assessor_url,"gis_url":gis_url,"parcel_source_url":parcel_source_url,"tax_source_url":tax_source_url,"delinquent_tax_source_url":delinquent_tax_source_url,"zoning_source_url":zoning_source_url,"source_vendor":source_vendor,"scraper_type":scraper_type,"verification_status":verification_status,"coverage_status":coverage_status,"last_successful_run":last_successful_run,"last_record_count":last_record_count,"data_freshness":data_freshness,"field_mapping":field_mapping or {},"notes":notes or ""}; entry.update(extra or {}); counties[county_id]=entry
    # Recompute metadata instead of incrementing, so repeated national refreshes are idempotent.
    reg["meta"]={"total":len(counties),"by_state":{}}
    for c in counties.values(): reg["meta"]["by_state"][c.get("state","Unknown")]=reg["meta"]["by_state"].get(c.get("state","Unknown"),0)+1
    _save_registry(reg); return entry
def get_county(county_id): return _load_registry().get("counties",{}).get(county_id)
def list_counties(state:Optional[str]=None):
    out=list(_load_registry().get("counties",{}).values()); return [c for c in out if not state or c.get("state")==state]
def update_county(county_id,**fields):
    reg=_load_registry(); entry=reg.get("counties",{}).get(county_id)
    if not entry:return None
    entry.update({k:v for k,v in fields.items() if v is not None}); reg["meta"]={"total":len(reg.get("counties",{})),"by_state":{}}
    for c in reg["counties"].values():reg["meta"]["by_state"][c.get("state","Unknown")]=reg["meta"]["by_state"].get(c.get("state","Unknown"),0)+1
    _save_registry(reg); return entry
def remove_county(county_id):
    reg=_load_registry(); existed=reg.get("counties",{}).pop(county_id,None) is not None
    if existed:
        reg["meta"]={"total":len(reg["counties"]),"by_state":{}}
        for c in reg["counties"].values():reg["meta"]["by_state"][c.get("state","Unknown")]=reg["meta"]["by_state"].get(c.get("state","Unknown"),0)+1
        _save_registry(reg)
    return existed
def county_summary():
    counties=list(_load_registry().get("counties",{}).values()); by_status={}; by_state={}
    for c in counties:
        s=c.get("coverage_status","tier_0"); by_status[s]=by_status.get(s,0)+1; st=c.get("state","Unknown"); by_state[st]=by_state.get(st,0)+1
    return {"total":len(counties),"by_coverage_status":by_status,"by_state":by_state}
