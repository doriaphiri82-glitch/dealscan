"""Controlled national source discovery and ETL batching."""
from __future__ import annotations
from typing import Any, Dict, List
from config.counties.national_registry import ensure_national_counties
from config.counties.registry import list_counties
from discovery.source_discovery import discover_arcgis_county_config
from runners import run as run_county


def discover_and_register(limit:int=25)->Dict[str,Any]:
    """Discover public ArcGIS parcel sources for a bounded batch of uncovered counties."""
    ensure_national_counties()
    from config.counties.registry import update_county
    candidates=[c for c in list_counties() if c.get("coverage_status","tier_0") in ("tier_0","tier_1","not_covered") and not c.get("arcgis_layer_url")]
    results=[]; found=0
    for county in candidates[:max(0,int(limit))]:
        cid=county["county_id"]
        try:
            cfg=discover_arcgis_county_config(cid,county["county_name"],county["state"])
            if not cfg:
                results.append({"county_id":cid,"status":"not_found"}); continue
            update_county(cid,data_source_type="arcgis",gis_url=cfg.get("arcgis_root"),parcel_source_url=cfg.get("arcgis_layer_url"),source_vendor="esri",scraper_type="arcgis",verification_status="discovered_not_verified",coverage_status="tier_1",field_mapping=cfg.get("fields",{}),notes="Public ArcGIS source discovered; ETL verification pending",extra={"arcgis_layer_url":cfg.get("arcgis_layer_url"),"discovery_source":cfg.get("discovery_source"),"discovery_score":cfg.get("discovery_score")})
            found+=1; results.append({"county_id":cid,"status":"discovered","url":cfg.get("arcgis_layer_url"),"field_count":len(cfg.get("fields",{}))})
        except Exception as exc:
            results.append({"county_id":cid,"status":"error","error":str(exc)[:300]})
    return {"attempted":min(len(candidates),max(0,int(limit))),"found":found,"results":results}


def run_national_batch(limit:int=10,max_records:int=5000,mode:str="publish")->Dict[str,Any]:
    """Run discovered counties through the real ETL pipeline in a resumable batch."""
    ensure_national_counties()
    counties=list_counties()
    eligible=[c for c in counties if c.get("arcgis_layer_url") and c.get("coverage_status") not in ("tier_5",)]
    results=[]
    for county in eligible[:max(0,int(limit))]:
        results.append(run_county(county["county_id"],mode=mode,max_records=max_records))
    return {"attempted":len(results),"ok":sum(1 for r in results if r.get("status") in ("ok","degraded")),"results":results}
