"""
DealScan - Scraper framework.

Polite, cache-backed HTTP client + source probing + shared adapter interface.
"""
from __future__ import annotations

import json
import logging
import math
import tempfile
import os
import time
import urllib.robotparser as robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from urllib3.exceptions import HTTPError as TransportError

USER_AGENT = "DealScanBot/0.1 (+https://github.com/doriaphiri82-glitch/dealscan; land screening research)"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
DEFAULT_TTL = 7 * 24 * 3600
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
log = logging.getLogger(__name__)
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
    # Never turn an untrusted hostname into a filesystem path.
    host = hashlib.sha256(urlparse(url).netloc.encode()).hexdigest()[:16]
    key = hashlib.sha256(f"{ns}:{url}".encode()).hexdigest()
    return os.path.join(CACHE_DIR,host,key+'.cache')


def _cached(url: str, ttl: int, ns: str = "", max_bytes: int = DEFAULT_MAX_BYTES) -> Optional[Any]:
    try:
        path = _cache_path(url,ns)
        stat = os.stat(path)
        age = time.time()-stat.st_mtime
        if age<0 or age>ttl or stat.st_size>max_bytes*2+16384: return None
        with open(path,encoding='utf-8') as source: envelope=json.load(source)
        if not isinstance(envelope,dict) or 'body' not in envelope: return None
        value=envelope['body']
        if envelope.get('b64'):
            import base64
            value=base64.b64decode(value,validate=True)
        size=len(value) if isinstance(value,bytes) else len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())
        return value if size<=max_bytes else None
    except FileNotFoundError: return None
    except (OSError,ValueError,TypeError):
        log.warning('Source cache read unavailable; performing a fresh request')
        return None


def _store_cache(url: str, body: Any, ns: str = "") -> None:
    temporary=None
    try:
        stored=body
        if isinstance(body,bytes):
            import base64
            stored=base64.b64encode(body).decode('ascii')
        path=_cache_path(url,ns)
        os.makedirs(os.path.dirname(path),mode=0o700,exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=os.path.dirname(path),delete=False) as target:
            temporary=target.name
            json.dump({'fetched_at':time.time(),'b64':isinstance(body,bytes),'body':stored},target,allow_nan=False,ensure_ascii=False)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary,path)
    except (OSError,ValueError,TypeError):
        log.warning('Optional source cache write unavailable; fetched data remains usable')
    finally:
        if temporary:
            try: os.unlink(temporary)
            except OSError: pass


def _politeness_delay(url: str) -> None:
    host = urlparse(url).netloc
    last = _last_request_at.get(host)
    if last is not None:
        wait = MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (hash(host) % 100 / 100.0)
        elapsed = time.time() - last
        if elapsed < wait:
            time.sleep(wait - elapsed)
    _last_request_at[host] = time.time()


def _valid_url(url: str) -> bool:
    try:
        parsed=urlparse(url)
        return isinstance(url,str) and not any(ord(char)<32 or ord(char)==127 for char in url) and parsed.scheme in {'https','http'} and bool(parsed.hostname) and not (parsed.username or parsed.password) and (parsed.port is None or 1<=parsed.port<=65535)
    except (TypeError,ValueError): return False


def _bounded_content(response, max_bytes: int, deadline: float | None = None) -> bytes:
    try:
        size=response.headers.get('content-length')
        if size and int(size)>max_bytes: raise ValueError('Response exceeds byte limit')
        raw=getattr(response,'raw',None)
        read1=getattr(raw,'read1',None)
        def chunks():
            if callable(read1):
                # read1 returns available data, rather than waiting to fill a large
                # buffer while a slow peer keeps resetting the socket timeout.
                while True:
                    if deadline is not None and time.monotonic()>deadline: raise TimeoutError()
                    chunk=read1(65536,decode_content=True)
                    if not chunk: break
                    yield chunk
            else:
                yield from response.iter_content(chunk_size=65536)
        content=bytearray()
        for chunk in chunks():
            if deadline is not None and time.monotonic()>deadline: raise TimeoutError()
            if len(content)+len(chunk)>max_bytes: raise ValueError('Response exceeds byte limit')
            content.extend(chunk)
        return bytes(content)
    finally:
        response.close()


