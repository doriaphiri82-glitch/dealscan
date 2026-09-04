"""
DealScan - ArcGIS FeatureServer / MapServer adapter.

Handles counties whose parcel data is exposed via ArcGIS REST.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scrapers.base import post_json
from scrapers.arcgis import layer_fields
from scrapers.adapter import BaseScraperAdapter


class ArcGISFeatureServerAdapter(BaseScraperAdapter):
    def __init__(self) -> None:
        self.last_error: Optional[str] = None

    @staticmethod
    def _out_fields(cfg: Dict[str, Any]) -> List[str]:
        configured = cfg.get("out_fields")
        if configured is None:
            configured = list((cfg.get("fields") or {}).values())
        fields: List[str] = []
        for value in configured:
            values = value if isinstance(value, (list, tuple)) else [value]
            for item in values:
                if item and str(item).strip() and str(item).strip() not in fields:
                    fields.append(str(item).strip())
        return fields

    @staticmethod
    def _resolve_field_names(cfg: Dict[str, Any], actual_fields: Optional[List[str]]) -> None:
        """Translate configured field names to the exact casing exposed by ArcGIS."""
        if not actual_fields:
            return
        lookup = {str(name).lower(): str(name) for name in actual_fields}

        def resolve(value: Any) -> Any:
            if isinstance(value, (list, tuple)):
                return [lookup.get(str(item).lower(), str(item)) for item in value]
            if not value:
                return value
            return lookup.get(str(value).lower(), str(value))

        if cfg.get("fields"):
            cfg["fields"] = {canonical: resolve(source) for canonical, source in cfg["fields"].items()}
        if cfg.get("out_fields") is not None:
            cfg["out_fields"] = [resolve(value) for value in cfg["out_fields"]]

    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        self.last_error = None
        layer_url = cfg.get("arcgis_layer_url")
        if not layer_url:
            self.last_error = "missing arcgis_layer_url"
            return []
        try:
            actual_fields = layer_fields(str(layer_url).rstrip("/"))
            if actual_fields is None:
                self.last_error = "layer metadata lookup failed or returned no metadata"
                return []
            if not actual_fields:
                self.last_error = "layer metadata contains no fields"
                return []
            self._resolve_field_names(cfg, actual_fields)
        except Exception as exc:
            self.last_error = f"layer metadata lookup failed: {exc}"
            return []
        where = cfg.get("where", "1=1")
        out_fields = self._out_fields(cfg)
        max_records = max(1, int(cfg.get("max_records", 5000)))
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
                "resultRecordCount": min(page_size, max_records - offset),
            }
            r = post_json(f"{layer_url}/query", payload)
            if not r.ok or not isinstance(r.body, dict):
                self.last_error = f"query request failed: {r.error or 'unknown error'}"
                break
            if r.body.get("error"):
                self.last_error = f"ArcGIS error: {r.body['error']}"
                break
            feats = r.body.get("features") or []
            for feature in feats:
                attrs = feature.get("attributes") or {}
                if attrs:
                    records.append(attrs)
            got = len(feats)
            if got == 0 or got < min(page_size, max_records - offset):
                break
            offset += got
        return records

    def parse(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [raw]

    def validate(self, record: Dict[str, Any]) -> bool:
        apn = record.get("apn") or record.get("PARCEL_ID") or record.get("GEO_ID")
        if not apn:
            for key in ("TAXPIN", "PARCELNO", "PARCEL_ID", "APN", "ACCOUNT", "ACCOUNT_NO", "PROP_ID"):
                apn = record.get(key)
                if apn:
                    break
        return bool(apn and str(apn).strip())

    def run(self, cfg: Dict[str, Any], max_records: int = 5000):
        result, normalized = super().run(cfg, max_records=max_records)
        if self.last_error:
            result.errors.append(f"source_error: {self.last_error}")
            result.metadata["partial_results"] = bool(normalized)
        result.metadata["source_url"] = cfg.get("arcgis_layer_url")
        return result, normalized


class ArcGISMapServerAdapter(ArcGISFeatureServerAdapter):
    pass


class ArcGISHubAdapter(ArcGISFeatureServerAdapter):
    """ArcGIS Hub sources use the same FeatureServer REST query contract."""
    pass
