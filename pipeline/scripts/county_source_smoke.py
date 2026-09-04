"""Read-only live smoke checks for every configured ArcGIS county.

The checker runs sources in parallel, validates configured fields, retrieves a
small sample, normalizes it, and checks vacancy classification. It never
writes to the DealScan database or promotes coverage status.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from scrapers.counties import COUNTY_SCRAPERS
from scrapers import arcgis

TARGETS = tuple(COUNTY_SCRAPERS.keys())


def check_county(county_id: str, max_records: int) -> Dict[str, Any]:
    cfg = COUNTY_SCRAPERS[county_id]
    layer = cfg.get("arcgis_layer_url")
    field_map = cfg.get("fields", {})
    requested = []
    for value in field_map.values():
        values = value if isinstance(value, (list, tuple)) else [value]
        requested.extend(str(item) for item in values if item)
    requested = list(dict.fromkeys(requested))
    result: Dict[str, Any] = {
        "county_id": county_id,
        "source": layer,
        "source_reachable": False,
        "fields_ok": False,
        "records": 0,
        "normalized": 0,
        "vacant_candidates": 0,
        "sample": [],
        "errors": [],
    }
    try:
        if not layer:
            raise RuntimeError("missing arcgis_layer_url")
        actual = arcgis.layer_fields(layer)
        if not actual:
            raise RuntimeError("layer metadata unavailable")
        result["source_reachable"] = True
        missing = [field for field in requested if field not in actual]
        result["missing_fields"] = missing
        result["fields_ok"] = not missing
        if missing:
            result["errors"].append("missing configured fields: " + ", ".join(missing))

        props = []
        for raw in arcgis.query_layer(layer, cfg.get("where", "1=1"), requested, max_records=max_records, page_size=min(25, max_records)):
            props.append(arcgis.map_attributes(raw, field_map, county_id, cfg.get("defaults", {})))
            if len(props) >= max_records:
                break
        vacant = [p for p in props if arcgis.is_vacant_residential(p, county_id)]
        result["records"] = len(props)
        result["normalized"] = sum(1 for p in props if p.get("apn"))
        result["vacant_candidates"] = len(vacant)
        result["sample"] = [
            {"apn": p.get("apn"), "lot_size_acres": p.get("lot_size_acres"), "land_use": p.get("land_use"), "zoning": p.get("zoning"), "has_improvements": p.get("has_improvements"), "improvement_value": p.get("improvement_value"), "market_value": p.get("market_value"), "last_sale_price": p.get("last_sale_price")}
            for p in props[:3]
        ]
        if not props:
            result["errors"].append("source returned zero records")
    except Exception as exc:
        result["errors"].append(str(exc))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--county", choices=TARGETS, action="append")
    parser.add_argument("--max-records", type=int, default=25)
    args = parser.parse_args()
    if not 1 <= args.max_records <= 250:
        parser.error("--max-records must be between 1 and 250")
    counties = args.county or list(TARGETS)
    with ThreadPoolExecutor(max_workers=max(1, len(counties))) as executor:
        futures = [executor.submit(check_county, county_id, args.max_records) for county_id in counties]
        results = [future.result() for future in futures]
    results.sort(key=lambda item: item["county_id"])
    print(json.dumps({"read_only": True, "parallel": True, "checked": len(results), "results": results}, indent=2))
    return 0 if all(not item["errors"] and item["records"] > 0 and item["fields_ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
