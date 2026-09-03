"""
DealScan - Base scraper adapter interface.

Every county-specific scraper adapter must implement this interface.
The runner uses adapters polymorphically so counties can share code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScrapeResult:
    county_id: str
    source_type: str
    discovered: int = 0
    downloaded: int = 0
    parsed: int = 0
    normalized: int = 0
    rejected: int = 0
    rejection_reasons: Dict[str, int] = field(default_factory=dict)
    stored: int = 0
    scored: int = 0
    qualified: int = 0
    published: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseScraperAdapter(ABC):
    """Abstract base for all county scraper adapters."""

    @abstractmethod
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return raw records from the source."""

    @abstractmethod
    def parse(self, raw: Any) -> List[Dict[str, Any]]:
        """Convert source-specific records into normalized dicts."""

    @abstractmethod
    def validate(self, record: Dict[str, Any]) -> bool:
        """Return True if the record is valid enough to keep."""

    def normalize(self, record: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
        return record

    def run(self, cfg: Dict[str, Any], max_records: int = 5000) -> ScrapeResult:
        county_id = cfg.get("county_id", cfg.get("county_id", "unknown"))
        result = ScrapeResult(county_id=county_id, source_type=self.__class__.__name__)
        raw: List[Dict[str, Any]] = []
        try:
            raw = self.discover(cfg)
        except Exception as exc:
            result.errors.append(f"discover_error: {exc}")
            return result
        result.discovered = len(raw)
        result.downloaded = len(raw)
        parsed: List[Dict[str, Any]] = []
        for item in raw:
            try:
                records = self.parse(item)
                result.parsed += len(records)
                parsed.extend(records)
            except Exception as exc:
                result.rejected += 1
                result.rejection_reasons["parse_error"] = result.rejection_reasons.get("parse_error", 0) + 1
                result.errors.append(f"parse_error: {exc}")
        normalized: List[Dict[str, Any]] = []
        for record in parsed:
            if not self.validate(record):
                result.rejected += 1
                reason = "validation_failed"
                result.rejection_reasons[reason] = result.rejection_reasons.get(reason, 0) + 1
                continue
            try:
                normalized.append(self.normalize(record, cfg))
            except Exception as exc:
                result.rejected += 1
                reason = "normalize_error"
                result.rejection_reasons[reason] = result.rejection_reasons.get(reason, 0) + 1
                result.errors.append(f"normalize_error: {exc}")
                continue
        result.normalized = len(normalized)
        return result, normalized
