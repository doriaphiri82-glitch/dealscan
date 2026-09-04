"""
DealScan - ArcGIS REST adapter.

Most county GIS departments publish parcel layers via ArcGIS REST
(MapServer/FeatureServer). This is the most stable, permission-friendly
acquisition interface: structured JSON, documented query semantics, no
HTML parsing. Field names differ per county -> mapping is configured in
config.counties.COUNTIES[c]['sources']['arcgis']['fields'].
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional

from .base import fetch, post_json, probe, ProbeResult  # noqa: F401


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v not in (None, "", " ") else None
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> int:
    f = _to_float(v)
    return int(f) if f is not None else 0


def discover_services(rest_root: str) -> Optional[Dict[str, Any]]:
    """Fetch {root}/arcgis/rest/services?f=json and index folders/services."""
    url = rest_root.rstrip("/") + "/arcgis/rest/services?f=json"
    r = fetch(url, ttl=24 * 3600, as_json=True, respect_robots=False)
    if not r.ok or not isinstance(r.body, dict):
        return None
    return r.body


def find_layer(rest_root: str, folder: str, service: str,
               layer_name_keywords: List[str]) -> Optional[str]:
    """Locate a parcel layer URL inside an ArcGIS service."""
    base = rest_root.rstrip("/") + "/arcgis/rest/services"
    svc_url = f"{base}/{folder}/{service}?f=json"
    r = fetch(svc_url, ttl=24 * 3600, as_json=True, respect_robots=False)
    if not r.ok or not isinstance(r.body, dict):
        return None
    layers = r.body.get("layers") or []
    for lyr in layers:
        name = (lyr.get("name") or "").lower()
        if any(k in name for k in layer_name_keywords):
            return f"{base}/{folder}/{service}/MapServer/{lyr.get('id')}"
    if layers:
        return f"{base}/{folder}/{service}/MapServer/{layers[0].get('id')}"
    return None


def find_layer_via_hub(hub_root: str,
                       keywords: List[str]) -> Optional[str]:
    """Discover a parcel feature layer via an ArcGIS Hub DCAT feed."""
    url = hub_root.rstrip("/") + "/api/feed/dcat-us/1.1.json"
    r = fetch(url, ttl=24 * 3600, as_json=True, respect_robots=False)
    if not r.ok or not isinstance(r.body, dict):
        return None
    best: Optional[str] = None
    for ds in r.body.get("dataset") or []:
        title = str(ds.get("title") or "").lower()
        if not any(k in title for k in keywords):
            continue
        for dist in ds.get("distribution") or []:
            for key in ("accessURL", "downloadURL"):
                u = str(dist.get(key) or "")
                if "/MapServer/" in u or "/FeatureServer/" in u:
                    cand = u.rstrip("/")
                    if cand.split("/")[-1].isdigit():
                        return cand
                    best = best or cand
    return best


def layer_fields(layer_url: str) -> Optional[List[str]]:
    """Return the layer's actual field names from its metadata endpoint."""
    r = fetch(f"{layer_url}?f=json", ttl=24 * 3600, as_json=True,
              respect_robots=False)
    if not r.ok or not isinstance(r.body, dict):
        return None
    return [f.get("name") for f in r.body.get("fields") or []
            if f.get("name")]


def query_layer(layer_url: str, where: str, out_fields: List[str],
                max_records: int = 5000,
                page_size: int = 1000) -> Iterator[Dict[str, Any]]:
    """Query a layer with pagination and fail loudly on API/network errors."""
    offset = 0
    fields = ",".join(out_fields) if out_fields else "*"
    while offset < max_records:
        payload = {
            "where": where,
            "outFields": fields,
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": min(page_size, max_records - offset),
        }
        r = post_json(f"{layer_url}/query", payload)
        if not r.ok:
            raise RuntimeError(
                f"ArcGIS query request failed: {r.error or 'unknown error'}"
            )
        if not isinstance(r.body, dict):
            raise RuntimeError("ArcGIS query returned a non-object response")
        if r.body.get("error"):
            raise RuntimeError(f"ArcGIS query error: {r.body['error']}")
        feats = r.body.get("features") or []
        for f in feats:
            attrs = f.get("attributes") or {}
            if attrs:
                yield attrs
        got = len(feats)
        if got == 0 or got < min(page_size, max_records - offset):
            return
        offset += got


