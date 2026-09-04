"""Publish DealScan bundles to Upstash KV or Redis-compatible stores."""
from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional

KEY_TOP = "deals:top"
KV_URL = os.getenv("KV_REST_API_URL", "").rstrip("/")
KV_TOKEN = os.getenv("KV_REST_API_TOKEN", "")
REDIS_URL = os.getenv("REDIS_URL", "").rstrip("/")

def _is_redis_proto() -> bool:
    return REDIS_URL.startswith(("redis://", "rediss://"))

def _is_redis_rest() -> bool:
    return REDIS_URL.startswith(("https://", "http://"))

def _request(method: str, url: str, **kwargs):
    import requests
    return requests.request(method, url, timeout=20, **kwargs)

def publish_top(bundle: Dict[str, Any]) -> bool:
    payload = json.dumps(bundle, separators=(",", ":"))
    if KV_URL and KV_TOKEN:
        try:
            r = _request("POST", f"{KV_URL}/set/{KEY_TOP}", headers={"Authorization": f"Bearer {KV_TOKEN}"}, json=payload)
            if r.ok:
                return True
        except Exception:
            pass
    if _is_redis_rest():
        try:
            r = _request("POST", f"{REDIS_URL}/set/{KEY_TOP}", json=payload)
            if r.ok:
                return True
        except Exception:
            pass
    if _is_redis_proto():
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=20)
            client.set(KEY_TOP, payload)
            client.close()
            return True
        except Exception:
            pass
    return False

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
    if KV_URL and KV_TOKEN:
        try:
            r = _request("GET", f"{KV_URL}/get/{KEY_TOP}", headers={"Authorization": f"Bearer {KV_TOKEN}"})
            if r.ok:
                return _decode_result(r.json())
        except Exception:
            pass
    if _is_redis_rest():
        try:
            r = _request("GET", f"{REDIS_URL}/get/{KEY_TOP}")
            if r.ok:
                return _decode_result(r.json())
        except Exception:
            pass
    if _is_redis_proto():
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=20)
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
