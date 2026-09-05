"""Live source validation for national county rollout."""
from __future__ import annotations
from typing import Any, Dict, List
from config.counties.registry import list_counties, update_county, mark_county_validation
from config.counties.national_registry import PILOT_COUNTIES
from scrapers import arcgis
from scrapers.counties import COUNTY_SCRAPERS
from validation.etl_validator import validate_county_config

_AUTHORITATIVE_PILOT_SOURCE_KEYS=("arcgis_layer_url","arcgis_root","gis_url","parcel_source_url","data_source_type","source_vendor","scraper_type")

def _config(county: Dict[str, Any]) -> Dict[str, Any]:
    cid=county["county_id"]; cfg=dict(COUNTY_SCRAPERS.get(cid) or {}); pilot=PILOT_COUNTIES.get(cid)
    if pilot:
        for key in _AUTHORITATIVE_PILOT_SOURCE_KEYS:
            value=pilot.get(key)
            if value is not None: cfg[key]=value
        if pilot.get("arcgis_layer_url"):
            cfg["arcgis_root"]=pilot["arcgis_layer_url"]
            cfg["data_mode"]="arcgis"; cfg["scraper_type"]="arcgis"
    if not cfg:
        cfg=dict(pilot or county); cfg["fields"]=county.get("field_mapping") or cfg.get("fields") or {}
    cfg.setdefault("arcgis_root",county.get("gis_url")); cfg.setdefault("arcgis_layer_url",county.get("arcgis_layer_url")); cfg.setdefault("parcel_source_url",county.get("parcel_source_url")); cfg.setdefault("scraper_type",county.get("scraper_type")); cfg.setdefault("fields",county.get("field_mapping") or {})
    return cfg

def _resolve_layer(cfg: Dict[str, Any]) -> str:
    if cfg.get("arcgis_layer_url"): return str(cfg["arcgis_layer_url"]).rstrip("/")
    root=cfg.get("arcgis_root") or cfg.get("gis_url")
    if root and "opendata.arcgis.com" in str(root):
        layer=arcgis.find_layer_via_hub(str(root),["parcel","ownership","tax parcel","cadastral"])
        if layer:return layer.rstrip("/")
    return ""

def _resolve_mapping_to_source_case(fields: Dict[str, Any], source_fields: List[str]) -> Dict[str, Any]:
    lookup={str(name).lower():str(name) for name in source_fields}
    def resolve(value: Any)->Any:
        if isinstance(value,(list,tuple)):return [lookup.get(str(item).lower(),str(item)) for item in value]
        return lookup.get(str(value).lower(),str(value)) if value else value
    return {canonical:resolve(source) for canonical,source in fields.items()}

def validate_county_live(county: Dict[str, Any]) -> Dict[str, Any]:
    cid=county["county_id"]; cfg=_config(county); layer=_resolve_layer(cfg)
    if not layer:
        result={"county_id":cid,"status":"unreachable","errors":["no resolvable ArcGIS parcel layer"],"warnings":[]}; mark_county_validation(cid,status="unreachable",errors=result["errors"]); return result
    try:
        source_fields=arcgis.layer_fields(layer)
        if not source_fields: raise RuntimeError("layer metadata returned no fields")
        cfg["arcgis_layer_url"]=layer; cfg["fields"]=_resolve_mapping_to_source_case(cfg.get("fields") or {},source_fields); mapped=cfg.get("fields") or {}; out_fields=[]
        for value in mapped.values(): out_fields.extend(str(v) for v in (value if isinstance(value,(list,tuple)) else [value]) if v)
        if not out_fields: raise RuntimeError("no configured mapping fields exist in live layer")
        sample=list(arcgis.query_layer(layer,"1=1",list(dict.fromkeys(out_fields)),max_records=5,page_size=5)); report=validate_county_config(cid,cfg,source_fields=source_fields,sample_records=sample)
        if not sample: report["valid"]=False; report["errors"].append("live layer returned no sample records")
        status="valid" if report["valid"] else "invalid"; mark_county_validation(cid,status=status,errors=report["errors"],warnings=report["warnings"],source_fields_checked=True,sample_checked=report["sample_checked"]); update_county(cid,arcgis_layer_url=layer,parcel_source_url=layer,verification_status="source_verified" if report["valid"] else "discovered_not_verified",field_mapping=cfg.get("fields") or {})
        return {"county_id":cid,"status":status,"layer":layer,"field_count":len(source_fields),"sample_count":len(sample),"errors":report["errors"],"warnings":report["warnings"]}
    except Exception as exc:
        error=str(exc)[:300]; mark_county_validation(cid,status="unreachable",errors=[error],source_fields_checked=False); return {"county_id":cid,"status":"unreachable","layer":layer,"errors":[error],"warnings":[]}

def validate_live_batch(limit:int=25,include_validated:bool=False)->Dict[str,Any]:
    counties=[c for c in list_counties() if c.get("arcgis_layer_url") or c.get("parcel_source_url") or c.get("gis_url")]
    if not include_validated:
        unvalidated=[c for c in counties if not c.get("last_validated_at")]; validated=[c for c in counties if c.get("last_validated_at")]; unvalidated.sort(key=lambda c:(c.get("state",""),c.get("county_name",""))); validated.sort(key=lambda c:c.get("last_validated_at") or ""); counties=unvalidated+validated
    batch=counties[:max(1,min(int(limit),100))]; results=[validate_county_live(c) for c in batch]
    return {"attempted":len(results),"valid":sum(r.get("status")=="valid" for r in results),"invalid":sum(r.get("status")=="invalid" for r in results),"unreachable":sum(r.get("status")=="unreachable" for r in results),"results":results}
