"""OpenAI-powered qualitative deal intelligence.

The deterministic scorer remains the source of truth for the numeric deal score.
This module adds a structured explanation, risks, strengths, and recommendation.
AI failures are intentionally non-fatal so ETL can continue without an API call.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency is optional at import time
    OpenAI = None

MODEL = os.getenv("OPENAI_DEAL_MODEL", "gpt-5.6-luna")

_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["strong_buy", "buy", "watch", "avoid"]},
        "summary": {"type": "string"},
        "why_it_stands_out": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["verdict", "summary", "why_it_stands_out", "risks", "next_steps", "risk_level", "confidence"],
    "additionalProperties": False,
}

_SYSTEM = """You are DealScan's real-estate deal analyst. Analyze vacant-land opportunities conservatively.
The deterministic DealScan score is authoritative for the numeric score; do not invent a replacement score.
Use only facts supplied in the input. Never claim zoning, access, title, utilities, comps, seller motivation,
or profitability has been verified unless the supplied evidence says so. Clearly flag estimates and missing data.
Return concise, investor-friendly language. This is decision support, not legal, tax, lending, or appraisal advice."""


def _client() -> Optional[Any]:
    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        return None
    return OpenAI()


def analyze_deal(deal: Dict[str, Any], property_data: Optional[Dict[str, Any]] = None,
                 comps: Optional[list[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """Return structured AI analysis, or None when OpenAI is not configured/available."""
    client = _client()
    if client is None:
        return None

    payload = {
        "deal": deal,
        "property": property_data or {},
        "comparable_sales": comps or [],
    }
    try:
        response = client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": json.dumps(payload, default=str)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "deal_intelligence",
                    "strict": True,
                    "schema": _SCHEMA,
                }
            },
            max_output_tokens=900,
            store=False,
        )
        return json.loads(response.output_text)
    except Exception:
        # AI enrichment must never break scraping, scoring, persistence, or delivery.
        return None


def attach_ai_analysis(deal: Dict[str, Any], property_data: Optional[Dict[str, Any]] = None,
                       comps: Optional[list[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Attach AI analysis as compact JSON in the existing notes field."""
    analysis = analyze_deal(deal, property_data, comps)
    if analysis is not None:
        deal["ai_analysis"] = analysis
        deal["notes"] = json.dumps({"ai": analysis}, ensure_ascii=False, separators=(",", ":"))
    return deal
