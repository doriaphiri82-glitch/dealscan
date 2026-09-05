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


def resolve_field_mapping(field_map: Dict[str, Any],
                          source_fields: Optional[List[str]]) -> Dict[str, Any]:
    """Resolve configured ArcGIS field names to the source's actual casing.

    ArcGIS schemas are frequently published with inconsistent capitalization.
    Querying the configured spelling verbatim can therefore fail even when the
    mapped field exists. Preserve nested/list mappings while resolving each
    simple source field case-insensitively.
    """
    if not source_fields:
        return dict(field_map)
    actual = {str(name).strip().lower(): name for name in source_fields
              if name not in (None, "")}

    def resolve(value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [resolve(part) for part in value]
        if not isinstance(value, str) or not value or "." in value:
            return value
        return actual.get(value.strip().lower(), value)

    return {pipeline_field: resolve(src_field)
            for pipeline_field, src_field in field_map.items()}


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
    from normalization import normalize
    return normalize(attrs, {'fields': field_map, 'county_id': county_id, 'defaults': defaults})


# Retained as a compatibility name; undocumented cross-county numeric codes
# are not vacancy evidence. Reviewed codebooks belong in source configuration.
VACANT_LAND_USE_CODES: Dict[str, List[str]] = {}


def is_vacant_residential(prop: Dict[str, Any], county_id: str) -> bool:
    from validation.vacancy import vacancy_decision
    return vacancy_decision(prop, county_id)[0]


def export_snapshot(props: List[Dict[str, Any]], path: str) -> str:
    """Write a normalized parcel snapshot (artifact for review/debug)."""
    os_dir = path.rsplit("/", 1)[0] if "/" in path else "."
    import os
    os.makedirs(os_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"count": len(props), "properties": props}, f, indent=1)
    return path
