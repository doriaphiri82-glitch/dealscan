"""
DealScan - CLI commands for county management.

Commands:
  probe-all      Probe all configured county sources
  expand         Generate priority expansion report
  health         Show county health dashboard
  counties       List configured counties
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from scrapers.counties import COUNTY_SCRAPERS
from config.counties.national_registry import ensure_pilot_counties, PILOT_COUNTIES
from config.counties.registry import (
    county_summary,
    list_counties,
    get_county,
    register_county,
)
from discovery.source_discovery import probe_county_sources, discover_sources
from monitoring.health import build_national_dashboard, health_status_symbol


def _registry_status_display() -> None:
    ensure_pilot_counties()
    summary = county_summary()
    print(f"\nDealScan County Registry")
    print(f"Total counties: {summary['total']}")
    if summary.get("by_state"):
        print("By state:")
        for state, count in sorted(summary["by_state"].items()):
            print(f"  {state}: {count}")
    if summary.get("by_coverage_status"):
        print("By coverage tier:")
        for tier, count in sorted(summary["by_coverage_status"].items()):
            print(f"  {tier}: {count}")


def _probe_all_display() -> None:
    ensure_pilot_counties()
    print("\nProbing county data sources...\n")
    results = []
    for county_id, cfg in COUNTY_SCRAPERS.items():
        county_results = probe_county_sources(county_id, cfg)
        results.extend(county_results)
        for r in county_results:
            symbol = "✅" if r["reachable"] else "❌"
            print(f"  {symbol} {county_id:12} {r['source_type']:20} "
                  f"{r['url'][:60]}")
            if r.get("detail"):
                print(f"      detail: {r['detail'][:100]}")
            if r.get("error"):
                print(f"      error: {r['error'][:100]}")

    return {"attempted":len(results),"ok":sum(bool(r["reachable"]) for r in results),"scope":"source_probe_not_authorization"}


def _health_display() -> None:
    ensure_pilot_counties()
    from runregistry import load_registry
    registry = load_registry()
    from config.counties.registry import _load_registry
    recent_runs = registry.get("runs", [])
    dashboard = build_national_dashboard(
        _load_registry(),
        recent_runs,
    )
    print(f"\nDealScan Coverage Dashboard")
    print(f"Generated: {dashboard['generated_at']}")
    print(f"\nConfigured registry summary (not national live coverage)")
    print(f"  Total counties: {dashboard['total_counties']}")
    cov = dashboard.get("coverage_summary", {})
    print(f"  Active: {cov.get('active', 0)}")
    print(f"  Degraded: {cov.get('degraded', 0)}")
    print(f"  Failed: {cov.get('failed', 0)}")
    print(f"  Not implemented: {cov.get('not_implemented', 0)}")
    print(f"  Skipped: {cov.get('skipped', 0)}")
    print(f"\nCounty Details")
    for c in dashboard.get("counties", []):
        print(f"  {c.get('symbol', '⚪')} {c.get('county_name', c['county_id']):30} "
              f"{c.get('state', ''):15} {c.get('status', '')}")
        if c.get("rejection_reasons"):
            print(f"      rejection reasons: {c['rejection_reasons']}")


def _expand_display() -> None:
    ensure_pilot_counties()
    print("\nDealScan County Expansion Planner")
    print("This command generates a prioritized expansion report.")
    print("For full prioritization, integrate with the state/county priority scorer.")
    existing = set(COUNTY_SCRAPERS.keys())
    registry_counties = list_counties()
    print(f"\nCurrently configured: {len(existing)}")
    print(f"In registry: {len(registry_counties)}")
    print("\nSuggested next steps:")
    print("  1. Use discovery/source_discovery.py to probe candidate counties")
    print("  2. Add discovered counties to pipeline/config/counties/national_registry.py")
    print("  3. Run --validate-live 1 --county COUNTY_ID, then review authority evidence")
    print("  4. Authorize the exact reviewed source before any bounded ingestion")


def add_county_commands(subparsers: argparse._SubParsersAction) -> None:
    probe_parser = subparsers.add_parser("probe-all", help="Probe all county sources")
    probe_parser.set_defaults(func=_probe_all_display)

    health_parser = subparsers.add_parser("health", help="Show county health dashboard")
    health_parser.set_defaults(func=_health_display)

    expand_parser = subparsers.add_parser("expand", help="Generate expansion report")
    expand_parser.set_defaults(func=_expand_display)

    counties_parser = subparsers.add_parser("counties", help="List configured counties")
    counties_parser.set_defaults(func=_registry_status_display)
