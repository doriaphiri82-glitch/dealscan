"""Read-only, current-run production assertions. Never inserts test records."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import requests
from database_supabase import SupabaseDatabase
from persistence import PROPERTY_FIELDS, json_safe, record_key
from normalization import number, sale_date
from validation.evidence import verify_property_snapshot
from validation.gates import authorization_error, source_fingerprint, source_url


def get_backend():
    # Readiness checks can report missing credentials without initializing SQLite.
    from database import get_backend as backend
    return backend()


class SmokeFailure(RuntimeError):
    pass


def public_key() -> str:
    key = os.getenv('SUPABASE_PUBLISHABLE_KEY') or os.getenv('SUPABASE_ANON_KEY') or ''
    if key.startswith('sb_publishable_'): return key
    try:
        parts = key.split('.')
        payload = json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)))
        if len(parts)==3 and isinstance(payload,dict) and payload.get('role')=='anon': return key
    except (IndexError,ValueError,TypeError): pass
    raise SmokeFailure('Set a public SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY for the RLS smoke check')


def web_origin(value: str) -> str:
    try:
        url = urlsplit(value)
        if url.scheme=='https' and url.hostname and not (url.username or url.password or url.query or url.fragment or url.path.strip('/')):
            port=url.port
            host=url.hostname.lower()
            if ':' in host: host='['+host+']'
            return 'https://'+host+(f':{port}' if port and port!=443 else '')
    except ValueError: pass
    raise SmokeFailure('The deployed application URL must be an HTTPS origin')


def _get(url, *, params=None, headers=None):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=(5,20), allow_redirects=False)
    except requests.RequestException:
        raise SmokeFailure('Production read transport is unavailable') from None
    return response


def _require(condition, message):
    if not condition: raise SmokeFailure(message)


def _private_key_present(value):
    private = {'owner_name','owner_address','owner_state','raw_payload_canonical','raw_payload','normalized_payload','financial_evidence','ingestion_record_id','email'}
    if isinstance(value,dict): return bool(private.intersection(value)) or any(_private_key_present(item) for item in value.values())
    if isinstance(value,list): return any(_private_key_present(item) for item in value)
    return False


def verify_ingestion(run_id: int, *, county_id: str | None = None, max_records: int = 5000,
                     app_url: str | None = None, require_web: bool = False) -> dict:
    _require(type(run_id) is int and run_id>0, 'A positive integer run ID is required')
    _require(type(max_records) is int and 1<=max_records<=5000, 'Record limit must be 1–5000')
    db = get_backend()
    _require(isinstance(db,SupabaseDatabase), 'Production smoke requires explicit Supabase mode')
    db.init_db()
    runs = db._request('GET','ingestion_runs',params={'id':f'eq.{int(run_id)}','select':'*'}).json()
    _require(isinstance(runs,list) and len(runs)==1 and isinstance(runs[0],dict), 'The requested ingestion run does not exist')
    _require(runs[0].get('id')==int(run_id), 'Returned audit run does not match the requested run')
    run = runs[0]; cid = run['county_id']; metadata = run.get('metadata') or {}
    _require(county_id is None or cid==county_id, 'The smoke run belongs to a different county')
    _require(run['status']=='completed' and not metadata.get('audit_gap'), 'The requested run did not complete with intact audit')
    _require(all(type(run.get(field)) is int and run[field]>=0 for field in ('records_seen','records_normalized','records_persisted')), 'Run counters are not nonnegative integers')
    _require(0 < run['records_seen'] <= max_records and run['records_persisted'] > 0, 'The bounded run did not persist real source properties')
    if os.getenv('GITHUB_RUN_ID'):
        _require(metadata.get('workflow_run_id')==os.environ['GITHUB_RUN_ID'], 'Refusing to count an older workflow run as current ingestion')
    if os.getenv('GITHUB_RUN_ATTEMPT'):
        _require(metadata.get('workflow_attempt')==os.environ['GITHUB_RUN_ATTEMPT'], 'Refusing evidence from a previous workflow attempt')
    cfg = metadata.get('source_config') or {}
    authorization = metadata.get('source_authorization') or {}
    fingerprint = source_fingerprint(cfg)
    _require(cfg.get('county_id')==cid and source_url(cfg)==run.get('source_url'), 'Run source configuration does not match its county and URL')
    _require(not authorization_error(authorization,cfg), 'Run source authorization is incomplete or expired')
    _require(fingerprint==metadata.get('source_fingerprint')==metadata.get('authorized_source_fingerprint'), 'Run source fingerprint is not reproducible')
    _require(sale_date(metadata.get('source_validated_at'))==sale_date(authorization.get('last_validated_at')), 'Run validation timestamps do not agree')
    started,finished,validated = (sale_date(value) for value in (run.get('started_at'),run.get('finished_at'),metadata.get('source_validated_at')))
    _require(started is not None and finished is not None and validated is not None and validated-timedelta(minutes=5)<=started<=finished<=datetime.now(timezone.utc)+timedelta(minutes=5), 'Completed run timestamps are missing or inconsistent')
    records = db.get_ingestion_records(run_id)
    _require(isinstance(records,list) and all(isinstance(row,dict) for row in records), 'Invalid audit response')
    _require(all(row.get('run_id')==run_id and row.get('county_id')==cid and row.get('source_url')==run.get('source_url') for row in records), 'Audit records belong to a different run, county or source')
    _require(all(type(row.get('id')) is int and row['id']>0 for row in records), 'Audit identity is missing')
    _require(len({row['id'] for row in records})==len(records) and len({row.get('record_key') for row in records})==len(records), 'Duplicate source audit records')
    _require(all(row.get('record_key')==record_key(row.get('source_url'),row.get('source_record_id'),row.get('raw_payload')) for row in records), 'Audit key cannot be reproduced')
    _require(len(records)==run['records_seen'], 'Not every received source record has a durable audit decision')
    statuses = Counter(row.get('status') for row in records)
    counters = {'held':'records_held','candidate':'deals_persisted','rejected':'records_rejected','skipped':'records_skipped','failed':'records_failed'}
    _require(set(statuses).issubset(counters), 'Completed audit contains nonterminal source records')
    _require(all(type(run.get(counter)) is int and run[counter]>=0 and statuses[status]==run[counter] for status,counter in counters.items()), 'Run outcome counters disagree with its audit records')
    _require(not statuses['failed'], 'A completed run contains failed source records')
    linked_rows = [row for row in records if row.get('property_id') is not None]
    _require(all(type(row['property_id']) is int and row['property_id']>0 and row.get('status') in {'held','candidate'} for row in linked_rows), 'Invalid persisted source decision or property link')
    linked = {row['property_id']:row for row in linked_rows}
    _require(len(linked)==len(linked_rows)==run['records_persisted'], 'Persisted property count does not match this run audit')
    properties = []
    ids = sorted(linked)
    for offset in range(0,len(ids),250):
        select = 'id,'+','.join(PROPERTY_FIELDS)
        properties.extend(db._request('GET','properties',params={'id':'in.('+','.join(str(int(i)) for i in ids[offset:offset+250])+')','select':select}).json())
    _require(all(isinstance(prop,dict) and type(prop.get('id')) is int for prop in properties), 'Invalid persisted property response')
    _require(len(properties)==len(linked) and {prop['id'] for prop in properties}==set(linked), 'Missing, duplicated or unexpected source-audited primary properties')
    for prop in properties:
        try: verify_property_snapshot(prop,linked[prop['id']],cfg)
        except ValueError as exc: raise SmokeFailure(str(exc)) from None
    result = {'scope':'current_run','run_id':int(run_id),'county_id':cid,'status':'verified',
              'records_seen':run['records_seen'],'properties_verified':len(properties),
              'audit_records':len(records),'web_api':'not_checked'}
    if app_url or require_web:
        public = verify_public_api(db, app_url or '')
        result.update(web_api='verified',available_verified=public['available_verified'])
    return result


def verify_public_api(db: SupabaseDatabase, app_url: str, *, expected_contact: str | None = None) -> dict:
    """Read-only RLS/API assertions; does not authorize or ingest any source."""
    origin = web_origin(app_url)
    key = public_key()
    headers = {'apikey':key}
    if not key.startswith('sb_publishable_'): headers['Authorization']='Bearer '+key
    # No status filter: this actually exercises the deployed RLS predicate.
    response = _get(db.base+'/deals',params={'select':'verification_status,status,verified_at,verification_expires_at','limit':'5'},headers=headers)
    _require(response.status_code==200,'Anonymous verified read failed')
    rows = response.json()
    _require(isinstance(rows,list) and all(_current_public_row(row) for row in rows),'RLS exposed an unverified or expired assessment')
    for table,column in [('properties','owner_name'),('ingestion_records','raw_payload')]:
        response = _get(db.base+'/'+table,params={'select':column,'limit':'1'},headers=headers)
        _require(response.status_code in (401,403),'A private database column is readable with the public key')
    response = _get(origin+'/api/health')
    _require(response.status_code==200 and response.json().get('database')=='ok','Deployed API health check failed')
    _require(web_origin(response.json().get('database_origin',''))==web_origin(db.url), 'Deployed API is configured for a different database project')
    response = _get(origin+'/api/deals',params={'limit':'5'})
    _require(response.status_code==200,'Deployed public opportunities API failed')
    body = response.json(); deals = body.get('deals')
    _require(isinstance(deals,list) and body.get('meta',{}).get('storage_source')=='supabase','Public API is not reading the configured database')
    _require(not _private_key_present(body),'Public API exposed private data')
    expected = db.get_top_deals(limit=5,min_score=0)
    verify_api_snapshot(expected,deals)
    if 'count' in body: _require(type(body['count']) is int and body['count']==len(deals), 'API count differs from returned records')
    if expected_contact:
        privacy = _get(origin+'/privacy')
        _require(privacy.status_code == 200 and 'text/html' in privacy.headers.get('content-type',''), 'Deployed privacy notice is unavailable')
        _require('mailto:'+expected_contact in privacy.text, 'Deployed operator contact does not match the configured contact')
    return {'status':'verified','scope':'public_boundary_read_only','available_verified':len(deals),'operator_contact_checked':bool(expected_contact)}


API_NUMERIC_FIELDS = ('deal_score','asking_price','estimated_costs','estimated_arv_low','estimated_arv_high',
    'estimated_profit_low','estimated_profit_high','recommended_offer_low','recommended_offer_high',
    'valuation_confidence','lot_size_acres','latitude','longitude')
API_TEXT_FIELDS = ('address','zoning','source_record_id','source_url','valuation_basis','valuation_model','data_freshness')


def _current_public_row(row: dict) -> bool:
    if not isinstance(row,dict): return False
    verified,expires = sale_date(row.get('verified_at')),sale_date(row.get('verification_expires_at'))
    now = datetime.now(timezone.utc)
    return row.get('verification_status')=='verified' and row.get('status')=='discovered' and verified is not None and expires is not None and verified<=now+timedelta(minutes=5) and now<expires<=verified+timedelta(days=7)


def verify_api_snapshot(expected: list[dict],actual: list[dict]) -> None:
    """Compare values, not merely matching parcel IDs; no field values in errors."""
    _require(all(_current_public_row(row) for row in actual), 'Public API exposed an unverified or expired assessment')
    _require(all(isinstance(row.get('county_id'),str) and isinstance(row.get('apn'),str) for row in [*expected,*actual]), 'Public parcel identity is missing')
    indexed = {(row['county_id'],row['apn']):row for row in expected}
    actual_keys = {(row['county_id'],row['apn']) for row in actual}
    _require(len(indexed)==len(expected) and len(actual_keys)==len(actual) and actual_keys==set(indexed), 'Public API and current verified database snapshot disagree')
    for row in actual:
        stored = indexed[(row['county_id'],row['apn'])]
        for key in API_NUMERIC_FIELDS:
            wanted,got = stored.get(key),row.get(key)
            same = got is None if wanted is None else number(wanted) is not None and number(got)==number(wanted)
            _require(same,'Public API value differs from verified database: '+key)
        for key in API_TEXT_FIELDS:
            if key in stored: _require(row.get(key)==stored[key], 'Public API value differs from verified database: '+key)
        for key in ('verified_at','verification_expires_at'):
            _require(sale_date(row.get(key))==sale_date(stored.get(key)), 'Public API verification timestamps differ from the database')
