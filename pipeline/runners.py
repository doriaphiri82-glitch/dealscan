"""
DealScan - Per-county run runner (single source of truth for a county run).

Pipeline of one county scrape:
  discover -> get data (arcgis/html) -> normalize -> filter -> save to SQLite
  -> score -> publish bundle + registry.

`run()` never raises; always returns a summary dict.
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, List

from config.counties import COUNTIES
from database import get_top_deals, save_deal, save_property
from runregistry import record_run, write_bundle
from scoring.deal_scorer import score_and_enrich_deal
from scrapers import arcgis
from scrapers.counties import COUNTY_SCRAPERS


def _county_config(county_id: str) -> Dict[str, Any]:
    cfg = dict(COUNTIES.get(county_id) or {})
    cfg.update(COUNTY_SCRAPERS.get(county_id) or {})
    return cfg


def fetch_parcels(cfg: Dict[str, Any], county_id: str,
                  max_records: int = 5000) -> List[Dict[str, Any]]:
    """Return normalized property dicts from the configured source.

    Supports two modes:
      * arcgis: locate + query a parcel layer via the REST API.
      * data_file: read from a local JSON/CSV (tests/dev, or a cached export).
    """
    mode = cfg.get("data_mode", "arcgis")
    if mode == "flatfile":
        from scrapers.flatfile import fetch_el_paso_properties
        return fetch_el_paso_properties(
            county_id, max_records=max_records)
    if mode == "arcgis":
        root = cfg.get("arcgis_root")
        if not root:
            return []
        props: List[Dict[str, Any]] = []
        for folder, service, keywords in cfg.get("services") or []:
            layer = arcgis.find_layer(root, folder, service, keywords)
            if not layer:
                continue
            for attrs in arcgis.query_layer(layer, cfg.get("where", "1=1"),
                                            list(cfg.get("fields", {}).values()),
                                            max_records=max_records):
                prop = arcgis.map_attributes(attrs, cfg.get("fields", {}),
                                             county_id, cfg.get("defaults", {}))
                props.append(prop)
            if props:
                break  # first service that yields data wins
        return props

    # data_file mode
    data_file = cfg.get("data_file")
    if not data_file:
        return []
    try:
        import json
        with open(data_file, "r", encoding="utf-8") as f:
            obj = json.load(f)
        items = obj if isinstance(obj, list) else obj.get("properties", [])
        out = []
        for it in items:
            if isinstance(it, dict) and it.get("county_id"):
                out.append(it)
            else:
                # raw ArcGIS-ish record: keep as-is, normalize minimally
                out.append(dict(it))
        return out
    except Exception:
        return []


def _load_comps_for(county_id: str, prop: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Stub: real comps need recorder/GIS transfers (Phase 2). Until then the
    scorer runs with no comps -> empty profit estimate -> such deals won't
    pass MIN_PROFIT_ESTIMATE, so nothing fabricated gets scored."""
    return []


def _shape_for_bundle(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a DB row (via get_top_deals) to the webapp bundle shape."""
    return {
        "apn": row.get("apn"),
        "address": row.get("address"),
        "county_id": row.get("county_id"),
        "lot_size_acres": row.get("lot_size_acres"),
        "asking_price": row.get("asking_price"),
        "deal_score": row.get("deal_score"),
        "estimated_arv_low": row.get("estimated_arv_low"),
        "estimated_arv_high": row.get("estimated_arv_high"),
        "estimated_profit_low": row.get("estimated_profit_low"),
        "estimated_profit_high": row.get("estimated_profit_high"),
        "motivation_signals": (row.get("motivation_signals") or "").split(","),
        "market_velocity": row.get("market_velocity"),
        "competition_level": row.get("competition_level"),
        "owner_state": row.get("owner_state"),
        "zoning": row.get("zoning"),
        "tax_delinquent_years": row.get("tax_delinquent_years"),
        "source": row.get("source", "scrape"),
    }


def run(county_id: str, mode: str = "publish", max_records: int = 5000,
        dry_run: bool = False, offline: bool = False) -> Dict[str, Any]:
    """Full county ETL + scoring + publish. Never raises.

    `offline=True` forces the local data_file mode (no network), so a
    dry-run works in CI-less / blocked environments.
    """
    cfg = _county_config(county_id)
    summary: Dict[str, Any] = {
        "county_id": county_id,
        "counts": {"found": 0, "vacant": 0, "saved": 0, "published": 0},
        "status": "ok",
        "error": "",
    }
    try:
        if offline:
            props = fetch_parcels({**cfg, "data_mode": "data_file"}, county_id,
                                  max_records=max_records)
        else:
            props = fetch_parcels(cfg, county_id, max_records=max_records)
        summary["counts"]["found"] = len(props)
        vacant = [p for p in props if arcgis.is_vacant_residential(p, county_id)]
        summary["counts"]["vacant"] = len(vacant)

        scored: List[Dict[str, Any]] = []
        for prop in vacant:
            comps = _load_comps_for(county_id, prop)
            deal = score_and_enrich_deal(prop, comps, cfg)
            if deal is None:
                continue
            if not dry_run:
                try:
                    prop_id = save_property(prop)
                    deal["property_id"] = prop_id
                    deal["source"] = "scrape"
                    deal["motivation_signals"] = ",".join(
                        deal.get("motivation_signals", []))
                    save_deal(deal)
                except Exception:
                    continue
            deal["apn"] = prop.get("apn")
            deal["address"] = prop.get("address")
            deal["county_id"] = county_id
            deal["county_name"] = cfg.get("name", county_id)
            scored.append(deal)
            summary["counts"]["saved"] += 1

        if mode == "publish" and not dry_run:
            top = get_top_deals(limit=25, min_score=0)
            publish_deals = [_shape_for_bundle(d) for d in top[:25]] if top else []
        else:
            publish_deals = [_shape_for_bundle(d) for d in scored[:25]]
        summary["counts"]["published"] = len(publish_deals)

        if mode == "publish":
            path = write_bundle(publish_deals, [county_id],
                                status="ok", error=summary["error"])
            summary["bundle_path"] = path

        record_run(county_id, summary["status"], summary["counts"],
                   summary["error"])
    except Exception as exc:
        summary["status"] = "error"
        summary["error"] = f"{exc} | {traceback.format_exc(limit=2)}"
        record_run(county_id, "error", summary["counts"], summary["error"])
    return summary


class CountyRunner:
    def __init__(self, county_id: str):
        self.county_id = county_id

    def run(self, mode: str = "publish", **kw) -> Dict[str, Any]:
        return run(self.county_id, mode=mode, **kw)


COUNTRY_RUNNERS: Dict[str, CountyRunner] = {
    cid: CountyRunner(cid) for cid in COUNTY_SCRAPERS
}