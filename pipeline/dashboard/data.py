"""
DealScan - Admin coverage dashboard data endpoint.

Returns JSON with national coverage stats for the admin UI.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from runregistry import load_registry
from config.counties.registry import list_counties
from monitoring.health import build_national_dashboard


def build_dashboard_payload() -> Dict[str, Any]:
    registry_counties = list_counties()
    registry = {"counties": {c["county_id"]: c for c in registry_counties}}
    recent_runs = load_registry().get("runs", [])
    return build_national_dashboard(registry, recent_runs)


if __name__ == "__main__":
    payload = build_dashboard_payload()
    print(json.dumps(payload, indent=2))
