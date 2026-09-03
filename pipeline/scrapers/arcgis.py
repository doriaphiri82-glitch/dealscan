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
    """Locate a parcel layer URL inside an ArcGIS service.

    Returns the full layer endpoint, e.g.
    {root}/arcgis/rest/services/{folder}/{service}/MapServer/0
    """
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
    # fall back to first layer
    if layers:
        return f"{base}/{folder}/{service}/MapServer/{layers[0].get('id')}"
    return None


def find_layer_via_hub(hub_root: str,
                       keywords: List[str]) -> Optional[str]:
    """Discover a parcel feature layer via an ArcGIS Hub opendata site.

    Hub subdomains (e.g. gis-cochise.opendata.arcgis.com) are NOT REST roots;
    their datasets are listed in the DCAT-US 1.1 feed, whose distributions
    link the underlying ArcGIS REST services.

    Returns a full layer URL (MapServer/{id} or FeatureServer/{id}).
    """
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
                    # prefer explicit layer endpoints
                    if cand.split("/")[-1].isdigit():
                        return cand
                    best = best or cand
    return best


def query_layer(layer_url: str, where: str, out_fields: List[str],
                max_records: int = 5000,
                page_size: int = 1000) -> Iterator[Dict[str, Any]]:
    """Query a layer with pagination. Yields raw attribute dicts."""
    offset = 0
    fields = ",".join(out_fields) if out_fields else "*"
    while offset < max_records:
        payload = {
            "where": where,
            "outFields": fields,
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        r = post_json(f"{layer_url}/query", payload)
        if not r.ok or not isinstance(r.body, dict):
            return
        feats = r.body.get("features") or []
        if r.body.get("exceededTransferLimit") and not feats:
            return
        for f in feats:
            attrs = f.get("attributes") or {}
            if attrs:
                yield attrs
        got = len(feats)
        if got < page_size:
            return
        offset += got


def map_attributes(attrs: Dict[str, Any], field_map: Dict[str, str],
                   county_id: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Map raw ArcGIS attributes to the pipeline Property dict shape.

    field_map: pipeline field -> source field name (or dotted path).
    """
    def get(src_field: str) -> Any:
        if "." in src_field:
            cur: Any = attrs
            for part in src_field.split("."):
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
    out["tax_delinquent_years"] = _to_int(out.get("tax_delinquent_years"))
    out["year_acquired"] = _to_int(out.get("year_acquired"))
    out["latitude"] = _to_float(out.get("latitude"))
    out["longitude"] = _to_float(out.get("longitude"))
    out["county_id"] = county_id
    return out


def is_vacant_residential(prop: Dict[str, Any], county_id: str) -> bool:
    """Filter heuristic: vacant land parcels. County-specific land-use codes
    can be extended via counties.py `vacant_land_use_codes`."""
    lu = str(prop.get("land_use") or "").lower()
    imp = prop.get("has_improvements")
    if imp is False or imp in (0, "0", "N", "No", None):
        return True
    return "vacant" in lu or "vacant" in str(prop.get("zoning") or "").lower()


def export_snapshot(props: List[Dict[str, Any]], path: str) -> str:
    """Write a normalized parcel snapshot (artifact for review/debug)."""
    os_dir = path.rsplit("/", 1)[0] if "/" in path else "."
    import os
    os.makedirs(os_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"count": len(props), "properties": props}, f, indent=1)
    return path
