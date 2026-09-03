"""
DealScan - Admin coverage dashboard API route.

Returns JSON with national county coverage statistics.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from pipeline.dashboard.data import build_dashboard_payload

router = APIRouter()


@router.get("/api/admin/coverage")
async def coverage_api() -> JSONResponse:
    payload = build_dashboard_payload()
    return JSONResponse(payload)
