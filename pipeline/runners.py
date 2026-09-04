"""
DealScan - Per-county run runner (single source of truth for a county run).

Pipeline of one county scrape:
  discover -> get data (arcgis/html) -> normalize -> filter -> save to SQLite
  -> score -> publish bundle + registry.

`run()` never raises; always returns a summary dict.
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional

from config.counties.national_registry import PILOT_COUNTIES
from database import get_top_deals, save_deal, save_property
from runregistry import record_run, write_bundle
from scoring.deal_scorer import score_and_enrich_deal
from scrapers import arcgis
from scrapers.adapter import BaseScraperAdapter, ScrapeResult
from scrapers.arcgis_adapter import ArcGISFeatureServerAdapter, ArcGISHubAdapter
from scrapers.counties import COUNTY_SCRAPERS
from scrapers.flatfile_adapter import FlatFileAdapter, CSVAdapter, ExcelAdapter


ADAPTER_MAP = {
    "arcgis": ArcGISFeatureServerAdapter,
    "arcgis_hub": ArcGISHubAdapter,
    "flatfile": FlatFileAdapter,
    "csv": CSVAdapter,
    "excel": ExcelAdapter,
    "state_parcel": ArcGISFeatureServerAdapter,
}


def _adapter_for(cfg: Dict[str, Any]) -> Optional[BaseScraperAdapter]:
    """Select the generic adapter only when the config supplies its inputs.

    County configs using an ArcGIS Hub/root plus candidate services are handled
    by the legacy discovery path below, which knows how to resolve a live layer
    from the Hub DCAT feed. The generic ArcGIS adapter requires a concrete
    ``arcgis_layer_url``; previously it was selected merely because
    ``data_mode`` was ``arcgis``, causing discover() to see no layer URL and
    silently return zero records for every Hub-backed pilot county.
    """
    scraper_type = cfg.get("scraper_type")
    data_mode = cfg.get("data_mode", "arcgis")

    if scraper_type:
        adapter_cls = ADAPTER_MAP.get(scraper_type)
        if adapter_cls is None:
            return None
        if scraper_type in ("arcgis", "arcgis_hub", "state_parcel") and not cfg.get("arcgis_layer_url"):
            return None
        return adapter_cls()

    if data_mode in ("flatfile", "csv", "excel"):
        return ADAPTER_MAP.get(data_mode, FlatFileAdapter)()

    # Root/Hub ArcGIS configs must go through fetch_parcels() discovery unless
    # a concrete layer URL is explicitly configured.
    if data_mode in ("arcgis", "arcgis_hub", "state_parcel") and cfg.get("arcgis_layer_url"):
        return ADAPTER_MAP.get(data_mode, ArcGISFeatureServerAdapter)()
    return None


class RunMetrics:
    """Observability metrics for a single county run."""
    __slots__ = (
        'county_id', 'discovered', 'downloaded', 'parsed', 'normalized',
        'rejected', 'rejection_reasons', 'stored', 'scored', 'qualified',
        'published', 'errors'
    )

    def __init__(self, county_id: str) -> None:
        self.county_id = county_id
        self.discovered = 0
        self.downloaded = 0
        self.parsed = 0
        self.normalized = 0
        self.rejected = 0
        self.rejection_reasons: Dict[str, int] = {}
        self.stored = 0
        self.scored = 0
        self.qualified = 0
        self.published = 0
        self.errors: List[str] = []

    def to_counts(self) -> Dict[str, int]:
        return {
            'discovered': self.discovered,
            'downloaded': self.downloaded,
            'parsed': self.parsed,
            'normalized': self.normalized,
            'rejected': self.rejected,
            'stored': self.stored,
            'scored': self.scored,
            'qualified': self.qualified,
            'published': self.published,
        }

    def record_rejection(self, reason: str) -> None:
        self.rejected += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1


def _county_config(county_id: str) -> Dict[str, Any]:
    cfg = dict(COUNTY_SCRAPERS.get(county_id) or {})
    if not cfg:
        pilot = PILOT_COUNTIES.get(county_id)
        if pilot:
            cfg = dict(pilot)
    return cfg


def fetch_parcels(cfg: Dict[str, Any], county_id: str,
                  max_records: int = 5000) -> List[Dict[str, Any]]:
    """Return normalized property dicts from the configured source.

    Supports:
      * arcgis adapter when a concrete layer URL is configured
      * flatfile adapter
      * direct ArcGIS layer URL fallback
      * root/Hub ArcGIS discovery fallback
      * data_file mode
    """
    adapter = _adapter_for(cfg)
    if adapter:
        result, normalized = adapter.run(cfg, max_records=max_records)
        if result.errors:
            print(f"[debug] adapter {county_id}: errors={result.errors}")
        return normalized[:max_records]

    mode = cfg.get("data_mode", "arcgis")
    if mode == "flatfile":
        from scrapers.flatfile import fetch_el_paso_properties
        props = fetch_el_paso_properties(county_id, max_records=max_records)
        print(f"[debug] flatfile {county_id}: fetched {len(props)} properties")
        return props
    if mode == "arcgis":
        direct_layer = cfg.get("arcgis_layer_url")
        if direct_layer:
            print(f"[debug] arcgis {county_id}: using direct layer {direct_layer}")
            available = arcgis.layer_fields(direct_layer) or []
            print(f"[debug] arcgis {county_id}: layer has {len(available)} fields; sample: {available[:25]}")
            configured = list(cfg.get("fields", {}).values())
            valid = [f for f in configured if f in available]
            out_fields: List[str] = valid if valid else []
            if not valid:
                print(f"[debug] arcgis {county_id}: configured fields {configured} not in layer -> using outFields=*")
            props: List[Dict[str, Any]] = []
            for attrs in arcgis.query_layer(direct_layer, cfg.get("where", "1=1"), out_fields, max_records=max_records):
                prop = arcgis.map_attributes(attrs, cfg.get("fields", {}), county_id, cfg.get("defaults", {}))
                props.append(prop)
            print(f"[debug] arcgis {county_id}: direct layer returned {len(props)} records")
            return props
        root = cfg.get("arcgis_root")
        if not root:
            return []
        props = []
        for folder, service, keywords in cfg.get("services") or []:
            layer: Optional[str] = None
            if "opendata.arcgis.com" in root:
                layer = arcgis.find_layer_via_hub(root, keywords)
            if not layer:
                layer = arcgis.find_layer(root, folder, service, keywords)
            if not layer:
                print(f"[debug] arcgis {county_id}: no layer for {folder}/{service} {keywords}")
                continue
            print(f"[debug] arcgis {county_id}: querying layer {layer}")
            available = arcgis.layer_fields(layer) or []
            print(f"[debug] arcgis {county_id}: layer has {len(available)} fields; sample: {available[:25]}")
            configured = list(cfg.get("fields", {}).values())
            valid = [f for f in configured if f in available]
            out_fields: List[str] = valid if valid else []
            if not valid:
                print(f"[debug] arcgis {county_id}: configured fields {configured} not in layer -> using outFields=*")
            got = 0
            for attrs in arcgis.query_layer(layer, cfg.get("where", "1=1"), out_fields, max_records=max_records):
                got += 1
                prop = arcgis.map_attributes(attrs, cfg.get("fields", {}), county_id, cfg.get("defaults", {}))
                props.append(prop)
            print(f"[debug] arcgis {county_id}: layer returned {got} records")
            if props:
                break
        return props

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
                out.append(dict(it))
        return out
    except Exception:
        return []


def _load_comps_for(county_id: str, prop: Dict[str, Any]) -> List[Dict[str, Any]]:
    return []


def _shape_for_bundle(row: Dict[str, Any]) -> Dict[str, Any]:
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
    """Full county ETL + scoring + publish. Never raises."""
    cfg = _county_config(county_id)
    metrics = RunMetrics(county_id)
    summary: Dict[str, Any] = {
        "county_id": county_id,
        "counts": metrics.to_counts(),
        "status": "ok",
        "error": "",
    }

    if cfg.get("_unavailable"):
        unavailable_reason = cfg.get("_unavailable_reason", "Marked as unavailable")
        summary["status"] = "skipped"
        summary["error"] = unavailable_reason
        print(f"[debug] {county_id}: SKIPPED - {unavailable_reason}")
        record_run(county_id, "skipped", summary["counts"], unavailable_reason)
        return summary

    try:
        if offline:
            props = fetch_parcels({**cfg, "data_mode": "data_file"}, county_id, max_records=max_records)
        else:
            props = fetch_parcels(cfg, county_id, max_records=max_records)
        metrics.downloaded = len(props)
        metrics.discovered = metrics.downloaded
        metrics.parsed = len(props)

        vacant = [p for p in props if arcgis.is_vacant_residential(p, county_id)]
        metrics.normalized = len(vacant)

        scored: List[Dict[str, Any]] = []
        for prop in vacant:
            try:
                comps = _load_comps_for(county_id, prop)
                deal = score_and_enrich_deal(prop, comps, cfg)
            except Exception as exc:
                metrics.record_rejection(f"score_error: {exc}")
                continue
            if deal is None:
                metrics.record_rejection("below_min_profit")
                continue
            if not dry_run:
                try:
                    prop_id = save_property(prop)
                    deal["property_id"] = prop_id
                    deal["source"] = "scrape"
                    deal["motivation_signals"] = ",".join(deal.get("motivation_signals", []))
                    save_deal(deal)
                    metrics.stored += 1
                except Exception as exc:
                    metrics.errors.append(f"save_error: {exc}")
                    metrics.record_rejection("save_error")
                    continue
            deal["apn"] = prop.get("apn")
            deal["address"] = prop.get("address")
            deal["county_id"] = county_id
            deal["county_name"] = cfg.get("name", county_id)
            scored.append(deal)
            metrics.scored += 1
            metrics.qualified += 1

        if mode == "publish" and not dry_run:
            top = get_top_deals(limit=25, min_score=0)
            publish_deals = [_shape_for_bundle(d) for d in top[:25]] if top else []
        else:
            publish_deals = [_shape_for_bundle(d) for d in scored[:25]]
        metrics.published = len(publish_deals)

        if mode == "publish":
            path = write_bundle(publish_deals, [county_id], status="ok", error=summary["error"])
            summary["bundle_path"] = path

        if metrics.errors:
            summary["status"] = "degraded"
            summary["error"] = "; ".join(metrics.errors[:3])
        summary["counts"] = metrics.to_counts()
        record_run(county_id, summary["status"], summary["counts"], summary["error"])
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
