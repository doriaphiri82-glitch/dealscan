"""Shared source adapter with per-record isolation and private provenance."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from normalization import normalize


@dataclass
class ScrapeResult:
    county_id: str
    source_type: str
    discovered: int = 0
    downloaded: int = 0
    parsed: int = 0
    normalized: int = 0
    rejected: int = 0
    skipped: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    stored: int = 0
    scored: int = 0
    qualified: int = 0
    published: int = 0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseScraperAdapter(ABC):
    @abstractmethod
    def discover(self, cfg: dict) -> list[dict]:
        """Fetch a bounded set of raw records."""

    @abstractmethod
    def parse(self, raw: Any) -> list[dict]:
        """Parse one source item."""

    @abstractmethod
    def validate(self, record: dict) -> bool:
        """Validate a normalized property identity."""

    def normalize(self, record: dict, cfg: dict) -> dict:
        return normalize(record, cfg)

    def run(self, cfg: dict, max_records: int = 5000):
        cfg = {**cfg, 'max_records': max_records}
        result = ScrapeResult(county_id=cfg.get('county_id', 'unknown'), source_type=self.__class__.__name__)
        audit = result.metadata['audit_records'] = []
        source_url = cfg.get('arcgis_layer_url') or cfg.get('data_url') or cfg.get('parcel_source_url')
        try:
            raw = self.discover(cfg)
        except Exception as exc:
            result.errors.append(f'discover_error: {type(exc).__name__}')
            return result, []
        result.discovered = result.downloaded = len(raw)
        normalized, seen = [], set()
        for item in raw:
            try:
                records = self.parse(item)
            except Exception as exc:
                records = []
                result.rejected += 1
                result.rejection_reasons['parse_error'] = result.rejection_reasons.get('parse_error', 0) + 1
                result.errors.append(f'parse_error: {type(exc).__name__}')
                audit.append({'raw_payload': item, 'source_url': source_url, 'status': 'rejected', 'rejection_reason': 'parse_error'})
            result.parsed += len(records)
            for record in records:
                canonical = {}
                reason = ''
                try:
                    if not isinstance(record, dict):
                        raise ValueError('Source record is not an object')
                    canonical = self.normalize(record, cfg)
                    result.normalized += 1
                    if not self.validate(canonical):
                        reason = 'validation_failed'
                except Exception as exc:
                    reason = 'normalize_error'
                    result.errors.append(f'normalize_error: {type(exc).__name__}')
                if reason:
                    result.rejected += 1
                    result.rejection_reasons[reason] = result.rejection_reasons.get(reason, 0) + 1
                    audit.append({'raw_payload': record, 'normalized_payload': canonical, 'source_url': source_url,
                                  'status': 'rejected', 'rejection_reason': reason})
                    continue
                identity = (canonical.get('county_id'), canonical.get('apn'))
                if identity in seen:
                    result.skipped += 1
                    continue
                seen.add(identity)
                source_id = next((record.get(key) for key in (cfg.get('object_id_field'), 'OBJECTID_1', 'ObjectID_1', 'OBJECTID', 'objectid', 'source_record_id', 'id') if key and record.get(key) not in (None, '')), canonical.get('apn'))
                canonical['_source_record_id'] = str(source_id) if source_id is not None else None
                canonical['_raw_payload'] = record
                canonical['source_url'] = source_url
                normalized.append(canonical)
        return result, normalized
