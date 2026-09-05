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


# Compatibility exports: a single adapter implementation avoids divergent
# normalization/vacancy behavior between legacy and current import paths.
from .adapter import BaseScraperAdapter, ScrapeResult  # noqa: E402,F401
