"""
DealScan - Pipeline run registry + updater.

The published JSON bundle written to Vercel KV by the pipeline is mirrored
here (data/registry.json), so:
  * the webapp can be pointed at the repo artifact instead of KV when KV is
    not configured (same shape),
  * deployments get a fresh patch of the latest bundle automatically via
    the update-bundle command.

Bundle shape (matches what the webapp /api/deals reads):
{
  "generated_at": <iso>,
  "count": n,
  "deals": [ { ...one report per deal... } ],
  "meta": { "scraped_counties": [...], "status": ... }
}
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REGISTRY_PATH = os.path.join(DATA_DIR, "registry.json")
BUNDLE_PATH = os.path.join(DATA_DIR, "bundle.json")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def load_registry() -> Dict[str, Any]:
    _ensure_dir()
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"runs": [], "last_run": None}


def record_run(county_id: str, status: str, counts: Dict[str, int],
               error: str = "") -> Dict[str, Any]:
    reg = load_registry()
    entry = {
        "county_id": county_id,
        "status": status,
        "counts": counts,
        "error": error,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    reg.setdefault("runs", []).insert(0, entry)
    reg["runs"] = reg["runs"][:30]  # keep last 30
    reg["last_run"] = entry
    _ensure_dir()
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)
    return entry


def write_bundle(deals: List[Dict[str, Any]],
                 scraped_counties: List[str],
                 status: str = "ok",
                 error: str = "") -> str:
    """Serialize the top deals bundle for the webapp."""
    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(deals),
        "deals": deals,
        "error": error,
        "meta": {
            "scraped_counties": scraped_counties,
            "status": status,
        },
    }
    _ensure_dir()
    with open(BUNDLE_PATH, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=1)
    return BUNDLE_PATH


def load_bundle() -> Optional[Dict[str, Any]]:
    try:
        with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    # `python -m runregistry` -> print last run summary
    reg = load_registry()
    last = reg.get("last_run")
    if last:
        print(f"last run: {last['county_id']} {last['status']} "
              f"{last['counts']} @ {last['at']}")
    else:
        print("no runs recorded yet")