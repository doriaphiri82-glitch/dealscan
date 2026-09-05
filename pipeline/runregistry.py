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
def _record_supabase_audit(county_id:str,status:str,counts:Dict[str,Any],error:str)->None:
    """Mirror local run-registry events into production audit storage when enabled."""
    if os.getenv("DEALSCAN_DB_BACKEND", "sqlite").strip().lower() != "supabase":
        return
    try:
        from database_supabase import SupabaseDatabase
        county = {}
        try:
            from config.counties.registry import get_county
            county = get_county(county_id) or {}
        except Exception:
            pass
        SupabaseDatabase().record_ingestion_run(
            county_id=county_id,
            status=status,
            counts=counts,
            error=error,
            source_url=county.get("arcgis_layer_url") or county.get("parcel_source_url") or county.get("gis_url"),
            metadata={"local_registry": True},
        )
    except Exception as exc:
        # Audit failure must not hide the primary ETL result; the pipeline summary
        # already records its operational errors separately.
        print(f"WARNING: Supabase ingestion audit unavailable: {str(exc)[:300]}")

def record_run(county_id,status,counts,error=""):
    reg=load_registry(); entry={"county_id":county_id,"status":status,"counts":counts,"error":error,"at":datetime.now(timezone.utc).isoformat()}; reg.setdefault("runs",[]).insert(0,entry); reg["runs"]=reg["runs"][:100]; reg["last_run"]=entry; _ensure_dir()
    with open(REGISTRY_PATH,"w",encoding="utf-8") as f:json.dump(reg,f,indent=1)
    _record_supabase_audit(county_id,status,counts,error)
    return entry
def _load_existing_bundle():
    try:
        with open(BUNDLE_PATH,encoding="utf-8") as f:return json.load(f)
    except Exception:return {"deals":[],"meta":{"scraped_counties":[]}}
def write_bundle(deals:List[Dict[str,Any]],scraped_counties:List[str],status="ok",error=""):
    """Publish incrementally: republishing one county never erases other counties."""
    old=_load_existing_bundle(); target=set(scraped_counties); merged={}
    for d in old.get("deals",[]):
        if isinstance(d,dict) and d.get("county_id") not in target:
            merged[d.get("apn") or d.get("id") or len(merged)]=d
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