def map_attributes(attrs: Dict[str, Any], field_map: Dict[str, Any],
                   county_id: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Map raw ArcGIS attributes to the pipeline Property dict shape."""
    def get(src_field: Any) -> Any:
        if isinstance(src_field, (list, tuple)):
            values = [get(part) for part in src_field]
            values = [str(v).strip() for v in values if v not in (None, "") and str(v).strip()]
            return ", ".join(values) if values else None
        if not src_field:
            return None
        if "." in str(src_field):
            cur: Any = attrs
            for part in str(src_field).split("."):
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    return None
            return cur
        return attrs.get(src_field)

    out = dict(defaults)
    for pipeline_field, src_field in field_map.items():
        out[pipeline_field] = get(src_field)
    out["lot_size_acres"] = _to_float(out.get("lot_size_acres"))
    out["assessed_value"] = _to_float(out.get("assessed_value"))
    out["market_value"] = _to_float(out.get("market_value"))
    out["tax_amount"] = _to_float(out.get("tax_amount"))
    out["improvement_value"] = _to_float(out.get("improvement_value"))
    out["tax_delinquent_years"] = _to_int(out.get("tax_delinquent_years"))
    out["year_acquired"] = _to_int(out.get("year_acquired"))
    out["latitude"] = _to_float(out.get("latitude"))
    out["longitude"] = _to_float(out.get("longitude"))
    out["county_id"] = county_id
    return out


VACANT_LAND_USE_CODES = {
    "cochise_az": ["0011", "9700", "0012", "0013", "0014", "0001", "0002", "0003"],
    "mohave_az": ["0011", "9700", "VAC", "VACANT"],
    "el_paso_tx": ["0011", "9700", "VAC", "VACANT"],
    "hudson_co": ["0011", "9700", "VAC", "VACANT"],
    "socorro_nm": ["0011", "9700", "VAC", "VACANT"],
}


def is_vacant_residential(prop: Dict[str, Any], county_id: str) -> bool:
    """Return True only when the source provides a credible vacant-land signal."""
    lu = str(prop.get("land_use") or "").strip().lower()
    zoning = str(prop.get("zoning") or "").strip().lower()
    code = str(prop.get("use_code") or prop.get("land_use") or "").strip().upper()
    imp = prop.get("has_improvements")
    improvement_value = prop.get("improvement_value")
    has_imp = imp is True or imp in (1, "1", "Y", "YES", "Yes", "true", "True")
    no_imp = imp is False or imp == 0 or imp in ("0", "N", "NO", "No", "NONE", "false", "False")
    if improvement_value is not None:
        try:
            if float(improvement_value) > 0:
                has_imp = True
                no_imp = False
            elif float(improvement_value) == 0:
                no_imp = True
        except (TypeError, ValueError):
            pass

    if has_imp:
        return "vacant" in lu or "unimproved" in lu
    if no_imp:
        if "residential" in lu or "res" in zoning or "residential" in zoning:
            return True
        if "vacant" in lu or "unimproved" in lu:
            return True
        return code in {str(x).upper() for x in VACANT_LAND_USE_CODES.get(county_id, [])}
    if "vacant" in lu or "unimproved" in lu or "vacant" in zoning:
        return True
    return code in {str(x).upper() for x in VACANT_LAND_USE_CODES.get(county_id, [])}


def export_snapshot(props: List[Dict[str, Any]], path: str) -> str:
    """Write a normalized parcel snapshot (artifact for review/debug)."""
    os_dir = path.rsplit("/", 1)[0] if "/" in path else "."
    import os
    os.makedirs(os_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"count": len(props), "properties": props}, f, indent=1)
    return path
