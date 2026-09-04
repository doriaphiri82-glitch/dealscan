"""Controlled national source discovery and ETL batching."""
from __future__ import annotations
from typing import Any, Dict
from config.counties.national_registry import ensure_national_counties
from config.counties.registry import list_counties, update_county
from discovery.source_discovery import discover_arcgis_county_config
from runners import run as run_county


def _limit(value: int, default: int = 25) -> int:
    try:return max(1,min(int(value),250))
    except (TypeError,ValueError):return default


def discover_and_register(limit:int=25)->Dict[str,Any]:
    """Discover sources for unconfigured counties and retry previously failed discovery/validation."""
    ensure_national_counties()
    candidates=[c for c in list_counties() if c.get("coverage_status")!="tier_5" and (not c.get("arcgis_layer_url") and not c.get("parcel_source_url") or c.get("validation_status") in {"invalid","unreachable"})]
    candidates.sort(key=lambda c:(bool(c.get("arcgis_layer_url") or c.get("parcel_source_url")),c.get("state",""),c.get("county_name","")))
    results=[]; found=0
    for county in candidates[:_limit(limit)]:
        cid=county["county_id"]
        try:
            cfg=discover_arcgis_county_config(cid,county["county_name"],county["state"])
            if not cfg:results.append({"county_id":cid,"status":"not_found"});continue
            fields=cfg.get("fields",{});quality=cfg.get("source_quality","partial");freshness=cfg.get("source_last_modified")
            update_county(cid,data_source_type="arcgis",gis_url=cfg.get("arcgis_root"),parcel_source_url=cfg.get("arcgis_layer_url"),source_vendor="esri",scraper_type="arcgis",verification_status="discovered_not_verified",coverage_status="tier_1",field_mapping=fields,data_freshness=str(freshness) if freshness is not None else None,notes=f"Public ArcGIS source discovered; live validation pending; source quality={quality}",extra={"arcgis_layer_url":cfg.get("arcgis_layer_url"),"discovery_source":cfg.get("discovery_source"),"discovery_score":cfg.get("discovery_score"),"field_count":len(fields),"source_quality":quality,"source_quality_score":cfg.get("source_quality_score",0),"useful_field_count":cfg.get("useful_field_count",0),"missing_useful_fields":cfg.get("missing_useful_fields",[]),"source_last_modified":freshness})
            found+=1;results.append({"county_id":cid,"status":"discovered","url":cfg.get("arcgis_layer_url"),"field_count":len(fields),"discovery_score":cfg.get("discovery_score"),"source_quality":quality,"source_quality_score":cfg.get("source_quality_score",0),"source_last_modified":freshness})
        except Exception as exc:results.append({"county_id":cid,"status":"error","error":str(exc)[:300]})
    return {"attempted":min(len(candidates),_limit(limit)),"found":found,"results":results}


def run_national_batch(limit:int=10,max_records:int=5000,mode:str="publish")->Dict[str,Any]:
    """Run only live-validated sources; repeatable batches eventually cover every eligible county."""
    ensure_national_counties()
    candidates=[c for c in list_counties() if c.get("coverage_status")!="tier_5" and (c.get("validation_status")=="valid" or c.get("coverage_status") in {"tier_4","tier_5"}) and (c.get("arcgis_layer_url") or c.get("parcel_source_url") or c.get("arcgis_root"))]
    candidates.sort(key=lambda c:(c.get("last_successful_run") is not None,c.get("last_successful_run") or ""))
    results=[]
    for county in candidates[:_limit(limit,10)]:
        try:results.append(run_county(county["county_id"],mode=mode,max_records=max(1,min(int(max_records),10000))))
        except Exception as exc:results.append({"county_id":county["county_id"],"status":"error","counts":{},"error":str(exc)[:300]})
    return {"attempted":len(results),"ok":sum(1 for r in results if r.get("status") in ("ok","degraded")),"results":results}
