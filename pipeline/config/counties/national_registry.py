"""National county registry with a complete Census-backed geography universe."""
from __future__ import annotations
import csv, io, json, logging, re, zipfile
from datetime import datetime, timezone
from scrapers.base import fetch
from typing import Any, Dict
from .registry import register_counties_bulk, list_counties

PILOT_COUNTIES: Dict[str, Dict[str, Any]] = {
    "cochise_az": {"county_name":"Cochise County","state":"Arizona","state_fips":"04","county_fips":"003","geoid":"04003","population":125447,"data_source_type":"arcgis","assessor_url":"https://www.cochise.az.gov/departments/assessor","gis_url":"https://gis-cochise.opendata.arcgis.com","parcel_source_url":"https://services6.arcgis.com/Yxem0VOcqSy8T6TE/arcgis/rest/services/Cad_Parcel_TaxInfo/FeatureServer/0","arcgis_layer_url":"https://services6.arcgis.com/Yxem0VOcqSy8T6TE/arcgis/rest/services/Cad_Parcel_TaxInfo/FeatureServer/0","source_vendor":"esri","scraper_type":"arcgis","verification_status":"source_verified","coverage_status":"tier_3","notes":"Official Cochise County Cad_Parcel_TaxInfo FeatureServer; layer updated weekly; ETL run pending"},
    "mohave_az": {"county_name":"Mohave County","state":"Arizona","state_fips":"04","county_fips":"015","geoid":"04015","population":217853,"data_source_type":"arcgis","assessor_url":"https://www.mohave.gov/departments/assessor","gis_url":"https://az-mohave.opendata.arcgis.com","parcel_source_url":"https://mcgis.mohave.gov/arcgis/rest/services/PARCELS/MapServer/14","arcgis_layer_url":"https://mcgis.mohave.gov/arcgis/rest/services/PARCELS/MapServer/14","source_vendor":"esri","scraper_type":"arcgis","verification_status":"source_verified","coverage_status":"tier_3","notes":"Official Mohave County parcel MapServer/14; source fields verified 2026-09-03; ETL run pending"},
    "el_paso_tx": {"county_name":"El Paso County","state":"Texas","state_fips":"48","county_fips":"141","geoid":"48141","population":865424,"data_source_type":"arcgis","assessor_url":"https://www.epcad.org","gis_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","parcel_source_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","arcgis_layer_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","source_vendor":"esri","scraper_type":"arcgis","verification_status":"source_verified","coverage_status":"tier_3","notes":"EPCAD direct ArcGIS FeatureServer; source verified 2026-09-03; ETL run pending"},
}

# Reviewed pilot identities, not blanket trust in any ArcGIS search result.
for _cid, _pilot in PILOT_COUNTIES.items():
    _pilot.update(authority_reviewed=True, authority_source_url=_pilot['arcgis_layer_url'],
                  authority_evidence_url=_pilot['assessor_url'], source_county_geoid=_pilot['geoid'],
                  verification_status='discovered_not_verified', coverage_status='tier_1',
                  notes='Curated official pilot source; live validation and ingestion authorization required')

_STATE_NAMES={"01":"Alabama","02":"Alaska","04":"Arizona","05":"Arkansas","06":"California","08":"Colorado","09":"Connecticut","10":"Delaware","11":"District of Columbia","12":"Florida","13":"Georgia","15":"Hawaii","16":"Idaho","17":"Illinois","18":"Indiana","19":"Iowa","20":"Kansas","21":"Kentucky","22":"Louisiana","23":"Maine","24":"Maryland","25":"Massachusetts","26":"Michigan","27":"Minnesota","28":"Mississippi","29":"Missouri","30":"Montana","31":"Nebraska","32":"Nevada","33":"New Hampshire","34":"New Jersey","35":"New Mexico","36":"New York","37":"North Carolina","38":"North Dakota","39":"Ohio","40":"Oklahoma","41":"Oregon","42":"Pennsylvania","44":"Rhode Island","45":"South Carolina","46":"South Dakota","47":"Tennessee","48":"Texas","49":"Utah","50":"Vermont","51":"Virginia","53":"Washington","54":"West Virginia","55":"Wisconsin","56":"Wyoming"}
GAZETTEER_URL = 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip'
_STATE_NAMES['72'] = 'Puerto Rico'
_SOURCE_KEYS = ('arcgis_layer_url', 'parcel_source_url', 'gis_url', 'data_source_type', 'source_vendor',
                'scraper_type', 'assessor_url', 'authority_reviewed', 'authority_evidence_url',
                'authority_source_url', 'source_county_geoid')


