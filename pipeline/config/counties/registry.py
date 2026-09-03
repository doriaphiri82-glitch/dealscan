"""
DealScan - National County Registry

Structured county definitions using FIPS/GEOID as stable identifiers.
The Census Bureau is treated as the authoritative geography reference.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# Registry file lives alongside county definition files
REGISTRY_DIR = os.path.dirname(__file__)
REGISTRY_PATH = os.path.join(REGISTRY_DIR, "registry.json")


def _load_registry() -> Dict[str, Any]:
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"counties": {}, "meta": {"total": 0, "by_state": {}}}


def _save_registry(reg: Dict[str, Any]) -> None:
    os.makedirs(REGISTRY_DIR, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)


def register_county(
    county_id: str,
    county_name: str,
    state: str,
    state_fips: str,
    county_fips: str,
    geoid: str,
    population: Optional[int] = None,
    data_source_type: Optional[str] = None,
    assessor_url: Optional[str] = None,
    gis_url: Optional[str] = None,
    parcel_source_url: Optional[str] = None,
    tax_source_url: Optional[str] = None,
    delinquent_tax_source_url: Optional[str] = None,
    zoning_source_url: Optional[str] = None,
    source_vendor: Optional[str] = None,
    scraper_type: Optional[str] = None,
    verification_status: str = "not_implemented",
    coverage_status: str = "tier_0",
    last_successful_run: Optional[str] = None,
    last_record_count: Optional[int] = None,
    data_freshness: Optional[str] = None,
    field_mapping: Optional[Dict[str, str]] = None,
    notes: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    reg = _load_registry()
    counties = reg.setdefault("counties", {})
    entry: Dict[str, Any] = {
        "county_id": county_id,
        "county_name": county_name,
        "state": state,
        "state_fips": state_fips,
        "county_fips": county_fips,
        "geoid": geoid,
        "population": population,
        "data_source_type": data_source_type,
        "assessor_url": assessor_url,
        "gis_url": gis_url,
        "parcel_source_url": parcel_source_url,
        "tax_source_url": tax_source_url,
        "delinquent_tax_source_url": delinquent_tax_source_url,
        "zoning_source_url": zoning_source_url,
        "source_vendor": source_vendor,
        "scraper_type": scraper_type,
        "verification_status": verification_status,
        "coverage_status": coverage_status,
        "last_successful_run": last_successful_run,
        "last_record_count": last_record_count,
        "data_freshness": data_freshness,
        "field_mapping": field_mapping or {},
        "notes": notes or "",
    }
    if extra:
        entry.update(extra)
    counties[county_id] = entry
    reg["meta"]["total"] = len(counties)
    by_state = reg.setdefault("meta", {}).setdefault("by_state", {})
    by_state[state] = by_state.get(state, 0) + 1
    _save_registry(reg)
    return entry


def get_county(county_id: str) -> Optional[Dict[str, Any]]:
    reg = _load_registry()
    return reg.get("counties", {}).get(county_id)


def list_counties(state: Optional[str] = None) -> List[Dict[str, Any]]:
    reg = _load_registry()
    counties = list(reg.get("counties", {}).values())
    if state:
        counties = [c for c in counties if c.get("state") == state]
    return counties


def update_county(county_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    reg = _load_registry()
    counties = reg.get("counties", {})
    entry = counties.get(county_id)
    if not entry:
        return None
    entry.update({k: v for k, v in fields.items() if v is not None})
    _save_registry(reg)
    return entry


def remove_county(county_id: str) -> bool:
    reg = _load_registry()
    counties = reg.get("counties", {})
    if county_id not in counties:
        return False
    entry = counties.pop(county_id)
    by_state = reg.get("meta", {}).get("by_state", {})
    state = entry.get("state")
    if state and by_state.get(state) is not None:
        by_state[state] = max(0, by_state[state] - 1)
        if by_state[state] == 0:
            by_state.pop(state, None)
    reg["meta"]["total"] = len(counties)
    _save_registry(reg)
    return True


def county_summary() -> Dict[str, Any]:
    reg = _load_registry()
    counties = list(reg.get("counties", {}).values())
    by_status: Dict[str, int] = {}
    by_state: Dict[str, int] = {}
    for c in counties:
        status = c.get("coverage_status", "tier_0")
        by_status[status] = by_status.get(status, 0) + 1
        state = c.get("state", "Unknown")
        by_state[state] = by_state.get(state, 0) + 1
    return {
        "total": len(counties),
        "by_coverage_status": by_status,
        "by_state": by_state,
    }
