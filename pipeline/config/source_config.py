"""Resolve a single effective source configuration for validation and ETL."""
from __future__ import annotations
from config.counties.national_registry import PILOT_COUNTIES
from config.counties.registry import get_county
from scrapers.counties import COUNTY_SCRAPERS

PILOT_SOURCE_KEYS = ('arcgis_layer_url', 'arcgis_root', 'gis_url', 'parcel_source_url',
                     'data_source_type', 'source_vendor', 'scraper_type', 'authority_evidence_url',
                     'authority_reviewed', 'authority_source_url', 'source_county_geoid', 'geoid')


def county_config(county_id: str, county: dict | None = None) -> dict:
    county = county if county is not None else (get_county(county_id) or {})
    cfg = {**county, **(COUNTY_SCRAPERS.get(county_id) or {})}
    pilot = PILOT_COUNTIES.get(county_id)
    if pilot:
        for key in PILOT_SOURCE_KEYS:
            if pilot.get(key) is not None:
                cfg[key] = pilot[key]
    if not cfg:
        return {}
    cfg['county_id'] = county_id
    cfg.setdefault('fields', county.get('field_mapping') or {})
    if cfg.get('arcgis_layer_url'):
        cfg.update(arcgis_root=cfg['arcgis_layer_url'], data_mode='arcgis', scraper_type='arcgis')
    elif cfg.get('data_url'):
        cfg.setdefault('scraper_type', 'flatfile')
    return cfg
