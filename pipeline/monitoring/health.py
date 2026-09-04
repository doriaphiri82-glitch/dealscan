"""
DealScan - County health monitoring and coverage tiers.

Provides health status for every configured county and coverage dashboards.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class CountyHealth:
    county_id: str
    status: str = "not_implemented"
    coverage_tier: str = "tier_0"
    source_reachable: bool = False
    schema_changed: bool = False
    records_discovered: int = 0
    records_downloaded: int = 0
    records_parsed: int = 0
    records_normalized: int = 0
    records_rejected: int = 0
    rejection_reasons: Dict[str, int] = field(default_factory=dict)
    records_stored: int = 0
    records_scored: int = 0
    records_qualified: int = 0
    records_published: int = 0
    error_rate: float = 0.0
    last_successful_run: Optional[str] = None
    data_freshness: Optional[str] = None
    scraper_version: str = "0.1.0"


def coverage_tier_name(tier: str) -> str:
    return {
        "tier_0": "Not Researched",
        "tier_1": "Source Discovered",
        "tier_2": "Source Verified",
        "tier_3": "Scraper Implemented",
        "tier_4": "Scraper Producing Valid Records",
        "tier_5": "Scraper Producing Qualified Deals",
        "tier_6": "Production Monitored",
    }.get(tier, tier)


def health_status_symbol(status: str) -> str:
    return {
        "active": "🟢",
        "ok": "🟢",
        "degraded": "🟡",
        "failed": "🔴",
        "not_implemented": "⚪",
        "skipped": "⚪",
    }.get(status, "⚪")


def build_county_health(run_entry: Dict[str, Any]) -> CountyHealth:
    county_id = run_entry.get("county_id", "unknown")
    status = run_entry.get("status", "error")
    counts = run_entry.get("counts", {})
    health = CountyHealth(
        county_id=county_id,
        status=status,
        coverage_tier=_tier_from_status(status, counts),
        records_discovered=counts.get("discovered", counts.get("found", 0)),
        records_downloaded=counts.get("downloaded", counts.get("found", 0)),
        records_parsed=counts.get("parsed", counts.get("vacant", 0)),
        records_normalized=counts.get("normalized", counts.get("vacant", 0)),
        records_rejected=counts.get("rejected", 0),
        rejection_reasons=counts.get("rejection_reasons", {}),
        records_stored=counts.get("saved", 0),
        records_scored=counts.get("scored", counts.get("saved", 0)),
        records_qualified=counts.get("qualified", counts.get("saved", 0)),
        records_published=counts.get("published", 0),
        last_successful_run=run_entry.get("at") if status in ("ok", "degraded") else None,
        data_freshness=run_entry.get("at") if status in ("ok", "degraded") else None,
    )
    return health


def _registry_health(county: Dict[str, Any]) -> CountyHealth:
    """Build a truthful dashboard state when no run-registry entry exists."""
    validation = str(county.get("validation_status") or "").lower()
    verification = str(county.get("verification_status") or "").lower()
    coverage = str(county.get("coverage_status") or "").lower()
    stored = int(county.get("last_record_count") or 0)
    published = int(county.get("last_published_count") or 0)

    # Persisted ETL state is authoritative even if the transient run registry
    # has been pruned. Never downgrade a county to "not implemented" merely
    # because there is no recent run entry.
    if coverage == "tier_5" and stored > 0:
        tier = "tier_5"
    elif stored > 0:
        tier = "tier_4"
    elif validation == "valid" or verification in {"source_verified", "verified"}:
        tier = "tier_2"
    elif county.get("arcgis_layer_url") or county.get("parcel_source_url") or county.get("arcgis_root"):
        tier = "tier_1"
    else:
        tier = "tier_0"

    status = "active" if verification == "verified" and stored > 0 else "not_implemented"
    return CountyHealth(
        county_id=county.get("county_id", "unknown"),
        status=status,
        coverage_tier=tier,
        records_stored=stored,
        records_published=published,
        last_successful_run=county.get("last_successful_run"),
        data_freshness=county.get("data_freshness"),
    )


def _tier_from_status(status: str, counts: Dict[str, int]) -> str:
    if status == "skipped":
        return "tier_1"
    published = counts.get("published", 0)
    saved = counts.get("saved", 0)
    found = counts.get("found", counts.get("discovered", 0))
    if status == "error":
        return "tier_3"
    if published > 0:
        return "tier_6"
    if saved > 0:
        return "tier_5"
    if found > 0:
        return "tier_4"
    return "tier_3"


def build_national_dashboard(registry: Dict[str, Any],
                             recent_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    runs_by_county: Dict[str, Dict[str, Any]] = {}
    for run in recent_runs:
        cid = run.get("county_id")
        if not cid:
            continue
        prev = runs_by_county.get(cid)
        if not prev or run.get("at", "") > prev.get("at", ""):
            runs_by_county[cid] = run

    counties = list(registry.get("counties", {}).values())
    status_counts: Dict[str, int] = {}
    tier_counts: Dict[str, int] = {}
    county_healths = []
    for county in counties:
        cid = county.get("county_id", "")
        run = runs_by_county.get(cid)
        health = build_county_health(run) if run else _registry_health(county)
        status_counts[health.status] = status_counts.get(health.status, 0) + 1
        tier_counts[health.coverage_tier] = tier_counts.get(health.coverage_tier, 0) + 1
        county_healths.append({
            "county_id": cid,
            "county_name": county.get("county_name", cid),
            "state": county.get("state", ""),
            "status": health.status,
            "symbol": health_status_symbol(health.status),
            "tier": health.coverage_tier,
            "tier_name": coverage_tier_name(health.coverage_tier),
            "records": health.records_stored,
            "published": health.records_published,
            "last_run": health.last_successful_run,
            "data_freshness": health.data_freshness,
            "rejection_reasons": health.rejection_reasons,
            "validation_status": county.get("validation_status"),
            "verification_status": county.get("verification_status"),
            "registry_coverage_status": county.get("coverage_status"),
        })

    return {
        "total_counties": len(counties),
        "status_counts": status_counts,
        "tier_counts": tier_counts,
        "coverage_summary": {
            "total": len(counties),
            "total_counties": len(counties),
            "active": status_counts.get("ok", 0) + status_counts.get("active", 0),
            "degraded": status_counts.get("degraded", 0),
            "failed": status_counts.get("error", 0),
            "not_implemented": status_counts.get("not_implemented", 0),
            "skipped": status_counts.get("skipped", 0),
        },
        "counties": county_healths,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
