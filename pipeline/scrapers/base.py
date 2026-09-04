"""
DealScan - Base scraper adapter interface.

Every county-specific scraper adapter must implement this interface.
The runner uses adapters polymorphically so counties can share code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


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
    """Abstract base for all county-specific scraper adapters."""

    @abstractmethod
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return raw records from the source."""

    @abstractmethod
    def parse(self, raw: Any) -> List[Dict[str, Any]]:
        """Convert source-specific records into normalized dicts."""

    @abstractmethod
    def validate(self, record: Dict[str, Any]) -> bool:
        """Return True if the normalized record is valid enough to keep."""

    def normalize(self, record: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Map county/source fields into DealScan's canonical Property shape."""
        field_map = cfg.get("fields") or {}
        defaults = dict(cfg.get("defaults") or {})
        county_id = cfg.get("county_id")

        def get_value(src_field: Any) -> Any:
            if isinstance(src_field, (list, tuple)):
                values = [get_value(part) for part in src_field]
                values = [str(v).strip() for v in values if v not in (None, "") and str(v).strip()]
                return ", ".join(values) if values else None
            if not src_field:
                return None
            if "." in str(src_field):
                cur: Any = record
                for part in str(src_field).split("."):
                    if isinstance(cur, dict):
                        cur = cur.get(part)
                    else:
                        return None
                return cur
            return record.get(src_field)

        normalized = dict(record)
        normalized.update(defaults)
        for canonical, source in field_map.items():
            value = get_value(source)
            if value is not None or canonical not in normalized:
                normalized[canonical] = value

        if county_id:
            normalized["county_id"] = county_id

        for key in (
            "lot_size_acres", "assessed_value", "market_value", "tax_amount",
            "latitude", "longitude", "improvement_value",
        ):
            value = normalized.get(key)
            if value in (None, "", " "):
                normalized[key] = None
                continue
            try:
                normalized[key] = float(value)
            except (TypeError, ValueError):
                normalized[key] = None

        # Derive improvement status only from an actual source value.
        if "has_improvements" not in normalized or normalized.get("has_improvements") in (None, "", " "):
            improvement_value = normalized.get("improvement_value")
            if improvement_value is not None:
                normalized["has_improvements"] = improvement_value > 0

        for key in ("tax_delinquent_years", "year_acquired"):
            value = normalized.get(key)
            try:
                normalized[key] = int(float(value)) if value not in (None, "", " ") else 0
            except (TypeError, ValueError):
                normalized[key] = 0

        return normalized

    def run(self, cfg: Dict[str, Any], max_records: int = 5000):
        county_id = cfg.get("county_id", "unknown")
        result = ScrapeResult(county_id=county_id, source_type=self.__class__.__name__)
        raw: List[Dict[str, Any]] = []
        try:
            raw = self.discover(cfg)
        except Exception as exc:
            result.errors.append(f"discover_error: {exc}")
            return result, []
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
            try:
                canonical = self.normalize(record, cfg)
            except Exception as exc:
                result.rejected += 1
                result.rejection_reasons["normalize_error"] = result.rejection_reasons.get("normalize_error", 0) + 1
                result.errors.append(f"normalize_error: {exc}")
                continue
            result.normalized += 1
            if not self.validate(canonical):
                result.rejected += 1
                result.rejection_reasons["validation_failed"] = result.rejection_reasons.get("validation_failed", 0) + 1
                continue
            normalized.append(canonical)

        # Keep the in-memory source pool available to the scorer so it can build
        # real same-source sale comparables without making another network call.
        # It is deliberately an internal key and is ignored by persistence.
        for canonical in normalized:
            canonical["_source_comp_pool"] = normalized

        return result, normalized
