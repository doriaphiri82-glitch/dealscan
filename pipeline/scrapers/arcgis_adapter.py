"""
DealScan - ArcGIS FeatureServer / MapServer adapter.

Handles counties whose parcel data is exposed via ArcGIS REST.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scrapers.base import fetch, post_json
from scrapers.adapter import BaseScraperAdapter, ScrapeResult


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v not in (None, "", " ") else None
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> int:
    f = _to_float(v)
    return int(f) if f is not None else 0


class ArcGISFeatureServerAdapter(BaseScraperAdapter):
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        layer_url = cfg.get("arcgis_layer_url")
        if not layer_url:
            return []
        where = cfg.get("where", "1=1")
        out_fields = cfg.get("out_fields", [])
        max_records = int(cfg.get("max_records", 5000))
        records: List[Dict[str, Any]] = []
        offset = 0
        page_size = min(1000, max_records)
        while offset < max_records:
            payload = {
                "where": where,
                "outFields": ",".join(out_fields) if out_fields else "*",
                "returnGeometry": "false",
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": page_size,
            }
            r = post_json(f"{layer_url}/query", payload)
            if not r.ok or not isinstance(r.body, dict):
                break
            if r.body.get("error"):
                break
            feats = r.body.get("features") or []
            for f in feats:
                attrs = f.get("attributes") or {}
                if attrs:
                    records.append(attrs)
            got = len(feats)
            if got < page_size:
                break
            offset += got
        return records

    def parse(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [raw]

    def validate(self, record: Dict[str, Any]) -> bool:
        apn = record.get("apn") or record.get("PARCEL_ID") or record.get("GEO_ID")
        # County configs map source APN fields during normalize(), so accept
        # common source identifiers here as well.
        if not apn:
            for key in ("TAXPIN", "PARCELNO", "PARCEL_ID", "APN", "ACCOUNT", "ACCOUNT_NO", "PROP_ID"):
                apn = record.get(key)
                if apn:
                    break
        return bool(apn and str(apn).strip())


class ArcGISMapServerAdapter(ArcGISFeatureServerAdapter):
    pass


class ArcGISHubAdapter(BaseScraperAdapter):
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        adapter = ArcGISFeatureServerAdapter()
        return adapter.discover(cfg)

    def parse(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [raw]

    def validate(self, record: Dict[str, Any]) -> bool:
        apn = record.get("apn") or record.get("PARCEL_ID") or record.get("GEO_ID")
        for key in ("TAXPIN", "PARCELNO", "ACCOUNT", "ACCOUNT_NO", "PROP_ID"):
            if not apn:
                apn = record.get(key)
        return bool(apn and str(apn).strip())
