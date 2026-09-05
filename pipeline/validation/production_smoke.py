"""Read-only, current-run production assertions. Never inserts test records."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from urllib.parse import urlsplit
import requests
from database import get_backend
from database_supabase import SupabaseDatabase
from persistence import json_safe
from normalization import normalize, sale_date, source_identity
from validation.gates import authorization_error, source_fingerprint, source_url


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
            return value.rstrip('/')
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
    private = {'owner_name','owner_address','owner_state','raw_payload','normalized_payload','financial_evidence','ingestion_record_id','email'}
    if isinstance(value,dict): return bool(private.intersection(value)) or any(_private_key_present(item) for item in value.values())
    if isinstance(value,list): return any(_private_key_present(item) for item in value)
    return False


def verify_ingestion(run_id: int, *, county_id: str | None = None, max_records: int = 5000,
                     app_url: str | None = None, require_web: bool = False) -> dict:
    db = get_backend()
    _require(isinstance(db,SupabaseDatabase), 'Production smoke requires explicit Supabase mode')
    db.init_db()
    runs = db._request('GET','ingestion_runs',params={'id':f'eq.{int(run_id)}','select':'*'}).json()
    _require(len(runs)==1, 'The requested ingestion run does not exist')
    _require(runs[0].get('id')==int(run_id), 'Returned audit run does not match the requested run')
    run = runs[0]; cid = run['county_id']; metadata = run.get('metadata') or {}
    _require(county_id is None or cid==county_id, 'The smoke run belongs to a different county')
    _require(run['status']=='completed' and not metadata.get('audit_gap'), 'The requested run did not complete with intact audit')
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
    _require(sale_date(run.get('finished_at')) is not None, 'Completed run has no completion timestamp')
    records = db.get_ingestion_records(run_id)
    _require(all(row.get('run_id')==int(run_id) for row in records), 'Audit records belong to a different run')
    linked = {row['property_id']:row for row in records if row.get('property_id') is not None}
    _require(len(linked)==run['records_persisted'], 'Persisted property count does not match this run audit')
    properties = []
    ids = sorted(linked)
    for offset in range(0,len(ids),250):
        select = 'id,apn,county_id,source_url,source_record_id,source_fingerprint,source_payload_hash'
        properties.extend(db._request('GET','properties',params={'id':'in.('+','.join(str(int(i)) for i in ids[offset:offset+250])+')','select':select}).json())
    _require(len(properties)==len(linked), 'Some source-audited primary properties are missing')
    for prop in properties:
        record = linked[prop['id']]
        _require(record.get('county_id')==prop.get('county_id')==cid, 'Cross-county provenance mismatch')
        _require(record.get('source_record_id') and record['source_record_id']==prop.get('source_record_id'), 'Source identity is missing or mismatched')
        _require(record.get('source_url')==prop.get('source_url')==run.get('source_url'), 'Source URLs do not agree')
        _require(record.get('raw_payload') and record.get('normalized_payload') and record.get('field_mapping'), 'A persisted property has incomplete source snapshots')
        digest = hashlib.sha256(json.dumps(json_safe(record['raw_payload']),sort_keys=True).encode()).hexdigest()
        _require(digest==prop.get('source_payload_hash'), 'Source payload changed after the selected run')
        _require(record['normalized_payload'].get('apn')==prop.get('apn'), 'Normalized parcel identity mismatch')
        _require(prop.get('source_fingerprint')==fingerprint, 'Property source fingerprint differs from authorized run')
        _require(source_fingerprint({**cfg,'fields':record['field_mapping']})==fingerprint, 'Audit mapping differs from authorized source mapping')
        normalized = normalize(record['raw_payload'],{**cfg,'fields':record['field_mapping']})
        _require(source_identity(record['raw_payload'],cfg,normalized)==record['source_record_id'], 'Source identity cannot be reproduced')
        _require(all(record['normalized_payload'].get(key)==value for key,value in normalized.items() if not key.startswith('_')), 'Normalized snapshot differs from raw source data')
    result = {'scope':'current_run','run_id':int(run_id),'county_id':cid,'status':'verified',
              'records_seen':run['records_seen'],'properties_verified':len(properties),
              'audit_records':len(records),'web_api':'not_checked'}
    if app_url or require_web:
        origin = web_origin(app_url or '')
        key = public_key()
        headers = {'apikey':key}
        if not key.startswith('sb_publishable_'): headers['Authorization']='Bearer '+key
        # No status filter: this actually exercises the deployed RLS predicate.
        response = _get(db.base+'/deals',params={'select':'verification_status,status','limit':'5'},headers=headers)
        _require(response.status_code==200,'Anonymous verified read failed')
        rows = response.json()
        _require(isinstance(rows,list) and all(row.get('verification_status')=='verified' and row.get('status')=='discovered' for row in rows),'RLS exposed an unverified assessment')
        for table,column in [('properties','owner_name'),('ingestion_records','raw_payload')]:
            response = _get(db.base+'/'+table,params={'select':column,'limit':'1'},headers=headers)
            _require(response.status_code in (401,403),'A private database column is readable with the public key')
        response = _get(origin+'/api/health')
        _require(response.status_code==200 and response.json().get('database')=='ok','Deployed API health check failed')
        response = _get(origin+'/api/deals',params={'limit':'5'})
        _require(response.status_code==200,'Deployed public opportunities API failed')
        body = response.json(); deals = body.get('deals')
        _require(isinstance(deals,list) and body.get('meta',{}).get('storage_source')=='supabase','Public API is not reading the configured database')
        _require(not _private_key_present(body),'Public API exposed private data')
        expected = {(row['county_id'],row['apn']) for row in db.get_top_deals(limit=5,min_score=0)}
        actual = {(row.get('county_id'),row.get('apn')) for row in deals}
        _require(expected==actual,'Public API and current verified database snapshot disagree')
        _require(all(row.get('verification_status')=='verified' for row in deals),'Public API exposed an unverified assessment')
        result.update(web_api='verified',available_verified=len(deals))
    return result
