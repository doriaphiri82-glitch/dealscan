"""
DealScan - Publish bundle to Vercel KV / any REDIS_URL.

This is the pipeline -> webapp bridge. Reads either:
  * KV_REST_API_URL + KV_REST_API_TOKEN (Upstash REST), or
  * REDIS_URL (native redis:// or Upstash REST https://)

Matches the same storage logic the webapp /api/deals will use.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

KEY_TOP = "deals:top"

KV_URL = os.getenv("KV_REST_API_URL", "")
KV_TOKEN = os.getenv("KV_REST_API_TOKEN", "")
REDIS_URL = os.getenv("REDIS_URL", "")


def _is_redis_proto() -> bool:
    return REDIS_URL.startswith("redis://") or REDIS_URL.startswith("rediss://")


def _is_redis_rest() -> bool:
    return REDIS_URL.startswith("https://") or REDIS_URL.startswith("http://")


def publish_top(bundle: Dict[str, Any]) -> bool:
    """Push the top-deals bundle to the configured store. Returns success."""
    if KV_URL and KV_TOKEN:
        try:
            import requests
            r = requests.post(
                f"{KV_URL}/set/{KEY_TOP}",
                headers={"Authorization": f"Bearer {KV_TOKEN}",
                         "Content-Type": "application/json"},
                json=bundle,
                timeout=20,
            )
            return r.status_code == 200
        except Exception:
            pass

    if _is_redis_rest():
        try:
            import requests
            r = requests.post(f"{REDIS_URL}/set/{KEY_TOP}",
                              json=bundle, timeout=20)
            return r.status_code == 200
        except Exception:
            pass

    if _is_redis_proto():
        try:
            import redis as rd
            client = rd.Redis.from_url(REDIS_URL)
            client.set(KEY_TOP, json.dumps(bundle))
            client.close()
            return True
        except Exception:
            pass
    return False


def read_top() -> Optional[Dict[str, Any]]:
    """Read the top-deals bundle back (useful for verifying publishes)."""
    if KV_URL and KV_TOKEN:
        try:
            import requests
            r = requests.get(f"{KV_URL}/get/{KEY_TOP}",
                             headers={"Authorization": f"Bearer {KV_TOKEN}"},
                             timeout=20)
            data = r.json().get("result")
            return json.loads(data) if data else None
        except Exception:
            return None
    if _is_redis_rest():
        try:
            import requests
            r = requests.get(f"{REDIS_URL}/get/{KEY_TOP}", timeout=20)
            data = r.json().get("result")
            return json.loads(data) if data else None
        except Exception:
            return None
    if _is_redis_proto():
        try:
            import redis as rd
            client = rd.Redis.from_url(REDIS_URL)
            val = client.get(KEY_TOP)
            client.close()
            return json.loads(val) if val else None
        except Exception:
            return None
    return None


if __name__ == "__main__":
    store = ("KV" if KV_URL else "REDIS" if REDIS_URL else "NONE")
    print(f"publish_top -> {store}")
    if store != "NONE":
        cfg = read_top()
        print("read_top:", (len(cfg["deals"]) if cfg else 0), "deals")