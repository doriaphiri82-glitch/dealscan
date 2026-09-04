"""DealScan pipeline run registry and durable published bundle."""
from __future__ import annotations
import json,os
from datetime import datetime,timezone
from typing import Any,Dict,List,Optional
DATA_DIR=os.path.join(os.path.dirname(__file__),"data"); REGISTRY_PATH=os.path.join(DATA_DIR,"registry.json"); BUNDLE_PATH=os.path.join(DATA_DIR,"bundle.json")
def _ensure_dir():os.makedirs(DATA_DIR,exist_ok=True)
def load_registry():
    _ensure_dir()
    try:
        with open(REGISTRY_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return {"runs":[],"last_run":None}
def record_run(county_id,status,counts,error=""):
    reg=load_registry(); entry={"county_id":county_id,"status":status,"counts":counts,"error":error,"at":datetime.now(timezone.utc).isoformat()}; reg.setdefault("runs",[]).insert(0,entry); reg["runs"]=reg["runs"][:100]; reg["last_run"]=entry; _ensure_dir()
    with open(REGISTRY_PATH,"w",encoding="utf-8") as f:json.dump(reg,f,indent=1)
    return entry
def _load_existing_bundle():
    try:
        with open(BUNDLE_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return {"deals":[],"meta":{"scraped_counties":[]}}
def _deal_key(d:Dict[str,Any],fallback:int)->str:
    county=str(d.get("county_id") or "unknown").strip(); apn=str(d.get("apn") or d.get("id") or fallback).strip(); return f"{county}:{apn}"
def write_bundle(deals:List[Dict[str,Any]],scraped_counties:List[str],status="ok",error=""):
    """Publish incrementally without cross-county APN collisions."""
    old=_load_existing_bundle(); target=set(scraped_counties); merged={}
    for i,d in enumerate(old.get("deals",[])):
        if isinstance(d,dict) and d.get("county_id") not in target:merged[_deal_key(d,i)]=d
    for i,d in enumerate(deals):
        if isinstance(d,dict):merged[_deal_key(d,i)]=d
    counties=sorted(set(old.get("meta",{}).get("scraped_counties",[]))|target)
    bundle={"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(merged),"deals":list(merged.values()),"error":error,"meta":{"scraped_counties":counties,"status":status}}
    _ensure_dir()
    with open(BUNDLE_PATH,"w",encoding="utf-8") as f:json.dump(bundle,f,indent=1)
    return BUNDLE_PATH
def load_bundle()->Optional[Dict[str,Any]]:
    try:
        with open(BUNDLE_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return None
