"""
DealScan - Scraper framework.

Polite, cache-backed HTTP client + source probing + shared adapter interface.
"""
from __future__ import annotations

import json
import os
import time
import urllib.robotparser as robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

USER_AGENT = "DealScanBot/0.1 (+https://github.com/doriaphiri82-glitch/dealscan; land screening research)"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
DEFAULT_TTL = 7 * 24 * 3600
MIN_DELAY = 2.0
MAX_DELAY = 4.0

_last_request_at: Dict[str, float] = {}
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})


@dataclass
class FetchResult:
    ok: bool
    status: int = 0
    body: Optional[Any] = None
    from_cache: bool = False
    error: str = ""


def _cache_path(url: str, ns: str = "") -> str:
    import hashlib
    h = hashlib.sha256(f"{ns}:{url}".encode()).hexdigest()[:24]
    host = urlparse(url).netloc.replace(":", "_")
    d = os.path.join(CACHE_DIR, host)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{h}.cache")


def _cached(url: str, ttl: int, ns: str = "") -> Optional[Any]:
    p = _cache_path(url, ns)
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > ttl:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            envelope = json.load(f)
        if envelope.get("b64"):
            import base64
            return base64.b64decode(envelope.get("body") or "")
        return envelope.get("body")
    except Exception:
        return None


def _store_cache(url: str, body: Any, ns: str = "") -> None:
    try:
        stored = body
        if isinstance(body, bytes):
            import base64
            stored = base64.b64encode(body).decode("ascii")
        with open(_cache_path(url, ns), "w", encoding="utf-8") as f:
            json.dump({"url": url, "fetched_at": time.time(), "b64": isinstance(body, bytes), "body": stored}, f)
    except Exception:
        pass


def _politeness_delay(url: str) -> None:
    host = urlparse(url).netloc
    last = _last_request_at.get(host)
    if last is not None:
        wait = MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (hash(host) % 100 / 100.0)
        elapsed = time.time() - last
        if elapsed < wait:
            time.sleep(wait - elapsed)
    _last_request_at[host] = time.time()


def robots_allows(url: str) -> bool:
    try:
        parsed = urlparse(url)
        rp = robotparser.RobotFileParser()
        rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def fetch(url: str, ttl: int = DEFAULT_TTL, as_json: bool = False,
          respect_robots: bool = True, retries: int = 2,
          timeout: int = 30, raw: bool = False) -> FetchResult:
    ns = "raw" if raw else ""
    cached = _cached(url, ttl, ns)
    if cached is not None:
        return FetchResult(ok=True, status=200, body=cached, from_cache=True)
    if respect_robots and not robots_allows(url):
        return FetchResult(ok=False, error="robots.txt disallows this URL")
    for attempt in range(retries + 1):
        _politeness_delay(url)
        try:
            resp = _session.get(url, timeout=timeout)
            if resp.status_code == 200:
                if raw:
                    body: Any = resp.content
                elif as_json:
                    body = resp.json()
                else:
                    ctype = resp.headers.get("content-type", "")
                    body = resp.json() if "application/json" in ctype else resp.text
                _store_cache(url, body, ns)
                return FetchResult(ok=True, status=200, body=body)
            if resp.status_code in (429, 503) and attempt < retries:
                time.sleep(2 ** attempt * 5)
                continue
            return FetchResult(ok=False, status=resp.status_code, error=f"HTTP {resp.status_code}")
        except requests.RequestException as exc:
            if attempt >= retries:
                return FetchResult(ok=False, error=str(exc)[:200])
            time.sleep(2 ** attempt * 5)
    return FetchResult(ok=False, error="unreachable")


def post_json(url: str, payload: Dict[str, Any], timeout: int = 30,
              retries: int = 1) -> FetchResult:
    for attempt in range(retries + 1):
        _politeness_delay(url)
        try:
            resp = _session.post(url, data=payload, timeout=timeout)
            if resp.status_code == 200:
                return FetchResult(ok=True, status=200, body=resp.json())
            if resp.status_code == 429 and attempt < retries:
                time.sleep(5)
                continue
            return FetchResult(ok=False, status=resp.status_code, error=f"HTTP {resp.status_code}")
        except requests.RequestException as exc:
            if attempt >= retries:
                return FetchResult(ok=False, error=str(exc)[:200])
            time.sleep(5)
    return FetchResult(ok=False, error="unreachable")


@dataclass
class ProbeResult:
    county_id: str
    source_name: str
    url: str
    reachable: bool
    status: int = 0
    detail: str = ""
    error: str = ""
    verified: bool = False
    extras: Dict[str, Any] = field(default_factory=dict)


def probe(url: str, county_id: str, source_name: str, expect: str = "http") -> ProbeResult:
    if expect == "arcgis":
        r = fetch(url, ttl=24 * 3600, as_json=True, respect_robots=False, timeout=10)
        if r.ok and isinstance(r.body, dict):
            entries = r.body.get("services") or r.body.get("folders") or []
            return ProbeResult(county_id, source_name, url, True, 200,
                               f"arcgis ok, {len(entries)} entries", verified=len(entries) > 0,
                               extras={"services": len(entries)})
        return ProbeResult(county_id, source_name, url, False, r.status, r.error or "unreachable")
    r = fetch(url, ttl=24 * 3600, timeout=10)
    if r.ok:
        body = r.body or ""
        detail = f"{len(body)} chars" if isinstance(body, str) else "json"
        return ProbeResult(county_id, source_name, url, True, 200, detail)
    return ProbeResult(county_id, source_name, url, False, r.status, r.error or "unreachable", verified=False)


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
    @abstractmethod
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def parse(self, raw: Any) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def validate(self, record: Dict[str, Any]) -> bool:
        pass

    def normalize(self, record: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
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

        for key in ("lot_size_acres", "assessed_value", "market_value", "tax_amount", "latitude", "longitude", "improvement_value"):
            value = normalized.get(key)
            if value in (None, "", " "):
                normalized[key] = None
            else:
                try:
                    normalized[key] = float(value)
                except (TypeError, ValueError):
                    normalized[key] = None

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
        return result, normalized
