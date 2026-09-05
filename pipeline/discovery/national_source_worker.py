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
from runners import run as run_county


def _limit(value:int,default:int=25)->int:
    try:return max(1,min(int(value),250))
    except (TypeError,ValueError):return default


def _statewide_queue(states: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """Enumerate configured statewide ArcGIS sources and reconcile to Census."""
    census = ensure_national_counties()
    wanted = {str(state).strip().lower() for state in states} if states else None
    candidates: List[Dict[str, Any]] = []
    for source in all_statewide_sources():
        if source.source_type != "arcgis_layer":
            continue
        if wanted and source.state.lower() not in wanted:
            continue
        candidates.extend(enumerate_statewide_counties(source.state))
    reconciled = reconcile_enumerated_statewide_counties(candidates, census.values())
    registry = list_counties()
    return build_county_discovery_queue(reconciled, registry)


def discover_and_register(limit:int=25)->Dict[str,Any]:
    """Discover sources fairly, prioritizing authoritative statewide enumeration."""
    ensure_national_counties()
    statewide = _statewide_queue()
    queued_ids = {row["county_id"] for row in statewide}
    candidates=[c for c in list_counties() if c.get("coverage_status")!="tier_5" and ((not c.get("arcgis_layer_url") and not c.get("parcel_source_url")) or c.get("validation_status") in {"invalid","unreachable"})]
    candidates.sort(key=lambda c:(c.get("discovery_attempted_at") is not None,c.get("discovery_attempted_at") or "",c.get("state",""),c.get("county_name","")))
    statewide_by_id = {row["county_id"]: row for row in statewide}
    prioritized = [c for c in candidates if c.get("county_id") in queued_ids]
    fallback = [c for c in candidates if c.get("county_id") not in queued_ids]
    batch=(prioritized + fallback)[:_limit(limit)]
    results=[];found=0
    for county in batch:
        cid=county["county_id"]; attempted_at=datetime.now(timezone.utc).isoformat(); update_county(cid,discovery_attempted_at=attempted_at)
        try:
            cfg=discover_arcgis_county_config(cid,county["county_name"],county["state"])
            if not cfg:
                results.append({"county_id":cid,"status":"not_found","statewide_hint":cid in statewide_by_id});continue
            fields=cfg.get("fields",{});quality=cfg.get("source_quality","partial");freshness=cfg.get("source_last_modified")
            update_county(cid,data_source_type="arcgis",gis_url=cfg.get("arcgis_root"),parcel_source_url=cfg.get("arcgis_layer_url"),source_vendor="esri",scraper_type="arcgis",verification_status="discovered_not_verified",coverage_status="tier_1",field_mapping=fields,data_freshness=str(freshness) if freshness is not None else None,notes=f"Public ArcGIS source discovered; live validation pending; source quality={quality}",extra={"arcgis_layer_url":cfg.get("arcgis_layer_url"),"discovery_source":cfg.get("discovery_source"),"discovery_score":cfg.get("discovery_score"),"field_count":len(fields),"source_quality":quality,"source_quality_score":cfg.get("source_quality_score",0),"useful_field_count":cfg.get("useful_field_count",0),"missing_useful_fields":cfg.get("missing_useful_fields",[]),"source_last_modified":freshness,"statewide_source_hint":statewide_by_id.get(cid,{}).get("source_url")})
            found+=1;results.append({"county_id":cid,"status":"discovered","url":cfg.get("arcgis_layer_url"),"field_count":len(fields),"discovery_score":cfg.get("discovery_score"),"source_quality":quality,"source_quality_score":cfg.get("source_quality_score",0),"source_last_modified":freshness,"statewide_hint":cid in statewide_by_id})
        except Exception as exc:results.append({"county_id":cid,"status":"error","error":str(exc)[:300],"statewide_hint":cid in statewide_by_id})
    return {"attempted":len(batch),"found":found,"statewide_queued":len(statewide),"results":results}


def run_national_batch(limit:int=10,max_records:int=5000,mode:str="publish")->Dict[str,Any]:
    """Run live-validated counties in oldest-success-first rotation, including published counties."""
    ensure_national_counties()
    candidates=[c for c in list_counties() if c.get("validation_status")=="valid" and (c.get("arcgis_layer_url") or c.get("parcel_source_url") or c.get("arcgis_root"))]
    candidates.sort(key=lambda c:(c.get("last_successful_run") is not None,c.get("last_successful_run") or "",c.get("state",""),c.get("county_name","")))
    results=[]
    for county in candidates[:_limit(limit,10)]:
        try:results.append(run_county(county["county_id"],mode=mode,max_records=max(1,min(int(max_records),10000))))
        except Exception as exc:results.append({"county_id":county["county_id"],"status":"error","counts":{},"error":str(exc)[:300]})
    return {"attempted":len(results),"ok":sum(1 for r in results if r.get("status") in ("ok","degraded")),"results":results}
