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
import re
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


def layer_metadata(layer_url: str, *, live: bool = False) -> Dict[str, Any]:
    r = fetch(f"{layer_url.rstrip('/')}?f=json", ttl=0 if live else 3600, as_json=True, respect_robots=False)
    if not r.ok or not isinstance(r.body, dict) or r.body.get('error'):
        raise RuntimeError('ArcGIS layer metadata unavailable')
    return r.body


def layer_fields(layer_url: str) -> Optional[List[str]]:
    try:
        return [field['name'] for field in layer_metadata(layer_url).get('fields', []) if field.get('name')]
    except RuntimeError:
        return None


def object_id_field(metadata: dict) -> str:
    fields=[field for field in metadata.get('fields',[]) if isinstance(field,dict) and isinstance(field.get('name'),str)]
    declared=metadata.get('objectIdField')
    if isinstance(declared,str) and declared:
        matches=[field['name'] for field in fields if field['name'].casefold()==declared.casefold()]
        return matches[0] if len(matches)==1 else ''
    candidates=[field['name'] for field in fields if field.get('type')=='esriFieldTypeOID']
    return candidates[0] if len(candidates)==1 else ''


def _oid_number(value) -> int | None:
    if type(value) is int: result=value
    elif isinstance(value,str) and re.fullmatch(r'[0-9]+',value): result=int(value)
    else: return None
    return result if 0<=result<=2**63-1 else None


def query_count(layer_url: str, where: str = '1=1') -> int:
    response = post_json(layer_url.rstrip('/') + '/query', {'f': 'json', 'where': where, 'returnCountOnly': 'true'})
    if not response.ok or not isinstance(response.body, dict) or response.body.get('error'):
        raise RuntimeError('ArcGIS count query failed')
    count = response.body.get('count')
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise RuntimeError('ArcGIS count query returned an invalid count')
    return count


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
    actual = {str(name).strip().casefold(): name for name in source_fields
              if name not in (None, "")}

    if len(actual)!=len([name for name in source_fields if name not in (None,'')]):
        raise ValueError('Ambiguous source field casing')

    def resolve(value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [resolve(part) for part in value]
        if not isinstance(value, str) or not value:
            return value
        return actual.get(value.strip().casefold(), value)

    return {pipeline_field: resolve(src_field)
            for pipeline_field, src_field in field_map.items()}


def query_layer(layer_url: str, where: str, out_fields: List[str],
                max_records: int = 5000, page_size: int = 1000,
                *, metadata: Optional[dict] = None, diagnostics: Optional[dict] = None) -> Iterator[Dict[str, Any]]:
    """Stable OID pagination shared by live validation and ETL.

    Never mistake a service-imposed page cap for exhaustion, accept a repeated
    page, or exceed a caller's bound. Unsupported pagination is quarantined.
    """
    if type(max_records) is not int or type(page_size) is not int or not 0<=max_records<=5000 or page_size<=0:
        raise ValueError('Invalid ArcGIS record or page bound')
    if max_records==0: return
    meta = metadata if metadata is not None else layer_metadata(layer_url)
    oid = object_id_field(meta)
    capabilities = meta.get('advancedQueryCapabilities') or {}
    if not oid or capabilities.get('supportsPagination') is not True or capabilities.get('supportsOrderBy') is not True:
        raise RuntimeError('ArcGIS source does not support verified ordered pagination')
    limit = meta.get('maxRecordCount')
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise RuntimeError('ArcGIS source has no valid record limit')
    size = min(page_size, limit, 1000)
    fields = list(dict.fromkeys([*out_fields, oid]))
    offset = 0
    seen = set()
    previous = None
    if diagnostics is not None:
        diagnostics.update(pages=0, record_limit=limit, object_id_field=oid)
    while offset < max_records:
        requested = min(size, max_records - offset)
        payload = {'where': where, 'outFields': ','.join(fields) if out_fields else '*',
                   'returnGeometry': 'false', 'f': 'json', 'orderByFields': f'{oid} ASC',
                   'resultOffset': offset, 'resultRecordCount': requested}
        response = post_json(layer_url.rstrip('/') + '/query', payload)
        if not response.ok:
            raise RuntimeError('ArcGIS query request failed')
        body = response.body
        if not isinstance(body, dict) or body.get('error'):
            raise RuntimeError('ArcGIS query returned an API error or invalid response')
        features = body.get('features')
        if not isinstance(features, list):
            raise RuntimeError('ArcGIS query did not return a features array')
        if len(features) > requested:
            raise RuntimeError('ArcGIS source ignored the requested record limit')
        if diagnostics is not None:
            diagnostics['pages'] += 1
        if not features:
            if body.get('exceededTransferLimit'):
                raise RuntimeError('ArcGIS pagination made no progress')
            return
        for feature in features:
            attrs = feature.get('attributes') if isinstance(feature, dict) else None
            numeric_id=_oid_number(attrs.get(oid)) if isinstance(attrs,dict) else None
            if numeric_id is None:
                # Reject this one malformed source record in the adapter, while
                # keeping valid siblings and the raw payload available for audit.
                yield {'_malformed_feature': feature}
                continue
            identity = numeric_id
            if identity in seen:
                raise RuntimeError('ArcGIS pagination repeated an object ID')
            if previous is not None and identity<=previous:
                raise RuntimeError('ArcGIS source ignored ordered object-ID pagination')
            seen.add(identity)
            previous=identity
            yield attrs
        offset += len(features)
        if body.get('exceededTransferLimit') is False:
            return
        if len(features) < requested and not body.get('exceededTransferLimit'):
            return


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
