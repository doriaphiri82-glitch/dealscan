"""Live validation is not permission to ingest a different or unreviewed source."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from normalization import sale_date

MAX_VALIDATION_AGE = timedelta(days=7)


def source_url(cfg: dict) -> str:
    return str(cfg.get('arcgis_layer_url') or cfg.get('data_url') or cfg.get('parcel_source_url') or '').rstrip('/')


def source_fingerprint(cfg: dict) -> str:
    identity = {key: cfg.get(key) for key in ('where', 'acreage_units', 'vacancy_codebook_url', 'vacant_use_codes',
        'authority_reviewed', 'authority_evidence_url', 'authority_source_url', 'source_county_geoid')}
    identity['url'] = source_url(cfg)
    # Resolving source field casing does not alter its meaning.
    identity['fields'] = {key: [str(v).casefold() for v in value] if isinstance(value, (list, tuple)) else str(value).casefold()
                          for key, value in (cfg.get('fields') or cfg.get('field_mapping') or {}).items()}
    identity['where'] = cfg.get('where') or '1=1'
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def authority_verified(cfg: dict) -> bool:
    try:
        evidence = urlsplit(str(cfg.get('authority_evidence_url') or ''))
        source = urlsplit(source_url(cfg))
        return (cfg.get('authority_reviewed') is True and evidence.scheme == 'https' and bool(evidence.hostname)
                and source.scheme == 'https' and bool(source.hostname) and not source.username and not source.password
                and str(cfg.get('authority_source_url') or '').rstrip('/') == source_url(cfg)
                and bool(cfg.get('geoid')) and cfg.get('source_county_geoid') == cfg.get('geoid'))
    except ValueError:
        return False


def validation_error(county: dict, cfg: dict) -> str:
    if county.get('validation_status') != 'valid':
        return 'source_not_live_validated'
    if county.get('validated_source_fingerprint') != source_fingerprint(cfg):
        return 'source_changed_since_validation'
    validated_at = sale_date(county.get('last_validated_at'))
    now = datetime.now(timezone.utc)
    if validated_at is None or not now - MAX_VALIDATION_AGE <= validated_at <= now + timedelta(minutes=5):
        return 'source_validation_expired'
    if not county.get('validation_source_fields_checked') or not county.get('validation_pagination_checked') or not county.get('validation_sample_checked'):
        return 'source_validation_incomplete'
    return ''


def authorization_error(county: dict, cfg: dict) -> str:
    error = validation_error(county, cfg)
    if error:
        return error
    if not authority_verified(cfg):
        return 'source_authority_not_reviewed'
    if county.get('ingestion_authorized') is not True or county.get('authorized_source_fingerprint') != source_fingerprint(cfg):
        return 'source_not_authorized'
    return ''


def authorize_county(county_id: str) -> dict:
    from config.counties.registry import get_county, update_county
    from config.source_config import county_config
    county = get_county(county_id) or {}
    cfg = county_config(county_id, county)
    error = validation_error(county, cfg)
    if not error and not authority_verified(cfg):
        error = 'source_authority_not_reviewed'
    patch = {'ingestion_authorized': not bool(error), 'authorization_error': error or None,
             'authorized_source_fingerprint': source_fingerprint(cfg) if not error else None,
             'authorized_at': datetime.now(timezone.utc).isoformat() if not error else None}
    update_county(county_id, **patch)
    return {'county_id': county_id, 'authorized': not bool(error), 'error': error or None}


def authorize_validated_batch(limit: int = 25) -> dict:
    from config.counties.registry import list_counties
    candidates = [c for c in list_counties() if c.get('validation_status') == 'valid']
    results = [authorize_county(c['county_id']) for c in candidates[:max(0, min(limit, 100))]]
    return {'attempted': len(results), 'authorized': sum(result['authorized'] for result in results), 'results': results}
