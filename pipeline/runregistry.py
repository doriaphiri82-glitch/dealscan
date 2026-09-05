"""DealScan pipeline run registry and durable published bundle."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
DATA_DIR=os.path.join(os.path.dirname(__file__),"data"); REGISTRY_PATH=os.path.join(DATA_DIR,"registry.json"); BUNDLE_PATH=os.path.join(DATA_DIR,"bundle.json")
def _ensure_dir(): os.makedirs(DATA_DIR,exist_ok=True)
def load_registry():
    _ensure_dir()
    try:
        with open(REGISTRY_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return {"runs":[],"last_run":None}
def _record_supabase_audit(county_id:str,status:str,counts:Dict[str,Any],error:str)->Optional[int]:
    if os.getenv("DEALSCAN_DB_BACKEND", "sqlite").strip().lower() != "supabase": return None
    try:
        from database_supabase import SupabaseDatabase
        db=SupabaseDatabase(); county={}
        try:
            from config.counties.registry import get_county
            county=get_county(county_id) or {}
        except Exception: pass
        source_url=county.get("arcgis_layer_url") or county.get("parcel_source_url") or county.get("gis_url")
        active=os.getenv("DEALSCAN_ACTIVE_AUDIT_RUN_ID")
        if active:
            try:
                run_id=db.update_ingestion_run(int(active),county_id,status,counts,error,metadata={"local_registry":True})
                os.environ.pop("DEALSCAN_ACTIVE_AUDIT_RUN_ID",None)
                return run_id
            except Exception as exc:
                print(f"WARNING: Supabase ingestion audit finalization failed: {str(exc)[:300]}")
        return db.record_ingestion_run(county_id,status,counts,error,source_url=source_url,metadata={"local_registry":True})
    except Exception as exc:
        print(f"WARNING: Supabase ingestion audit unavailable: {str(exc)[:300]}")
        return None

def record_run(county_id,status,counts,error=""):
    reg=load_registry(); entry={"county_id":county_id,"status":status,"counts":counts,"error":error,"at":datetime.now(timezone.utc).isoformat()}; audit_id=_record_supabase_audit(county_id,status,counts,error); 
    if audit_id is not None: entry["supabase_run_id"]=audit_id
    reg.setdefault("runs",[]).insert(0,entry); reg["runs"]=reg["runs"][:100]; reg["last_run"]=entry; _ensure_dir()
    with open(REGISTRY_PATH,"w",encoding="utf-8") as f:json.dump(reg,f,indent=1)
    return entry
def _load_existing_bundle():
    try:
        with open(BUNDLE_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return {"deals":[],"meta":{"scraped_counties":[]}}
def write_bundle(deals:List[Dict[str,Any]],scraped_counties:List[str],status="ok",error=""):
    old=_load_existing_bundle(); target=set(scraped_counties); merged={}
    for d in old.get("deals",[]):
        if isinstance(d,dict) and d.get("county_id") not in target: merged[d.get("apn") or d.get("id") or len(merged)]=d
    for d in deals:
        if isinstance(d,dict): merged[d.get("apn") or d.get("id") or len(merged)]=d
    counties=sorted(set(old.get("meta",{}).get("scraped_counties",[]))|target)
    bundle={"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(merged),"deals":list(merged.values()),"error":error,"meta":{"scraped_counties":counties,"status":status}}
    _ensure_dir()
    with open(BUNDLE_PATH,"w",encoding="utf-8") as f:json.dump(bundle,f,indent=1)
    return BUNDLE_PATH
def load_bundle()->Optional[Dict[str,Any]]:
    try:
        with open(BUNDLE_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return None
