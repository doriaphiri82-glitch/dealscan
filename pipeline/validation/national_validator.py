"""National validation orchestration across every registered county.

Validation is deliberately read-only: it never upgrades coverage or claims that
ETL ran. Counties without a discovered source are reported as not_started,
while counties with a source are checked for mapping/config completeness.
"""
from __future__ import annotations

from typing import Any, Dict, List

from config.counties.registry import list_counties
from config.counties.national_registry import PILOT_COUNTIES
from scrapers.counties import COUNTY_SCRAPERS
from .etl_validator import validate_county_config


_PILOT_SOURCE_KEYS = (
    "data_source_type",
    "parcel_source_url",
    "gis_url",
    "arcgis_root",
    "arcgis_layer_url",
    "source_vendor",
    "scraper_type",
)


def _config_for(county: Dict[str, Any]) -> Dict[str, Any]:
    county_id = county["county_id"]
    cfg = dict(COUNTY_SCRAPERS.get(county_id) or {})
    pilot = PILOT_COUNTIES.get(county_id)

    # Pilot source identity is authoritative. County-specific scraper configs
    # still supply field mappings and other adapter details, but cannot silently
    # replace a committed pilot endpoint with stale duplicated metadata.
    if pilot:
        for key in _PILOT_SOURCE_KEYS:
            if pilot.get(key) not in (None, ""):
                cfg[key] = pilot[key]
        if pilot.get("arcgis_layer_url"):
            # Keep the validator's root aligned with the canonical FeatureServer
            # just like the production runner, preventing endpoint drift.
            cfg["arcgis_root"] = pilot["arcgis_layer_url"]
            cfg["data_mode"] = "arcgis"
            cfg["scraper_type"] = "arcgis"

    cfg.setdefault("scraper_type", county.get("scraper_type"))
    cfg.setdefault("data_source_type", county.get("data_source_type"))
    cfg.setdefault("parcel_source_url", county.get("parcel_source_url"))
    cfg.setdefault("gis_url", county.get("gis_url"))
    cfg.setdefault("arcgis_root", county.get("gis_url"))
    cfg.setdefault("arcgis_layer_url", county.get("arcgis_layer_url"))
    cfg.setdefault("fields", county.get("field_mapping") or {})
    return cfg


def validate_all_counties() -> Dict[str, Any]:
    """Validate every county currently registered in the national universe."""
    counties = list_counties()
    results: List[Dict[str, Any]] = []
    counts = {"total": len(counties), "not_started": 0, "invalid": 0, "ready": 0, "etl_verified": 0}

    for county in sorted(counties, key=lambda c: (c.get("state", ""), c.get("county_name", ""))):
        cid = county["county_id"]
        cfg = _config_for(county)
        has_source = bool(cfg.get("arcgis_layer_url") or cfg.get("arcgis_root") or cfg.get("data_url") or cfg.get("parcel_source_url"))
        coverage = county.get("coverage_status", "tier_0")
        if coverage in {"tier_4", "tier_5"}:
            counts["etl_verified"] += 1

        if not has_source:
            counts["not_started"] += 1
            results.append({
                "county_id": cid,
                "county_name": county.get("county_name"),
                "state": county.get("state"),
                "status": "not_started",
                "coverage_status": coverage,
                "errors": ["no parcel source discovered/configured"],
                "warnings": [],
            })
            continue

        report = validate_county_config(cid, cfg)
        status = "ready" if report["valid"] else "invalid"
        counts["ready" if report["valid"] else "invalid"] += 1
        results.append({
            "county_id": cid,
            "county_name": county.get("county_name"),
            "state": county.get("state"),
            "status": status,
            "coverage_status": coverage,
            "verification_status": county.get("verification_status"),
            "errors": report["errors"],
            "warnings": report["warnings"],
            "mapping_count": report["mapping_count"],
        })

    return {"counts": counts, "results": results}
