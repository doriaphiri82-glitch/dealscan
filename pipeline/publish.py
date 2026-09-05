"""Publish DealScan bundles to Upstash KV or Redis-compatible stores."""
from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional
from urllib.parse import quote

KEY_TOP = "deals:top"
KEY_DEAL_PREFIX = "deal:"
KV_URL = os.getenv("KV_REST_API_URL", "").rstrip("/")
KV_TOKEN = os.getenv("KV_REST_API_TOKEN", "")
REDIS_URL = os.getenv("REDIS_URL", "").rstrip("/")
REDIS_TOKEN = os.getenv("REDIS_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN") or ""


def _is_redis_proto() -> bool:
    return REDIS_URL.startswith('rediss://') or (os.getenv('DEALSCAN_ENV')!='production' and REDIS_URL.startswith('redis://'))


def _is_redis_rest() -> bool:
    return REDIS_URL.startswith("https://")


def _request(method: str, url: str, **kwargs):
    import requests
    return requests.request(method, url, timeout=20, allow_redirects=False, **kwargs)


def _set_key(key: str, payload: str) -> bool:
    encoded_key = quote(key, safe="")
    if KV_URL.startswith("https://") and KV_TOKEN:
        try:
            r = _request("POST", f"{KV_URL}/set/{encoded_key}", headers={"Authorization": f"Bearer {KV_TOKEN}"}, json=payload)
            if r.ok:
                return True
        except Exception:
            pass
    if _is_redis_rest():
        try:
            headers = {"Authorization": f"Bearer {REDIS_TOKEN}"} if REDIS_TOKEN else {}
            r = _request("POST", f"{REDIS_URL}/set/{encoded_key}", headers=headers, json=payload)
            if r.ok:
                return True
        except Exception:
            pass
    if _is_redis_proto():
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=20, socket_connect_timeout=5)
            client.set(key, payload)
            client.close()
            return True
        except Exception:
            pass
    return False


def publish_top(bundle: Dict[str, Any] | None = None) -> bool:
    """Opt-in diagnostic cache export. Caller-provided bundle contents are ignored.

    This does not publish a deal. The live application never reads these keys.
    """
    if os.getenv('ENABLE_CACHE_EXPORT')!='true': return False
    from database import get_top_deals
    from persistence import PUBLIC_DEAL_FIELDS,PUBLIC_PROPERTY_FIELDS,json_safe,now
    from normalization import sale_date
    from datetime import datetime,timezone
    records=[]
    for row in get_top_deals(limit=100):
        expiry=sale_date(row.get('verification_expires_at'))
        if row.get('verification_status')!='verified' or not expiry or expiry<=datetime.now(timezone.utc): continue
        records.append({key:row.get(key) for key in (*PUBLIC_DEAL_FIELDS,*PUBLIC_PROPERTY_FIELDS)})
    snapshot={'generated_at':now(),'deals':records,'count':len(records),'meta':{'storage_source':'verified_database_snapshot'}}
    return _set_key(KEY_TOP,json.dumps(json_safe(snapshot),separators=(',',':')))


def _decode_result(response_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    value = response_json.get("result")
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def read_top() -> Optional[Dict[str, Any]]:
    if KV_URL.startswith("https://") and KV_TOKEN:
        try:
            r = _request("GET", f"{KV_URL}/get/{quote(KEY_TOP, safe='')}", headers={"Authorization": f"Bearer {KV_TOKEN}"})
            if r.ok:
                return _decode_result(r.json())
        except Exception:
            pass
    if _is_redis_rest():
        try:
            headers = {"Authorization": f"Bearer {REDIS_TOKEN}"} if REDIS_TOKEN else {}
            r = _request("GET", f"{REDIS_URL}/get/{quote(KEY_TOP, safe='')}", headers=headers)
            if r.ok:
                return _decode_result(r.json())
        except Exception:
            pass
    if _is_redis_proto():
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=20, socket_connect_timeout=5)
            value = client.get(KEY_TOP)
            client.close()
            return json.loads(value) if value else None
        except Exception:
            pass
    return None


if __name__ == "__main__":
    store = "KV" if KV_URL and KV_TOKEN else "REDIS" if REDIS_URL else "NONE"
    print(f"publish_top -> {store}")
    cfg = read_top() if store != "NONE" else None
    print("read_top:", len(cfg.get("deals", [])) if cfg else 0, "deals")
