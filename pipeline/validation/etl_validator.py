"""Deterministic preflight validation for county ETL configurations.

This module validates configuration and sampled records without changing county
coverage state. Network probing is deliberately optional so CI remains offline.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


REQUIRED_PROPERTY_FIELDS = ("apn", "address", "lot_size_acres", "market_value", "owner_name")
NUMERIC_FIELDS = ("lot_size_acres", "assessed_value", "market_value", "tax_amount", "improvement_value", "latitude", "longitude")


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _numeric(value: Any) -> bool:
    if value in (None, "", " "):
        return True
    try:
        float(str(value).replace(",", "").replace("$", ""))
        return True
    except (TypeError, ValueError):
        return False


def validate_county_config(county_id: str, cfg: Mapping[str, Any], source_fields: Optional[Iterable[str]] = None, sample_records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Return a machine-readable ETL preflight report.

    A valid report means the configured source and mapping are internally
    coherent. It does not mean the county has successfully completed ETL.
    """
    errors: List[str] = []
    warnings: List[str] = []
    fields = dict(cfg.get("fields") or {})

    if not county_id:
        errors.append("county_id is required")
    if not (cfg.get("arcgis_layer_url") or cfg.get("arcgis_root") or cfg.get("data_url") or cfg.get("parcel_source_url")):
        errors.append("no parcel source configured")

    if cfg.get("scraper_type") in {"arcgis", "arcgis_hub", "state_parcel"} and not (cfg.get("arcgis_layer_url") or cfg.get("arcgis_root")):
        errors.append("ArcGIS scraper requires arcgis_layer_url or arcgis_root")

    missing_mapping = [f for f in REQUIRED_PROPERTY_FIELDS if f not in fields]
    if missing_mapping:
        errors.append("missing required field mappings: " + ", ".join(missing_mapping))

    mapping_values = []
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            mapping_values.extend(str(v) for v in value if _nonempty(v))
        elif _nonempty(value):
            mapping_values.append(str(value))
    duplicate_sources = sorted({v for v in mapping_values if mapping_values.count(v) > 1})
    if duplicate_sources:
        warnings.append("source fields mapped more than once: " + ", ".join(duplicate_sources[:10]))

    if source_fields is not None:
        available = {str(f).lower(): str(f) for f in source_fields if _nonempty(f)}
        missing_source_fields: List[str] = []
        for canonical, source in fields.items():
            sources = source if isinstance(source, (list, tuple)) else [source]
            for item in sources:
                if _nonempty(item) and str(item).lower() not in available:
                    missing_source_fields.append(f"{canonical}<-{item}")
        if missing_source_fields:
            errors.append("configured source fields not present in layer: " + ", ".join(missing_source_fields[:12]))

    sample = sample_records or []
    sample_checked = 0
    sample_invalid = 0
    for record in sample[:5]:
        sample_checked += 1
        issues: List[str] = []
        for field in REQUIRED_PROPERTY_FIELDS:
            source = fields.get(field)
            if not source:
                continue
            source_fields_for_value = source if isinstance(source, (list, tuple)) else [source]
            value = next((record.get(s) for s in source_fields_for_value if _nonempty(record.get(s))), None)
            if field in ("apn", "address", "owner_name") and not _nonempty(value):
                issues.append(f"{field} missing")
            if field == "lot_size_acres" and _nonempty(value) and not _numeric(value):
                issues.append("lot_size_acres not numeric")
            if field == "market_value" and _nonempty(value) and not _numeric(value):
                issues.append("market_value not numeric")
        for field in NUMERIC_FIELDS:
            source = fields.get(field)
            if not source:
                continue
            sources = source if isinstance(source, (list, tuple)) else [source]
            value = next((record.get(s) for s in sources if _nonempty(record.get(s))), None)
            if not _numeric(value):
                issues.append(f"{field} not numeric")
        if issues:
            sample_invalid += 1
            errors.extend(f"sample record: {issue}" for issue in issues)

    return {
        "valid": not errors,
        "county_id": county_id,
        "errors": errors,
        "warnings": warnings,
        "mapping_count": len(fields),
        "sample_checked": sample_checked,
        "sample_invalid": sample_invalid,
        "source_checked": source_fields is not None,
    }