def robots_allows(url: str) -> bool:
    if not _valid_url(url): return False
    try:
        parsed=urlparse(url)
        response=_session.get(f'{parsed.scheme}://{parsed.netloc}/robots.txt',timeout=(5,10),allow_redirects=False,stream=True)
        if response.status_code in (404,410):
            response.close()
            return True
        if response.status_code!=200:
            response.close()
            return False
        rp=robotparser.RobotFileParser()
        rp.parse(_bounded_content(response,65536,time.monotonic()+10).decode('utf-8',errors='replace').splitlines())
        return rp.can_fetch(USER_AGENT,url)
    except (requests.RequestException,TransportError,OSError,ValueError): return False


def _json(content: bytes):
    def constant(_): raise ValueError('Nonfinite JSON value')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON field')
            result[key]=value
        return result
    return json.loads(content,parse_constant=constant,object_pairs_hook=pairs)


def _network(method: str,url: str,*,payload=None,raw=False,as_json=False,
             timeout=30,retries=2,max_bytes=DEFAULT_MAX_BYTES) -> FetchResult:
    if not _valid_url(url): return FetchResult(False,error='Invalid source URL')
    if type(max_bytes) is not int or not 1<=max_bytes<=128*1024*1024:
        return FetchResult(False,error='Invalid response byte cap')
    if type(retries) is not int or not 0<=retries<=3 or not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not math.isfinite(timeout) or not 0<timeout<=120:
        return FetchResult(False,error='Invalid request timeout or retry budget')
    for attempt in range(retries+1):
        _politeness_delay(url)
        response=None
        try:
            deadline=time.monotonic()+timeout
            options={'timeout':(min(5,timeout),min(10,timeout)),'allow_redirects':False,'stream':True}
            response=_session.post(url,data=payload,**options) if method=='POST' else _session.get(url,**options)
            if response.status_code!=200:
                status=response.status_code
                response.close()
                if status in (429,500,502,503,504) and attempt<retries:
                    time.sleep(2**attempt*5)
                    continue
                return FetchResult(False,status,error=f'HTTP {status}')
            content=_bounded_content(response,max_bytes,deadline)
            body=content if raw else _json(content) if as_json or 'json' in response.headers.get('content-type','') else content.decode(response.encoding or 'utf-8')
            if time.monotonic()>deadline: raise TimeoutError()
            return FetchResult(True,200,body)
        except (ValueError,UnicodeError):
            return FetchResult(False,error='Invalid or oversized source response')
        except (requests.RequestException,TransportError,OSError) as exc:
            if attempt>=retries: return FetchResult(False,error=type(exc).__name__)
            time.sleep(2**attempt*5)
        finally:
            if response is not None: response.close()
    return FetchResult(False,error='unreachable')


def fetch(url: str,ttl: int=DEFAULT_TTL,as_json: bool=False,respect_robots: bool=True,
          retries: int=2,timeout: int=30,raw: bool=False,max_bytes: int | None=DEFAULT_MAX_BYTES) -> FetchResult:
    max_bytes=DEFAULT_MAX_BYTES if max_bytes is None else max_bytes
    if not _valid_url(url): return FetchResult(False,error='Invalid source URL')
    if type(max_bytes) is not int or not 1<=max_bytes<=128*1024*1024:
        return FetchResult(False,error='Invalid response byte cap')
    # A text/JSON/raw request must never reuse an incompatible cached value.
    ns='v2-'+('raw' if raw else 'json' if as_json else 'auto')
    cached=_cached(url,ttl,ns,max_bytes) if ttl>0 else None
    if cached is not None: return FetchResult(True,200,cached,from_cache=True)
    if respect_robots and not robots_allows(url):
        return FetchResult(False,error='robots.txt disallows or cannot verify this URL')
    result=_network('GET',url,raw=raw,as_json=as_json,timeout=timeout,retries=retries,max_bytes=max_bytes)
    if result.ok and ttl>0: _store_cache(url,result.body,ns)
    return result


def post_json(url: str,payload: Dict[str,Any],timeout: int=30,retries: int=1,
              max_bytes: int=DEFAULT_MAX_BYTES) -> FetchResult:
    return _network('POST',url,payload=payload,as_json=True,timeout=timeout,retries=retries,max_bytes=max_bytes)


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
