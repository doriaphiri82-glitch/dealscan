"""
DealScan - Source discovery engine.

Probes county websites and GIS portals to identify likely public
parcel/property-data sources without manual per-county research.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from scrapers.base import fetch, probe


@dataclass
class SourceCandidate:
    url: str
    source_type: str
    confidence: float
    notes: str = ""


def discover_arcgis_sources(county_cfg: Dict[str, Any]) -> List[SourceCandidate]:
    candidates: List[SourceCandidate] = []
    root = county_cfg.get("arcgis_root")
    if not root:
        return candidates
    if "opendata.arcgis.com" in root:
        candidates.append(SourceCandidate(
            url=f"{root}/api/feed/dcat-us/1.1.json",
            source_type="arcgis_hub",
            confidence=0.9,
            notes="ArcGIS Hub DCAT feed",
        ))
    else:
        candidates.append(SourceCandidate(
            url=f"{root}/arcgis/rest/services?f=json",
            source_type="arcgis_rest",
            confidence=0.8,
            notes="ArcGIS REST services directory",
        ))
    layer_url = county_cfg.get("arcgis_layer_url")
    if layer_url:
        candidates.append(SourceCandidate(
            url=layer_url,
            source_type="arcgis_layer",
            confidence=1.0,
            notes="Explicit layer URL",
        ))
    return candidates


def discover_flatfile_sources(county_cfg: Dict[str, Any]) -> List[SourceCandidate]:
    candidates: List[SourceCandidate] = []
    for key in ("parcel_source_url", "open_gov_url", "data_url"):
        url = county_cfg.get(key)
        if not url:
            continue
        candidates.append(SourceCandidate(
            url=url,
            source_type="flatfile",
            confidence=0.7,
            notes=f"Configured {key}",
        ))
    return candidates


def discover_sources(county_cfg: Dict[str, Any]) -> List[SourceCandidate]:
    candidates = []
    candidates.extend(discover_arcgis_sources(county_cfg))
    candidates.extend(discover_flatfile_sources(county_cfg))
    seen = set()
    unique = []
    for c in candidates:
        if c.url not in seen:
            seen.add(c.url)
            unique.append(c)
    unique.sort(key=lambda c: c.confidence, reverse=True)
    return unique


def probe_county_sources(county_id: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    for candidate in discover_sources(cfg):
        try:
            result = probe(candidate.url, county_id, candidate.source_type,
                           expect="arcgis" if "arcgis" in candidate.source_type else "http")
            results.append({
                "county_id": county_id,
                "source_type": candidate.source_type,
                "url": candidate.url,
                "reachable": result.reachable,
                "status": result.status,
                "detail": result.detail,
                "error": result.error,
                "verified": result.verified,
                "confidence": candidate.confidence,
                "notes": candidate.notes,
            })
        except Exception as exc:
            results.append({
                "county_id": county_id,
                "source_type": candidate.source_type,
                "url": candidate.url,
                "reachable": False,
                "status": 0,
                "detail": "",
                "error": str(exc)[:200],
                "verified": False,
                "confidence": candidate.confidence,
                "notes": candidate.notes,
            })
    return results
