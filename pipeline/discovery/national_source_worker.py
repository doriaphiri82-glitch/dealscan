"""Controlled national source discovery and ETL batching."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from config.counties.national_registry import ensure_national_counties
from config.counties.registry import list_counties, update_county
from discovery.source_discovery import discover_arcgis_county_config, enumerate_statewide_counties
from discovery.statewide_pipeline import reconcile_enumerated_statewide_counties
from discovery.statewide_queue import build_county_discovery_queue
from discovery.statewide_sources import all_statewide_sources
from discovery.statewide_coverage import build_statewide_coverage_report
from runners import run as run_county
from validation.gates import authorization_error
from config.source_config import county_config


def _limit(value:int,default:int=25)->int:
    try:return max(0,min(int(value),250))
    except (TypeError,ValueError):return default


def _statewide_snapshot(states: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Build one deterministic statewide snapshot for queueing and coverage."""
    census = ensure_national_counties()
    if not isinstance(census, dict):
        return {"census": {}, "reconciled": [], "queue": [], "coverage": {"states": {}, "totals": {}}}
    wanted = {str(state).strip().lower() for state in states} if states else None
    candidates: List[Dict[str, Any]] = []
    source_states = sorted({source.state for source in all_statewide_sources() if source.source_type == 'arcgis_layer'})
    for state in source_states:
        if wanted and state.lower() not in wanted:
            continue
        candidates.extend(enumerate_statewide_counties(state))
    reconciled = reconcile_enumerated_statewide_counties(candidates, census.values())
    registry = list_counties()
    queue = build_county_discovery_queue(reconciled, registry)
    coverage = build_statewide_coverage_report(reconciled, census.values(), registry, states=states)
    return {"census": census, "reconciled": reconciled, "queue": queue, "coverage": coverage}


