"""
DealScan - National County Registry

Initial registry populated with the three existing pilot counties.
Additional counties can be added programmatically or via the expand CLI.
"""
from __future__ import annotations

from typing import Any, Dict

from .registry import register_county

# Existing pilot counties migrated from scrapers/counties.py.
# FIPS/GEOID are stable identifiers per the Census Bureau.

PILOT_COUNTIES: Dict[str, Dict[str, Any]] = {
    "cochise_az": {
        "county_name": "Cochise County",
        "state": "Arizona",
        "state_fips": "04",
        "county_fips": "003",
        "geoid": "04003",
        "population": 125_447,
        "data_source_type": "arcgis",
        "assessor_url": "https://www.cochise.az.gov/departments/assessor",
        "gis_url": "https://gis-cochise.opendata.arcgis.com",
        "parcel_source_url": "https://gis-cochise.opendata.arcgis.com/datasets/Cad_Parcel_TaxInfo",
        "source_vendor": "esri",
        "scraper_type": "arcgis",
        "verification_status": "verified",
        "coverage_status": "tier_4",
        "notes": "ArcGIS Hub DCAT -> Cad_Parcel_TaxInfo FeatureServer (fields verified 2026-09-03)",
    },
    "mohave_az": {
        "county_name": "Mohave County",
        "state": "Arizona",
        "state_fips": "04",
        "county_fips": "015",
        "geoid": "04015",
        "population": 217_853,
        "data_source_type": "arcgis",
        "assessor_url": "https://www.mohave.gov/departments/assessor",
        "gis_url": "https://az-mohave.opendata.arcgis.com",
        "parcel_source_url": "https://mohave.maps.arcgis.com",
        "source_vendor": "esri",
        "scraper_type": "arcgis",
        "verification_status": "verified",
        "coverage_status": "tier_4",
        "notes": "ArcGIS Hub DCAT -> mcgis.mohave.gov MapServer/38 (fields verified 2026-09-03)",
    },
    "el_paso_tx": {
        "county_name": "El Paso County",
        "state": "Texas",
        "state_fips": "48",
        "county_fips": "141",
        "geoid": "48141",
        "population": 865_424,
        "data_source_type": "arcgis",
        "assessor_url": "https://www.epcad.org",
        "gis_url": "https://services7.arcgis.com/HCMBmskOgOdHcxMC/arcgis/rest/services/EPCAD",
        "parcel_source_url": "https://services7.arcgis.com/HCMBmskOgOdHcxMC/arcgis/rest/services/EPCAD/FeatureServer/0",
        "source_vendor": "esri",
        "scraper_type": "arcgis",
        "verification_status": "verified",
        "coverage_status": "tier_4",
        "notes": "EPCAD ArcGIS Hub FeatureServer/0 (working 2026-09-03). Flatfile fallback blocked by Cloudflare.",
    },
}


def ensure_pilot_counties() -> None:
    for county_id, meta in PILOT_COUNTIES.items():
        entry = register_county(
            county_id=county_id,
            county_name=meta["county_name"],
            state=meta["state"],
            state_fips=meta["state_fips"],
            county_fips=meta["county_fips"],
            geoid=meta["geoid"],
            population=meta.get("population"),
            data_source_type=meta.get("data_source_type"),
            assessor_url=meta.get("assessor_url"),
            gis_url=meta.get("gis_url"),
            parcel_source_url=meta.get("parcel_source_url"),
            source_vendor=meta.get("source_vendor"),
            scraper_type=meta.get("scraper_type"),
            verification_status=meta.get("verification_status", "not_implemented"),
            coverage_status=meta.get("coverage_status", "tier_0"),
            notes=meta.get("notes", ""),
        )
