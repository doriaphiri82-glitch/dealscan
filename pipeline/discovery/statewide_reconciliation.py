"""Reconcile statewide parcel county identifiers with the Census county universe.

Statewide parcel services are discovery accelerators. This module turns their
county identifiers into deterministic matches against the national Census
geography universe without treating a statewide hit as source verification.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


def _norm(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return re.sub(r"\s+county$", "", text).strip()


def _fips(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.isdigit():
        return text.zfill(3)
    return None


def reconcile_statewide_counties(
    statewide: Iterable[Dict[str, Any]],
    census: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Match statewide county discoveries to Census geography records.

    FIPS is authoritative when available. County names are used only as a
    constrained fallback within the same state. Every output remains a
    discovery candidate and retains its original statewide source metadata.
    """
    census_rows = list(census)
    by_state_fips = {
        (str(row.get("state_fips") or ""), _fips(row.get("county_fips"))): row
        for row in census_rows
        if row.get("state_fips") is not None and _fips(row.get("county_fips"))
    }
    by_state_name = {
        (str(row.get("state_fips") or ""), _norm(row.get("county_name"))): row
        for row in census_rows
        if row.get("state_fips") is not None and row.get("county_name")
    }

    results: List[Dict[str, Any]] = []
    for candidate in statewide:
        state_fips = str(candidate.get("state_fips") or "")
        county_fips = _fips(candidate.get("county_fips"))
        match = by_state_fips.get((state_fips, county_fips)) if county_fips else None
        match_method = "fips" if match else None

        if match is None and state_fips and candidate.get("county_name"):
            match = by_state_name.get((state_fips, _norm(candidate["county_name"])))
            match_method = "name" if match else None

        result = dict(candidate)
        result["reconciliation_status"] = "matched" if match else "unmatched"
        result["reconciliation_method"] = match_method
        if match:
            result.update(
                {
                    "county_id": match.get("county_id"),
                    "county_name": match.get("county_name") or result.get("county_name"),
                    "state": match.get("state") or result.get("state"),
                    "state_fips": match.get("state_fips") or state_fips,
                    "county_fips": match.get("county_fips") or county_fips,
                    "geoid": match.get("geoid"),
                }
            )
        results.append(result)
    return results


def build_coverage_report(
    reconciled: Iterable[Dict[str, Any]],
    census: Iterable[Dict[str, Any]],
    state_fips: Optional[str] = None,
) -> Dict[str, Any]:
    """Summarize statewide coverage against the expected Census universe.

    ``state_fips`` scopes the report when a caller supplies a national Census
    universe rather than a single state's rows.
    """
    rows = list(reconciled)
    census_rows = [
        row for row in census
        if state_fips is None or str(row.get("state_fips") or "") == str(state_fips)
    ]
    if state_fips is not None:
        rows = [row for row in rows if str(row.get("state_fips") or "") == str(state_fips)]
    matched = [row for row in rows if row.get("reconciliation_status") == "matched"]
    expected = len(census_rows)
    covered = len({row.get("geoid") for row in matched if row.get("geoid")})
    return {
        "expected_counties": expected,
        "discovered_counties": len(rows),
        "matched_counties": covered,
        "unmatched_discoveries": sum(row.get("reconciliation_status") == "unmatched" for row in rows),
        "missing_counties": max(expected - covered, 0),
        "coverage_ratio": round(covered / expected, 4) if expected else 0.0,
    }