def _statewide_queue(states: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    return _statewide_snapshot(states)["queue"]


def discover_and_register(limit:int=25, states: Optional[Iterable[str]] = None, statewide_queue: Optional[List[Dict[str, Any]]] = None, persist: bool = True)->Dict[str,Any]:
    """Discover sources fairly, optionally persisting registry changes."""
    ensure_national_counties()
    statewide_error = None
    if statewide_queue is None:
        try: statewide = _statewide_queue(states)
        except Exception as exc:
            statewide = []; statewide_error = str(exc)[:300]
    else: statewide = list(statewide_queue)
    queued_ids = {row["county_id"] for row in statewide}
    wanted = {str(state).strip().lower() for state in states} if states else None
    candidates=[c for c in list_counties() if c.get("coverage_status")!="tier_5" and ((not c.get("arcgis_layer_url") and not c.get("parcel_source_url")) or c.get("validation_status") in {"invalid","unreachable"})]
    if wanted: candidates=[c for c in candidates if str(c.get("state") or "").strip().lower() in wanted]
    candidates.sort(key=lambda c:(c.get("discovery_attempted_at") is not None,c.get("discovery_attempted_at") or "",c.get("state",""),c.get("county_name","")))
    statewide_by_id = {row["county_id"]: row for row in statewide}
    prioritized = [c for c in candidates if c.get("county_id") in queued_ids]
    fallback = [c for c in candidates if c.get("county_id") not in queued_ids]
    batch=(prioritized + fallback)[:_limit(limit)]
    results=[];found=0
    for county in batch:
        cid=county["county_id"]; attempted_at=datetime.now(timezone.utc).isoformat()
        if persist: update_county(cid,discovery_attempted_at=attempted_at)
        try:
            cfg=discover_arcgis_county_config(cid,county["county_name"],county["state"])
            if not cfg:
                results.append({"county_id":cid,"status":"not_found","statewide_hint":cid in statewide_by_id}); continue
            fields=cfg.get("fields",{});quality=cfg.get("source_quality","partial");freshness=cfg.get("source_last_modified");layer_url=cfg.get("arcgis_layer_url")
            patch={"data_source_type":"arcgis","gis_url":cfg.get("arcgis_root"),"parcel_source_url":layer_url,"arcgis_layer_url":layer_url,"source_vendor":"esri","scraper_type":"arcgis","verification_status":"discovered_not_verified","coverage_status":"tier_1","validation_status":"pending","ingestion_authorized":False,"validated_source_fingerprint":None,"authorized_source_fingerprint":None,"last_validated_at":None,"field_mapping":fields,"data_freshness":str(freshness) if freshness is not None else None,"notes":f"Public ArcGIS source discovered; live validation pending; source quality={quality}","extra":{"arcgis_layer_url":layer_url,"discovery_source":cfg.get("discovery_source"),"discovery_score":cfg.get("discovery_score"),"field_count":len(fields),"source_quality":quality,"source_quality_score":cfg.get("source_quality_score",0),"useful_field_count":cfg.get("useful_field_count",0),"missing_useful_fields":cfg.get("missing_useful_fields",[]),"source_last_modified":freshness,"statewide_source_hint":statewide_by_id.get(cid,{}).get("source_url")}}
            if persist: update_county(cid,**patch)
            found+=1;results.append({"county_id":cid,"status":"discovered","url":layer_url,"field_count":len(fields),"discovery_score":cfg.get("discovery_score"),"source_quality":quality,"source_quality_score":cfg.get("source_quality_score",0),"source_last_modified":freshness,"statewide_hint":cid in statewide_by_id,"registry_patch":patch})
        except Exception as exc: results.append({"county_id":cid,"status":"error","error":str(exc)[:300],"statewide_hint":cid in statewide_by_id})
    response={"attempted":len(batch),"found":found,"statewide_queued":len(statewide),"results":results,"persisted":bool(persist)}
    if statewide_error: response["statewide_error"]=statewide_error
    return response


def run_statewide_batch(states: Optional[Iterable[str]] = None, discovery_limit: int = 25, etl_limit: int = 5, max_records: int = 5000, mode: str = "dry_run") -> Dict[str, Any]:
    ensure_national_counties(); snapshot = _statewide_snapshot(states); queue = snapshot["queue"]
    wanted = {str(state).strip().lower() for state in states} if states else None
    queued = [row for row in queue if not wanted or str(row.get("state") or "").strip().lower() in wanted]
    persist = str(mode).lower() != "dry_run"
    discovery = discover_and_register(limit=_limit(discovery_limit), states=states, statewide_queue=queued, persist=persist)
    refreshed = {str(row.get("county_id")): row for row in list_counties()}
    if not persist:
        for result in discovery.get("results", []):
            cid=result.get("county_id"); patch=result.get("registry_patch")
            if cid in refreshed and isinstance(patch, dict):
                refreshed[cid]=dict(refreshed[cid]); refreshed[cid].update({k:v for k,v in patch.items() if k != "extra"}); refreshed[cid].update(patch.get("extra") or {})
    coverage = build_statewide_coverage_report(snapshot["reconciled"], snapshot["census"].values(), refreshed.values(), states=states)
    # Discovery is deliberately not ETL authorization. A newly discovered source
    # must pass live validation first; only validation_status=valid can enter ETL.
    targets = [row for row in refreshed.values()
               if (not wanted or str(row.get('state') or '').strip().lower() in wanted)
               and not authorization_error(row, county_config(row['county_id'], row))]
    targets.sort(key=lambda row: (str(row.get("state_fips") or ""), str(row.get("county_fips") or ""), str(row.get("county_id") or "")))
    etl_results=[]
    for county in targets[:_limit(etl_limit,5)]:
        try: etl_results.append(run_county(county["county_id"],mode=mode,dry_run=not persist,max_records=max(1,min(int(max_records),5000))))
        except Exception as exc: etl_results.append({"county_id":county["county_id"],"status":"error","error":str(exc)[:300]})
    return {"states":sorted(wanted) if wanted else None,"statewide_queued":len(queued),"coverage":coverage,"discovery":discovery,"etl":{"attempted":len(etl_results),"ok":sum(1 for result in etl_results if result.get("status") == "ok"),"results":etl_results}}


def run_national_batch(limit:int=10,max_records:int=5000,mode:str="publish")->Dict[str,Any]:
    candidates=[c for c in list_counties() if not authorization_error(c, county_config(c["county_id"], c))]
    candidates.sort(key=lambda c:(c.get("last_successful_run") is not None,c.get("last_successful_run") or "",c.get("state",""),c.get("county_name","")))
    results=[]
    for county in candidates[:_limit(limit,10)]:
        try: results.append(run_county(county["county_id"],mode=mode,max_records=max(1,min(int(max_records),5000))))
        except Exception as exc: results.append({"county_id":county["county_id"],"status":"error","counts":{},"error":str(exc)[:300]})
    return {"attempted":len(results),"ok":sum(1 for r in results if r.get("status") == "ok"),"results":results}
