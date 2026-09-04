"""Publish and verify the generated DealScan bundle in the live store."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from publish import publish_top, read_top

BUNDLE_PATH = Path(__file__).resolve().parent / "data" / "bundle.json"


def main() -> int:
    configured = bool(
        (os.getenv("KV_REST_API_URL") and os.getenv("KV_REST_API_TOKEN"))
        or os.getenv("REDIS_URL")
    )
    if not configured:
        print("No live Redis/KV credentials configured; committed fallback bundle retained.")
        return 0

    if not BUNDLE_PATH.exists():
        print(f"Bundle not found: {BUNDLE_PATH}", file=sys.stderr)
        return 1

    try:
        with BUNDLE_PATH.open(encoding="utf-8") as f:
            bundle = json.load(f)
    except Exception as exc:
        print(f"Could not read bundle: {exc}", file=sys.stderr)
        return 1

    if not isinstance(bundle, dict) or not isinstance(bundle.get("deals"), list):
        print("Invalid bundle format.", file=sys.stderr)
        return 1

    if not publish_top(bundle):
        print("Live bundle publish failed.", file=sys.stderr)
        return 1

    live = read_top()
    if not live or live.get("generated_at") != bundle.get("generated_at"):
        print("Live bundle verification failed.", file=sys.stderr)
        return 1

    print(f"Published and verified {len(bundle['deals'])} deals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
