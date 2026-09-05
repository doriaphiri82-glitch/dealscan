"""Durable source registry state across stateless production workflow runs.

The configured Supabase registry, even when empty, owns runtime authorization.
Local/pinned configuration can supply source candidates, never stale permission.
"""
from database import get_backend, _USE_SUPABASE
from config.counties import registry
from config.source_config import county_config
from validation.gates import authorization_error

CONFIG_FIELDS = {'county_id','county_name','state','state_fips','county_fips','geoid','geography_source_url',
                 'geography_vintage','assessor_url','gis_url','parcel_source_url','arcgis_layer_url','data_url',
                 'data_source_type','source_vendor','scraper_type','field_mapping','where','acreage_units',
                 'vacancy_codebook_url','vacant_use_codes','authority_evidence_url','authority_source_url',
                 'authority_reviewed','source_county_geoid'}


def pull_registry():
    if not _USE_SUPABASE: return
    db = get_backend(); db.init_db()
    remote = db.get_counties()
    local = registry._load_registry()
    candidates = {cid: {**{key:value for key,value in row.items() if key in CONFIG_FIELDS},
                        'validation_status':'pending','ingestion_authorized':False,
                        'verification_status':'discovered_not_verified','coverage_status':'tier_1'}
                  for cid,row in local.get('counties',{}).items()}
    for county in remote: candidates[county['county_id']] = county
    local['counties'] = candidates
    local.setdefault('meta',{})['runtime_source'] = 'supabase'
    registry._recompute_meta(local)
    registry._save_registry(local)


def push_registry():
    if not _USE_SUPABASE: return
    local = registry._load_registry()
    for county in local.get('counties',{}).values():
        if county.get('ingestion_authorized'):
            error = authorization_error(county,county_config(county['county_id'],county))
            if error:
                county.update(ingestion_authorized=False,authorized_source_fingerprint=None,authorization_error=error)
    get_backend().upsert_counties(list(local.get('counties',{}).values()))
    registry._save_registry(local)
