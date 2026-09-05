"""Coverage reporting for statewide parcel discovery.

This module measures discovery against the Census county universe without
confusing statewide enumeration, source discovery, or ETL success with
verification. It is intentionally read-only and deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _state_key(row: Dict[str, Any]) -> str:
    return str(row.get("state") or "").strip().lower()


def _county_key(row: Dict[str, Any]) -> str:
    geoid = str(row.get("geoid") or "").strip()
    if geoid:
        return f"geoid:{geoid}"
    state_fips = str(row.get("state_fips") or "").strip()
    county_fips = str(row.get("county_fips") or "").strip().zfill(3)
    return f"fips:{state_fips}:{county_fips}"


def build_statewide_coverage_report(
    reconciled: Iterable[Dict[str, Any]],
    census: Iterable[Dict[str, Any]],
    registry: Optional[Iterable[Dict[str, Any]]] = None,
    states: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Return per-state expected, enumerated, discovered, and validated coverage.

    A county is considered ``source_discovered`` only when the registry has a
    parcel/source URL. It is considered ``verified`` only when the registry
    explicitly reports ``verified``/``source_verified`` or a valid validation
    status. Statewide enumeration alone never upgrades either status.
    """
    wanted = {str(state).strip().lower() for state in states} if states else None
    census_rows = [row for row in census if not wanted or _state_key(row) in wanted]
    reconciled_rows = [row for row in reconciled if not wanted or _state_key(row) in wanted]
    registry_rows = list(registry or [])
    registry_by_id = {str(row.get("county_id")): row for row in registry_rows if row.get("county_id")}

    states_seen = sorted({_state_key(row) for row in census_rows if _state_key(row)})
    reports: Dict[str, Dict[str, Any]] = {}
    for state in states_seen:
        expected_rows = [row for row in census_rows if _state_key(row) == state]
        state_discoveries = [row for row in reconciled_rows if _state_key(row) == state]
        matched = {str(row.get("geoid")) for row in state_discoveries if row.get("reconciliation_status") == "matched" and row.get("geoid")}
        matched_rows = [row for row in state_discoveries if row.get("reconciliation_status") == "matched"]

        discovered_ids = set()
        verified_ids = set()
        for row in matched_rows:
            county_id = row.get("county_id")
            registry_row = registry_by_id.get(str(county_id)) if county_id else None
            if not registry_row:
                continue
            if registry_row.get("arcgis_layer_url") or registry_row.get("parcel_source_url") or registry_row.get("gis_url"):
                discovered_ids.add(str(county_id))
            verification = str(registry_row.get("verification_status") or "").lower()
            validation = str(registry_row.get("validation_status") or "").lower()
            if verification in {"verified", "source_verified"} or validation == "valid":
                verified_ids.add(str(county_id))

        expected_keys = {_county_key(row) for row in expected_rows}
        matched_keys = {_county_key(row) for row in matched_rows}
        missing = sorted(
            (str(row.get("county_id")) if row.get("county_id") else _county_key(row))
            for row in expected_rows
            if _county_key(row) not in matched_keys
        )
        expected = len(expected_rows)
        reports[state] = {
            "expected_counties": expected,
            "enumerated_discoveries": len(state_discoveries),
            "matched_counties": len(matched),
            "source_discovered": len(discovered_ids),
            "verified": len(verified_ids),
            "missing_counties": len(missing),
            "missing_county_keys": missing,
            "enumeration_coverage_ratio": round(len(matched) / expected, 4) if expected else 0.0,
            "source_discovery_ratio": round(len(discovered_ids) / expected, 4) if expected else 0.0,
            "verified_ratio": round(len(verified_ids) / expected, 4) if expected else 0.0,
        }

    totals = {
        "expected_counties": sum(report["expected_counties"] for report in reports.values()),
        "enumerated_discoveries": sum(report["enumerated_discoveries"] for report in reports.values()),
        "matched_counties": sum(report["matched_counties"] for report in reports.values()),
        "source_discovered": sum(report["source_discovered"] for report in reports.values()),
        "verified": sum(report["verified"] for report in reports.values()),
    }
    expected = totals["expected_counties"]
    totals.update({
        "missing_counties": max(expected - totals["matched_counties"], 0),
        "enumeration_coverage_ratio": round(totals["matched_counties"] / expected, 4) if expected else 0.0,
        "source_discovery_ratio": round(totals["source_discovered"] / expected, 4) if expected else 0.0,
        "verified_ratio": round(totals["verified"] / expected, 4) if expected else 0.0,
    })
    return {"states": reports, "totals": totals}
