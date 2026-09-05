"""Turn reconciled statewide discoveries into county source-work queue items."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def build_county_discovery_queue(
    reconciled: Iterable[Dict[str, Any]],
    registry: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build deterministic county discovery jobs without marking sources verified.

    Only Census-reconciled counties are queued. Existing counties that already
    have a verified/source-verified status are skipped. Duplicate county IDs
    collapse to one job, while preserving the statewide source URL as provenance.
    """
    existing = {str(row.get("county_id")): row for row in (registry or []) if row.get("county_id")}
    jobs: Dict[str, Dict[str, Any]] = {}

    for row in reconciled:
        if row.get("reconciliation_status") != "matched" or not row.get("county_id"):
            continue
        county_id = str(row["county_id"])
        current = existing.get(county_id, {})
        verification = str(current.get("verification_status") or "").lower()
        if verification in {"verified", "source_verified"}:
            continue
        if county_id in jobs:
            continue
        jobs[county_id] = {
            "county_id": county_id,
            "county_name": row.get("county_name"),
            "state": row.get("state"),
            "state_fips": row.get("state_fips"),
            "county_fips": row.get("county_fips"),
            "geoid": row.get("geoid"),
            "source_url": row.get("source_url"),
            "source_type": row.get("source_type"),
            "discovery_status": "DISCOVERED_NOT_VERIFIED",
            "verified": False,
            "next_step": "discover_arcgis_county_config",
        }
    return sorted(jobs.values(), key=lambda row: (str(row.get("state_fips") or ""), str(row.get("county_fips") or ""), str(row.get("county_id"))))
