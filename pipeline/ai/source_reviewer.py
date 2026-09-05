"""Optional OpenAI-powered review layer for discovered parcel sources.

Deterministic discovery and ETL validation remain authoritative. This agent only
adds a structured human-readable assessment to help prioritize which discovered
sources should be verified next.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from pydantic import BaseModel, Field

try:
    from agents import Agent, Runner
except ImportError:  # pragma: no cover - dependency is installed in CI/runtime
    Agent = None  # type: ignore[assignment,misc]
    Runner = None  # type: ignore[assignment,misc]


class SourceReview(BaseModel):
    priority: int = Field(ge=0, le=100)
    likely_parcel_source: bool
    likely_authoritative: bool
    verification_focus: list[str]
    rationale: str


def build_source_review_agent() -> Any:
    """Build the stateless reviewer; construction never calls the OpenAI API."""
    if Agent is None:
        raise RuntimeError("openai-agents is not installed")
    return Agent(
        name="DealScan Source Reviewer",
        model=os.getenv("DEALSCAN_AI_MODEL", "gpt-5.4-mini"),
        instructions=(
            "Review discovered real-estate parcel data sources for DealScan. "
            "Use only the supplied metadata; do not invent facts. Prioritize "
            "official government sources, explicit parcel semantics, county/FIPS "
            "coverage, parcel identifiers, addresses, values, land use and "
            "usable ArcGIS/REST endpoints. Discovery is never verification. "
            "Return concise, actionable verification priorities."
        ),
        output_type=SourceReview,
    )


async def review_source_candidate(candidate: Dict[str, Any]) -> SourceReview:
    """Ask OpenAI to prioritize a discovered source without changing its status."""
    if Runner is None:
        raise RuntimeError("openai-agents is not installed")
    agent = build_source_review_agent()
    result = await Runner.run(agent, json.dumps(candidate, sort_keys=True, default=str))
    return result.final_output
