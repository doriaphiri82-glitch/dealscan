"""
DealScan - Per-county scraper registry.

Each county defines its data sources. `verified: False` entries are
research-informed candidates that MUST be confirmed by `main.py --probe`
from a network the county does not block (e.g. GitHub Actions), before
trusting the data. See docs/DATA_PIPELINE_SCOPE.md section 2.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import arcgis  # noqa: F401
from .base import probe, ProbeResult  # noqa: F401

# Typical AZ/TX assessor field names for the pipeline Property shape.
# Real field names differ per county service; the probe command reports
# available fields so these maps can be corrected without code changes.
_DEFAULT_FIELDS = {
    "apn": "APN",
    "address": "SITUS_ADDR",
    "lot_size_acres": "LAND_ACRES",
    "assessed_value": "LIMITED_VALUE",
    "market_value": "FULL_CASH_VALUE",
    "owner_name": "OWNER_NAME",
    "owner_address": "OWNER_MAIL_ADDR",
    "owner_state": "OWNER_MAIL_STATE",
    "tax_amount": "TAX_AMT",
    "tax_delinquent_years": "TAX_DELINQ_YEARS",
    "year_acquired": "SALE_YEAR",
    "zoning": "ZONING",
    "land_use": "LAND_USE",
    "has_improvements": "HAS_IMPROVEMENTS",
    "legal_description": "LEGAL_DESC",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "last_sale_price": "SALE_PRICE",
    "last_sale_date": "SALE_DATE",
}

COUNTY_SCRAPERS: Dict[str, Dict[str, Any]] = {
    "cochise_az": {
        "name": "Cochise County, AZ",
        "arcgis_root": "https://gis-cochise.opendata.arcgis.com",
        # Candidate service folder/service names, probed in order.
        "services": [
            ("Parcels", "Parcels", ["parcel", "ownership"]),
            ("Assessor", "Assessor", ["parcel", "ownership"]),
            ("Hosted", "Hosted", ["parcel", "ownership"]),
        ],
        "fields": _DEFAULT_FIELDS,
        "defaults": {"county_state": "Arizona"},
        "where": "1=1",
        "html_search_url": "https://parcelinquirytreasurer.cochise.az.gov/Main/ParcelSearch",
        "delinquent_list_url": "https://www.cochise.az.gov/treasurer",
        "verified": False,
        "status": "Cochise has ArcGIS Hub + Treasurer Parcel Inquiry w/ CSV export",
    },
    "mohave_az": {
        "name": "Mohave County, AZ",
        "arcgis_root": "https://az-mohave.opendata.arcgis.com",
        "services": [
            ("Parcels", "Parcels", ["parcel", "ownership"]),
            ("Hosted", "Hosted", ["parcel", "ownership"]),
        ],
        "fields": _DEFAULT_FIELDS,
        "defaults": {"county_state": "Arizona"},
        "where": "1=1",
        "html_search_url": "https://www.mohave.gov/departments/assessor/assessor-search/",
        "delinquent_list_url": "https://www.mohave.gov/departments/information-technology/gis-maps/",
        "verified": False,
        "status": "Mohave has ArcGIS Hub + GeoCortex viewer (2k-record export)",
    },
        "el_paso_tx": {
        "name": "El Paso County, TX",
        "data_mode": "flatfile",
        "open_gov_url": "https://epcad.org/OpenGovernment",
        "fields": _DEFAULT_FIELDS,
        "defaults": {"county_state": "Texas"},
        "where": "1=1",
        "verified": False,
        "status": "EPCAD publishes CAMA flat files (Properties/Owners/Values); probe confirms open_gov_url",
    },
}


def probe_county(county_id: str) -> List[ProbeResult]:
    cfg = COUNTY_SCRAPERS.get(county_id)
    if not cfg:
        return [ProbeResult(county_id, "registry", "", False, 0, "unknown county")]
    results: List[ProbeResult] = []
    data_mode = cfg.get("data_mode", "arcgis")
    if data_mode == "flatfile":
        og_url = cfg.get("open_gov_url")
        if og_url:
            # Test whether the OpenGovernment page is reachable and contains
            # the expected ~-delimited flat-file download links.
            try:
                from scrapers.flatfile import discover_downloads
                downloads = discover_downloads(og_url)
                ok = bool(downloads)
                results.append(ProbeResult(
                    county_id, "open_gov_url", og_url, ok, 200 if ok else 200,
                    f"flat-file downloads: {list(downloads.keys())}" if downloads else "no .txt links found",
                    verified=ok,
                ))
            except Exception as exc:
                results.append(ProbeResult(county_id, "open_gov_url", og_url, False, 0,
                                           f"error: {exc}", verified=False))
        return results
    root = cfg.get("arcgis_root")
    if root:
        r = probe(f"{root}/arcgis/rest/services?f=json", county_id,
                  "arcgis-root", expect="arcgis")
        results.append(r)
        # If reachable, try to locate a parcel layer in each candidate service
        if r.verified:
            for folder, service, keywords in cfg.get("services", []):
                layer = arcgis.find_layer(root, folder, service, keywords)
                results.append(ProbeResult(
                    county_id, f"layer:{folder}/{service}",
                    layer or f"{root}/arcgis/rest/services/{folder}/{service}",
                    layer is not None, 200 if layer else 404,
                    layer or "layer not found", verified=layer is not None))
    for key in ("html_search_url", "delinquent_list_url"):
        if cfg.get(key):
            results.append(probe(cfg[key], county_id, key, expect="http"))
    return results
