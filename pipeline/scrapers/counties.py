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
        # VERIFIED against Cad_Parcel_TaxInfo/FeatureServer/0 metadata
        # (28 fields observed in probe, run 2026-09-03)
        "fields": {
            "apn": "apn",
            "address": "situs_address",
            "lot_size_acres": "acres",
            "market_value": "fcv",
            "owner_name": "owner_name1",
            "owner_address": "address1",
            "owner_state": "state",
            "land_use": "use_code",
            "legal_description": "legal_text",
            "longitude": "geo_x",
            "latitude": "geo_y",
        },
        "defaults": {"county_state": "Arizona"},
        "where": "1=1",
        "html_search_url": "https://parcelinquirytreasurer.cochise.az.gov/Main/ParcelSearch",
        "delinquent_list_url": "https://www.cochise.az.gov/treasurer",
        "verified": True,
        "status": "Cochise ArcGIS Hub DCAT -> Cad_Parcel_TaxInfo FeatureServer (fields verified)",
    },
    "mohave_az": {
        "name": "Mohave County, AZ",
        "arcgis_root": "https://az-mohave.opendata.arcgis.com",
        "services": [
            ("Parcels", "Parcels", ["parcel", "ownership"]),
            ("Hosted", "Hosted", ["parcel", "ownership"]),
        ],
        # VERIFIED against mcgis.mohave.gov Mohave/MapServer/38 metadata
        # (70 fields observed in probe, run 2026-09-03)
        "fields": {
            "apn": "TAXPIN",
            "address": "SITE_ADDRESS",
            "owner_name": "OWNER",
            "owner_address": "MAILING_ADDRESS",
            "owner_state": "STATE",
            "market_value": "ASSESSED_FULL_CASH_VALUE",
        },
        "defaults": {"county_state": "Arizona"},
        "where": "1=1",
        "html_search_url": "https://www.mohave.gov/departments/assessor/assessor-search/",
        "delinquent_list_url": "https://www.mohave.gov/departments/information-technology/gis-maps/",
        "verified": True,
        "status": "Mohave ArcGIS Hub DCAT -> mcgis.mohave.gov MapServer/38 (fields verified)",
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
                from scrapers.flatfile import discover_downloads, discover_links_sample
                downloads = discover_downloads(og_url)
                ok = bool(downloads)
                detail = (f"flat-file downloads: {sorted(downloads.keys())}"
                          if downloads else
                          f"no data-file links found; sample hrefs: "
                          f"{discover_links_sample(og_url, 8)}")
                results.append(ProbeResult(
                    county_id, "open_gov_url", og_url, ok, 200,
                    detail, verified=ok,
                ))
            except Exception as exc:
                results.append(ProbeResult(county_id, "open_gov_url", og_url, False, 0,
                                           f"error: {exc}", verified=False))
        return results
    root = cfg.get("arcgis_root")
    if root:
        if "opendata.arcgis.com" in root:
            # Hub site: verify the DCAT feed yields a parcel feature layer
            layer = arcgis.find_layer_via_hub(root, ["parcel", "ownership"])
            results.append(ProbeResult(
                county_id, "arcgis-hub-dcat",
                f"{root}/api/feed/dcat-us/1.1.json",
                layer is not None, 200 if layer else 404,
                layer or "no parcel layer found in DCAT feed",
                verified=layer is not None,
                extras={"layer": layer or ""},
            ))
        else:
            r = probe(f"{root}/arcgis/rest/services?f=json", county_id,
                      "arcgis-root", expect="arcgis")
            results.append(r)
            # If reachable, try to locate a parcel layer in each candidate
            # service (non-hub REST roots only)
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
