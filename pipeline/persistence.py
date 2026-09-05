"""Shared persistence contracts. Source verification never authorizes publication."""
from __future__ import annotations
import hashlib
import json
import math
from datetime import date, datetime, timezone
from normalization import boolean, number

PUBLIC_DEAL_FIELDS = ('id','property_id','deal_score','asking_price','asking_price_basis','estimated_arv_low',
    'estimated_arv_high','estimated_costs','estimated_profit_low','estimated_profit_high','recommended_offer_low',
    'recommended_offer_high','motivation_signals','status','source','source_url','source_vendor','source_quality',
    'verification_status','data_freshness','valuation_basis','valuation_confidence','discovered_at','updated_at',
    'verified_at','verification_expires_at','valuation_model')

PROPERTY_FIELDS = ('apn', 'county_id', 'address', 'lot_size_acres', 'assessed_value', 'market_value',
    'owner_name', 'owner_address', 'owner_state', 'tax_amount', 'tax_delinquent_years', 'year_acquired',
    'zoning', 'land_use', 'has_improvements', 'legal_description', 'latitude', 'longitude',
    'source_url', 'source_record_id', 'source_fingerprint', 'source_payload_hash', 'vacancy_status', 'vacancy_evidence', 'last_seen_at')
DEAL_FIELDS = ('property_id', 'deal_score', 'asking_price', 'asking_price_basis', 'estimated_arv_low',
    'estimated_arv_high', 'estimated_costs', 'estimated_profit_low', 'estimated_profit_high',
    'recommended_offer_low', 'recommended_offer_high', 'motivation_signals', 'motivation_score',
    'market_velocity', 'competition_level', 'status', 'notes', 'source', 'source_url', 'source_vendor',
    'source_quality', 'verification_status', 'data_freshness', 'valuation_basis', 'valuation_confidence',
    'financial_evidence', 'ingestion_record_id', 'verified_at', 'verification_expires_at', 'valuation_model')
COMP_FIELDS = ('address', 'sale_price', 'sale_date', 'distance_miles', 'lot_size_acres', 'price_per_acre',
               'source_url', 'source_record_id', 'source_apn', 'county_id', 'sale_qualified',
               'vacant_at_sale', 'ingestion_record_id')
PUBLIC_COMP_FIELDS = tuple(field for field in COMP_FIELDS if field != 'ingestion_record_id')
PUBLIC_PROPERTY_FIELDS = ('apn', 'county_id', 'address', 'lot_size_acres', 'zoning', 'latitude', 'longitude')
STATUS_MAP = {'running': 'running', 'ok': 'completed', 'completed': 'completed', 'degraded': 'partial',
              'partial': 'partial', 'error': 'failed', 'failed': 'failed', 'skipped': 'skipped'}


class AuditRunNotFound(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_safe(value):
    if isinstance(value, dict): return {str(key): json_safe(val) for key, val in value.items()}
    if isinstance(value, (tuple, list)): return [json_safe(val) for val in value]
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value): return str(value)
    return value


def property_payload(data: dict) -> dict:
    if not str(data.get('apn') or '').strip() or not data.get('county_id'):
        raise ValueError('Property requires county-scoped APN')
    payload = {key: data.get(key) for key in PROPERTY_FIELDS}
    payload.update(apn=str(data['apn']).strip(), source_record_id=data.get('_source_record_id') or data.get('source_record_id'),
                   has_improvements=boolean(data.get('has_improvements')), last_seen_at=now(),
                   vacancy_status=data.get('vacancy_status') or 'unknown', vacancy_evidence=data.get('vacancy_evidence') or {})
    for key in ('lot_size_acres', 'assessed_value', 'market_value', 'tax_amount', 'latitude', 'longitude'):
        payload[key] = number(payload.get(key))
    payload['source_payload_hash'] = hashlib.sha256(json.dumps(json_safe(data.get('_raw_payload') or {}), sort_keys=True).encode()).hexdigest()
    return json_safe(payload)


def deal_payload(data: dict) -> dict:
    payload = {key: data.get(key) for key in DEAL_FIELDS}
    payload.update(property_id=int(data['property_id']), deal_score=data.get('deal_score'),
                   status=data.get('status') or 'discovered', verification_status='pending_review',
                   verified_at=None, verification_expires_at=None, financial_evidence=data.get('financial_evidence') or {})
    if isinstance(payload.get('motivation_signals'), list):
        payload['motivation_signals'] = ','.join(payload['motivation_signals'])
    for field in ('asking_price','estimated_arv_low','estimated_arv_high','estimated_costs','estimated_profit_low',
                  'estimated_profit_high','recommended_offer_low','recommended_offer_high','motivation_score',
                  'market_velocity','valuation_confidence'):
        payload[field] = number(payload[field])
    # Ingestion always revokes previous publication pending verification of this
    # version. Only the separate verification operation may set verified.
    return json_safe(payload)


def run_payload(county_id: str, status: str, counts: dict, error: str = '', metadata: dict | None = None) -> dict:
    state = STATUS_MAP.get(status)
    if state is None: raise ValueError('Invalid ingestion status')
    payload = {'county_id': county_id, 'status': state, 'heartbeat_at': now(),
               'finished_at': None if state == 'running' else now(),
               'error_message': error or None, 'metadata': metadata or {}}
    for field, counter in {'records_seen': 'discovered', 'records_normalized': 'normalized',
                           'records_persisted': 'stored', 'records_rejected': 'rejected',
                           'records_held': 'held', 'records_skipped': 'skipped',
                           'deals_persisted': 'qualified', 'records_failed': 'failed', 'records_published': 'published'}.items():
        payload[field] = max(0, int(counts.get(counter) or 0))
    return payload


def record_key(source_url: str | None, source_id, raw) -> str:
    # County and run are part of the DB uniqueness constraint; the source URL
    # distinguishes identifiers from two different layers in the same county.
    identity = str(source_id) if source_id not in (None, '') else json.dumps(json_safe(raw or {}), sort_keys=True)
    return hashlib.sha256(f'{source_url or ""}\n{identity}'.encode()).hexdigest()


def audit_record(run_id: int, county_id: str, item: dict) -> dict:
    if item.get('status', 'normalized') not in {'normalized','persisted','candidate','held','rejected','skipped','failed'}:
        raise ValueError('Invalid ingestion record status')
    normalized = item.get('normalized_payload') or {}
    normalized = normalized if isinstance(normalized, dict) else {}
    source_id = item.get('source_record_id')
    if source_id in (None, ''): source_id = normalized.get('apn')
    source_url = item.get('source_url') or normalized.get('source_url')
    raw = item.get('raw_payload') or {}
    if not isinstance(raw,dict): raw={'value':raw}
    return json_safe({'run_id': int(run_id), 'county_id': county_id,
        'record_key': record_key(source_url, source_id, raw), 'source_record_id': str(source_id) if source_id is not None else None,
        'source_url': source_url, 'raw_payload': raw,
        'raw_payload_canonical': json.dumps(json_safe(raw),sort_keys=True),
        'normalized_payload': {key: val for key, val in normalized.items() if not key.startswith('_')},
        'field_mapping': item.get('field_mapping') or normalized.get('_field_sources') or {},
        'property_id': item.get('property_id'), 'deal_id': item.get('deal_id'),
        'status': item.get('status') or 'normalized', 'rejection_reason': item.get('rejection_reason'),
        'hold_reason': item.get('hold_reason')})
