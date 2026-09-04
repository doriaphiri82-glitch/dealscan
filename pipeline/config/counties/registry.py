"""DealScan national county registry with truthful, idempotent coverage state."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

REGISTRY_DIR=os.path.dirname(__file__)
REGISTRY_PATH=os.path.join(REGISTRY_DIR,"registry.json")


def _load_registry():
    try:
        with open(REGISTRY_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return {"counties":{},"meta":{"total":0,"by_state":{}}}


def _save_registry(reg):
    os.makedirs(REGISTRY_DIR,exist_ok=True)
    tmp=REGISTRY_PATH+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:json.dump(reg,f,indent=2)
    os.replace(tmp,REGISTRY_PATH)


def _recompute_meta(reg):
    counties=reg.setdefault("counties",{})
    by_state={}
    for c in counties.values():
        state=c.get("state","Unknown")
        by_state[state]=by_state.get(state,0)+1
    reg["meta"]={"total":len(counties),"by_state":by_state}


def register_county(county_id:str,county_name:str,state:str,state_fips:str,county_fips:str,geoid:str,population:Optional[int]=None,data_source_type:Optional[str]=None,assessor_url:Optional[str]=None,gis_url:Optional[str]=None,parcel_source_url:Optional[str]=None,tax_source_url:Optional[str]=None,delinquent_tax_source_url:Optional[str]=None,zoning_source_url:Optional[str]=None,source_vendor:Optional[str]=None,scraper_type:Optional[str]=None,verification_status="not_implemented",coverage_status="tier_0",last_successful_run:Optional[str]=None,last_record_count:Optional[int]=None,data_freshness:Optional[str]=None,field_mapping:Optional[Dict[str,str]]=None,notes:Optional[str]=None,extra:Optional[Dict[str,Any]]=None):
    reg=_load_registry(); counties=reg.setdefault("counties",{})
    entry={"county_id":county_id,"county_name":county_name,"state":state,"state_fips":state_fips,"county_fips":county_fips,"geoid":geoid,"population":population,"data_source_type":data_source_type,"assessor_url":assessor_url,"gis_url":gis_url,"parcel_source_url":parcel_source_url,"tax_source_url":tax_source_url,"delinquent_tax_source_url":delinquent_tax_source_url,"zoning_source_url":zoning_source_url,"source_vendor":source_vendor,"scraper_type":scraper_type,"verification_status":verification_status,"coverage_status":coverage_status,"last_successful_run":last_successful_run,"last_record_count":last_record_count,"data_freshness":data_freshness,"field_mapping":field_mapping or {},"notes":notes or ""}
    entry.update(extra or {}); counties[county_id]=entry; _recompute_meta(reg); _save_registry(reg); return entry


def get_county(county_id): return _load_registry().get("counties",{}).get(county_id)


def list_counties(state:Optional[str]=None):
    out=list(_load_registry().get("counties",{}).values()); return [c for c in out if not state or c.get("state")==state]


def update_county(county_id,**fields):
    reg=_load_registry(); entry=reg.get("counties",{}).get(county_id)
    if not entry:return None
    entry.update({k:v for k,v in fields.items() if v is not None}); _recompute_meta(reg); _save_registry(reg); return entry


def mark_county_run(county_id:str, *, record_count:int, qualified_count:int=0, published_count:int=0, status:str="ok", error:str=""):
    """Promote coverage only from evidence produced by a real ETL run.

    tier_0: no source/extraction
    tier_1: source discovered
    tier_3: source reached and records normalized
    tier_4: records persisted successfully
    tier_5: qualified deals published
    """
    entry=get_county(county_id)
    if not entry:return None
    now=datetime.now(timezone.utc).isoformat()
    fields={"last_successful_run":now,"last_record_count":int(record_count),"data_freshness":now}
    if status in ("ok","degraded") and record_count>0:
        fields["verification_status"]="verified"
        fields["coverage_status"]="tier_5" if published_count>0 else "tier_4"
    elif status=="ok" and record_count==0:
        fields["verification_status"]="source_verified"
        fields["coverage_status"]="tier_3"
    else:
        fields["verification_status"]="discovered_not_verified" if entry.get("data_source_type") else "not_started"
        fields["coverage_status"]=entry.get("coverage_status") or "tier_0"
    note=f"Last ETL: records={record_count}, qualified={qualified_count}, published={published_count}, status={status}."
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