def parse_gazetteer(text: str) -> Dict[str, Dict[str, Any]]:
    first = text.splitlines()[0]
    delimiter = '|' if '|' in first else '\t'
    rows = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not {'GEOID', 'NAME'} <= {str(key).strip() for key in rows.fieldnames or []}:
        raise ValueError('Census gazetteer is missing required columns')
    out = {}
    for raw in rows:
        row = {str(key).strip(): str(value or '').strip() for key, value in raw.items()}
        geoid, name = row.get('GEOID', ''), row.get('NAME', '')
        if not re.fullmatch(r'\d{5}', geoid) or not name or geoid[:2] not in _STATE_NAMES:
            raise ValueError('Invalid Census county geography')
        if geoid in out:
            raise ValueError('Duplicate Census county geography')
        out[geoid] = {'county_name': name, 'state': _STATE_NAMES[geoid[:2]], 'state_fips': geoid[:2],
                      'county_fips': geoid[2:], 'geoid': geoid, 'geography_source_url': GAZETTEER_URL,
                      'geography_vintage': '2025', 'verification_status': 'not_started',
                      'coverage_status': 'tier_0', 'notes': 'Census geography only; no parcel coverage implied'}
    return {f"{re.sub(r'[^a-z0-9]+', '_', row['county_name'].casefold()).strip('_')}_{row['state_fips']}_{row['county_fips']}": row for row in out.values()}


def discover_national_counties() -> Dict[str, Dict[str, Any]]:
    # A fixed, released geography file avoids an unreleased ACS year and the
    # Census data API's API-key requirement. Geography contains no opportunities.
    try:
        response = fetch(GAZETTEER_URL, ttl=30 * 86400, raw=True, respect_robots=False)
        if not response.ok or not isinstance(response.body, bytes):
            raise RuntimeError('Census gazetteer download failed')
        with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
            entries = [info for info in archive.infolist() if info.filename.endswith('.txt')]
            if len(entries) != 1 or entries[0].file_size > 5_000_000:
                raise ValueError('Unexpected Census archive size or contents')
            counties = parse_gazetteer(archive.read(entries[0]).decode('utf-8-sig'))
        if len(counties) < 3000 or {row['state_fips'] for row in counties.values()} != set(_STATE_NAMES):
            raise ValueError('Census county universe is incomplete')
        return counties
    except Exception as exc:
        logging.getLogger(__name__).warning('Census geography refresh unavailable (%s); retaining last known registry', type(exc).__name__)
        return {}


def _merge_pilot(cid: str, existing: dict) -> dict:
    pilot = PILOT_COUNTIES[cid]
    payload = {**pilot, **existing, 'county_id': cid}
    changed = any(existing.get(key) not in (None, pilot.get(key)) for key in ('arcgis_layer_url', 'parcel_source_url'))
    for key in (*_SOURCE_KEYS, 'county_name', 'state', 'state_fips', 'county_fips', 'geoid'):
        if key in pilot:
            payload[key] = pilot[key]
    if changed:
        payload.update(validation_status='pending', ingestion_authorized=False, validated_source_fingerprint=None,
                       authorized_source_fingerprint=None, verification_status='discovered_not_verified',
                       coverage_status='tier_1', notes=pilot['notes'])
    return payload


def ensure_national_counties() -> Dict[str, Dict[str, Any]]:
    from . import registry
    discovered = discover_national_counties()
    existing = {c['county_id']: c for c in list_counties()}
    by_geoid = {c['geoid']: cid for cid, c in existing.items() if c.get('geoid')}
    pilot_ids = {c['geoid']: cid for cid, c in PILOT_COUNTIES.items()}
    combined = dict(existing)
    for cid, geography in discovered.items():
        identity = pilot_ids.get(geography['geoid']) or by_geoid.get(geography['geoid']) or cid
        # Preserve all runtime state, authorization, retry scheduling and audit
        # fields. Updating Census names must not reset a successful ETL run.
        old = existing.get(identity) or existing.get(by_geoid.get(geography['geoid'])) or {}
        combined[identity] = {**geography, **old, 'county_id': identity}
        old_id = by_geoid.get(geography['geoid'])
        if old_id and old_id != identity:
            combined.pop(old_id, None)
    for cid in PILOT_COUNTIES:
        combined[cid] = _merge_pilot(cid, combined.get(cid) or {})
    saved = register_counties_bulk(list(combined.values()))
    # Drop duplicate geography keys only from this local registry; no DB delete.
    reg = registry._load_registry()
    reg['counties'] = {cid: saved[cid] for cid in combined}
    registry._recompute_meta(reg)
    if discovered:
        reg['meta'].update(universe_complete=True, universe_source=GAZETTEER_URL,
                           universe_refreshed_at=datetime.now(timezone.utc).isoformat())
    else:
        reg['meta']['universe_complete'] = bool(reg['meta'].get('universe_complete'))
    registry._save_registry(reg)
    return reg['counties']


def ensure_pilot_counties():
    existing = {c['county_id']: c for c in list_counties()}
    return register_counties_bulk([_merge_pilot(cid, existing.get(cid) or {}) for cid in PILOT_COUNTIES])
