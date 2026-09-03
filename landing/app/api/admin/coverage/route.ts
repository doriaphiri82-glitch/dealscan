"""
DealScan - Coverage dashboard API route.

Returns national county coverage statistics for the admin UI.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from pipeline.dashboard.data import build_dashboard_payload


async def get_coverage_dashboard() -> Dict[str, Any]:
    return build_dashboard_payload()
