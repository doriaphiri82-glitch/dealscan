"""Read-only live smoke checks for newly configured ArcGIS counties.

This script never writes to the DealScan database. It verifies that each
source is reachable, fields are present, records normalize, and vacancy
classification produces plausible candidates. Keep the record cap small so
it is safe to run manually against public county services.

Usage:
    PYTHONPATH=pipeline python pipeline/scripts/county_source_smoke.py
    PYTHONPATH=pipeline python pipeline/scripts/county_source_smoke.py --county pinal_az --max-records 25
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from config.counties import COUNTY_SCRAPERS
from scrapers import arcgis

TARGETS = ("yavapai_az", "washoe_nv", "pinal_az")


def check_county(county_id: str, max_records: int) -> Dict[str, Any]:
    cfg = COUNTY_SCRAPERS[county_id]
    layer = cfg["arcgis_layer_url"]
    field_map = cfg.get("fields", {})
    requested = []
    for value in field_map.values():
        if isinstance(value, (list, tuple)):
            requested.extend(value)
        elif value:
            requested.append(value)
    requested = list(dict.fromkeys(requested))

    result: Dict[str, Any] = {
        "county_id": county_id,
        "source": layer,
        "source_reachable": False,
        "fields_ok": False,
        "records": 0,
        "vacant_candidates": 0,
        "sample": [],
        "errors": [],
    }

    try:
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
        for raw in arcgis.query_layer(
            layer,
            cfg.get("where", "1=1"),
            requested,
            max_records=max_records,
            page_size=min(25, max_records),
        ):
            prop = arcgis.map_attributes(raw, field_map, county_id, cfg.get("defaults", {}))
            props.append(prop)
            if len(props) >= max_records:
                break

        vacant = [p for p in props if arcgis.is_vacant_residential(p, county_id)]
        result["records"] = len(props)
        result["vacant_candidates"] = len(vacant)
        result["sample"] = [
            {
                "apn": p.get("apn"),
                "lot_size_acres": p.get("lot_size_acres"),
                "land_use": p.get("land_use"),
                "zoning": p.get("zoning"),
                "has_improvements": p.get("has_improvements"),
                "improvement_value": p.get("improvement_value"),
            }
            for p in props[:3]
        ]
    except Exception as exc:  # smoke tests should report, not crash mid-suite
        result["errors"].append(str(exc))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--county", choices=TARGETS, action="append")
    parser.add_argument("--max-records", type=int, default=25)
    args = parser.parse_args()
    if args.max_records < 1 or args.max_records > 250:
        parser.error("--max-records must be between 1 and 250")

    counties = args.county or list(TARGETS)
    results = [check_county(county_id, args.max_records) for county_id in counties]
    print(json.dumps({"read_only": True, "results": results}, indent=2))
    return 0 if all(not item["errors"] and item["records"] > 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
