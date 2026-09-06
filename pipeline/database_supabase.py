"""Supabase/PostgREST persistence with scoped audit, retries and atomic upserts."""
from __future__ import annotations

import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import requests
from normalization import sale_date
from persistence import (AuditRunNotFound, COMP_FIELDS, PUBLIC_COMP_FIELDS, PUBLIC_DEAL_FIELDS, PUBLIC_PROPERTY_FIELDS, STATUS_MAP,
                         audit_record, audit_records, deal_payload, json_safe, now, property_payload, run_payload)

log = logging.getLogger(__name__)


class SupabaseDatabase:
    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        self.url = (url or os.getenv('SUPABASE_URL', '')).rstrip('/')
        self.key = key or os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
        if not self.url or not self.key:
            raise RuntimeError('Supabase backend requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY')
        parsed = urlsplit(self.url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise RuntimeError('SUPABASE_URL must be an HTTPS origin without credentials or query parameters')
        self.base = self.url + '/rest/v1'
        self.headers = {'apikey': self.key, 'Authorization': f'Bearer {self.key}', 'Content-Type': 'application/json'}
        if self.key.startswith('sb_secret_'): self.headers.pop('Authorization',None)
        self.timeout = max(1, min(float(os.getenv('SUPABASE_DB_TIMEOUT', '30')), 120))
        self.session = requests.Session()
        self._counties: dict[str, dict | None] = {}
        self._active: dict | None = None
        self.audit_failures: list[str] = []
        self._schema_checked = False
        self._active_checked_at = 0.0

    def _request(self, method: str, table: str, **kwargs) -> requests.Response:
        headers = kwargs.pop('headers', None) or self.headers
        retryable = method in {'GET', 'PATCH', 'DELETE'} or bool((kwargs.get('params') or {}).get('on_conflict')) or table in {'rpc/replace_deal_comps', 'rpc/hold_deals_for_parcels'}
        for attempt in range(3 if retryable else 1):
            try:
                response = self.session.request(method, f'{self.base}/{table}', headers=headers,
                    timeout=(min(5, self.timeout), self.timeout), allow_redirects=False, **kwargs)
            except requests.RequestException as exc:
                if retryable and attempt < 2:
                    time.sleep(2 ** attempt); continue
                raise RuntimeError(f'Supabase {method} {table} transport failed ({type(exc).__name__})') from None
            if response.status_code in {429, 500, 502, 503, 504} and retryable and attempt < 2:
                retry_after = response.headers.get('Retry-After', '')
                time.sleep(min(30, int(retry_after)) if retry_after.isdigit() else 2 ** attempt)
                continue
            if not response.ok or 300 <= response.status_code < 400:
                # PostgreSQL error bodies may contain owner names, values or SQL.
                # Never echo those bodies or credentials into Actions logs.
                raise RuntimeError(f'Supabase {method} {table} failed (HTTP {response.status_code})')
            return response
        raise RuntimeError('Supabase retry budget exhausted')

    def init_db(self) -> None:
        # Schema changes are migrations, not a no-op disguised as initialization.
        if self._schema_checked: return
        required = {'counties': 'county_id', 'properties': 'id,source_record_id,source_payload_hash,vacancy_status',
                    'deals': 'id,financial_evidence,ingestion_record_id,revision,verification_expires_at', 'comps': 'id,source_url,ingestion_record_id',
                    'ingestion_runs': 'id,run_key,heartbeat_at,finished_at', 'ingestion_records': 'id,record_key,field_mapping,raw_payload_canonical'}
        for table, fields in required.items():
            self._request('GET', table, params={'select': fields, 'limit': '0'})
        self._schema_checked = True

    def warn_audit(self, operation: str, exc: Exception) -> None:
        message = f'{operation}: {type(exc).__name__}'
        self.audit_failures.append(message)
        log.warning('Ingestion audit unavailable (%s); primary data retained, publication held', message)

    @staticmethod
    def county_payload(county: dict) -> dict:
        cid = str(county.get('county_id') or '').strip()
        name = str(county.get('county_name') or '').strip()
        if not cid or not name: raise ValueError('County metadata requires county_id and county_name')
        known = {'county_id','county_name','state','state_fips','county_fips','coverage_status','data_source_type',
                 'gis_url','parcel_source_url','arcgis_layer_url','source_vendor','scraper_type','field_mapping',
                 'verification_status','validation_status','data_freshness','discovery_attempted_at','last_successful_run',
                 'last_run_status','last_run_error','record_count','qualified_count','published_count','persisted_count','notes'}
        payload = {key: county.get(key) for key in known}
        payload.update(county_id=cid, county_name=name, field_mapping=county.get('field_mapping') or {},
                       extra={**(county.get('extra') or {}), **{key:value for key,value in county.items() if key not in known and key != 'extra'}})
        return json_safe(payload)

    def upsert_county(self, county: dict) -> None:
        self.upsert_counties([county])

    def upsert_counties(self, counties: list[dict]) -> int:
        payloads = [self.county_payload(county) for county in counties]
        changed = [payload for payload in payloads if self._counties.get(payload['county_id']) != payload]
        for offset in range(0,len(changed),100):
            batch = changed[offset:offset+100]
            self._request('POST','counties',params={'on_conflict':'county_id'},
                          headers={**self.headers,'Prefer':'resolution=merge-duplicates'},json=batch)
            for payload in batch: self._counties[payload['county_id']] = payload
        return len(changed)

    def get_counties(self) -> list[dict]:
        counties = []
        for offset in range(0,6000,1000):
            rows = self._request('GET','counties',params={'select':'*','order':'county_id.asc','offset':str(offset),'limit':'1000'}).json()
            for row in rows:
                counties.append({**(row.get('extra') or {}), **{key:value for key,value in row.items() if key not in {'extra','created_at','updated_at'}}})
            if len(rows)<1000: return counties
        raise RuntimeError('County registry exceeds bounded read limit')

    def ensure_county(self, county: dict) -> None:
        cid = str(county.get('county_id') or '')
        if cid in self._counties:
            return
        rows = self._request('GET', 'counties', params={'county_id': f'eq.{cid}', 'select': 'county_id'}).json()
        if not rows:
            self.upsert_county(county)
        else:
            self._counties[cid] = None

    def record_ingestion_run(self, county_id: str, status: str, counts: dict, error: str = '',
                             source_url: str | None = None, metadata: dict | None = None, run_key: str | None = None) -> int:
        payload = run_payload(county_id, status, counts, error, metadata)
        payload.update(run_key=run_key or str(uuid.uuid4()), source_url=source_url,
                       run_type='scheduled' if os.getenv('GITHUB_ACTIONS') else 'manual')
        rows = self._request('POST', 'ingestion_runs', params={'on_conflict': 'run_key'},
                headers={**self.headers, 'Prefer': 'resolution=ignore-duplicates,return=representation'}, json=payload).json()
        if not rows:
            rows = self._request('GET', 'ingestion_runs', params={'run_key': f'eq.{payload["run_key"]}', 'select': 'id'}).json()
        if not rows: raise RuntimeError('Ingestion run insert returned no row')
        return int(rows[0]['id'])

    def update_ingestion_run(self, run_id: int, county_id: str, status: str, counts: dict, error: str = '', metadata: dict | None = None) -> int:
        active = self._active if self._active and self._active['id'] == run_id and self._active['county_id'] == county_id else {}
        payload = run_payload(county_id, status, counts, error, {**active.get('metadata',{}), **(metadata or {})})
        rows = self._request('PATCH', 'ingestion_runs', params={'id': f'eq.{run_id}', 'county_id': f'eq.{county_id}', 'status': 'eq.running'},
                headers={**self.headers, 'Prefer': 'return=representation'}, json=payload).json()
        if not rows:
            existing = self._request('GET', 'ingestion_runs', params={'id': f'eq.{run_id}', 'county_id': f'eq.{county_id}', 'select': 'id,status'}).json()
            if not existing: raise AuditRunNotFound('Active ingestion run no longer exists')
            if existing[0]['status'] != STATUS_MAP[status]:
                raise RuntimeError('Ingestion run was already finalized with a different outcome')
        if status == 'running' and self._active: self._active['metadata'] = payload['metadata']
        if status != 'running': self.clear_active_run()
        return int(run_id)

    def clear_active_run(self) -> None:
        self._active = None
        os.environ.pop('DEALSCAN_ACTIVE_AUDIT_RUN_ID', None)

    def active_run_id(self, county_id: str) -> int | None:
        return self._active['id'] if self._active and self._active['county_id'] == county_id else None

    def recover_stale_runs(self, county_id: str) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self._request('PATCH', 'ingestion_runs', params={'county_id': f'eq.{county_id}', 'status': 'eq.running', 'heartbeat_at': f'lt.{cutoff}'},
                      json={'status': 'failed', 'finished_at': now(), 'error_message': 'Stale heartbeat; interrupted ingestion requires retry'})

    def ensure_active_ingestion_run(self, county_id: str, source_url: str | None = None) -> int:
        if self._active and self._active['county_id'] == county_id and self._active.get('source_url') == source_url:
            if time.monotonic() - self._active_checked_at < 30:
                return int(self._active['id'])
            os.environ['DEALSCAN_ACTIVE_AUDIT_RUN_ID'] = str(self._active['id'])
        active = os.getenv('DEALSCAN_ACTIVE_AUDIT_RUN_ID')
        self.clear_active_run()
        if active and active.isdigit():
            rows = self._request('GET', 'ingestion_runs', params={'id': f'eq.{active}', 'county_id': f'eq.{county_id}', 'status': 'eq.running', 'select': 'id,county_id,source_url,heartbeat_at,metadata'}).json()
            if rows:
                heartbeat = sale_date(rows[0].get('heartbeat_at'))
                if rows[0].get('source_url') == source_url and heartbeat and datetime.now(timezone.utc) - timedelta(hours=2) <= heartbeat <= datetime.now(timezone.utc) + timedelta(minutes=5):
                    self._active = rows[0]
        if not self._active:
            self.recover_stale_runs(county_id)
            run_id = self.record_ingestion_run(county_id, 'running', {}, source_url=source_url,
                metadata={'workflow_run_id': os.getenv('GITHUB_RUN_ID'), 'workflow_attempt': os.getenv('GITHUB_RUN_ATTEMPT')})
            self._active = {'id': run_id, 'county_id': county_id, 'source_url': source_url,
                            'metadata': {'workflow_run_id': os.getenv('GITHUB_RUN_ID'), 'workflow_attempt': os.getenv('GITHUB_RUN_ATTEMPT')}}
        self._active_checked_at = time.monotonic()
        os.environ['DEALSCAN_ACTIVE_AUDIT_RUN_ID'] = str(self._active['id'])
        return int(self._active['id'])

    def record_ingestion_records(self, run_id: int, county_id: str, records: list[dict]) -> int:
        values = audit_records(run_id,county_id,records)
        for start in range(0, len(values), 250):
            self._request('POST', 'ingestion_records', params={'on_conflict': 'run_id,record_key'},
                headers={**self.headers, 'Prefer': 'resolution=merge-duplicates'}, json=values[start:start + 250])
        return len(values)

    def get_ingestion_records(self, run_id: int, include_payloads: bool = True) -> list[dict]:
        records = []
        select = '*' if include_payloads else 'id,record_key,source_url,source_record_id,property_id'
        for offset in range(0, 11000, 1000):
            rows = self._request('GET', 'ingestion_records', params={'run_id': f'eq.{run_id}', 'select': select, 'order': 'id.asc', 'limit': '1000', 'offset': str(offset)}).json()
            records.extend(rows)
            if len(rows) < 1000: return records
        raise RuntimeError('Ingestion audit exceeds the bounded read limit')

    def save_property(self, data: dict) -> int:
        if data.get('_county_metadata'):
            self.upsert_county(data['_county_metadata'])
        else:
            self.ensure_county({'county_id': data['county_id'], 'county_name': data.get('county_name') or data['county_id']})
        payload = property_payload(data)
        rows = self._request('POST', 'properties', params={'on_conflict': 'apn,county_id'},
                headers={**self.headers, 'Prefer': 'resolution=merge-duplicates,return=representation'}, json=payload).json()
        if not rows: raise RuntimeError('Property upsert returned no row')
        property_id = int(rows[0]['id'])
        # A database trigger atomically revokes publication when the source payload changes.
        if not data.get('_defer_audit'):
            try:
                run_id = self.ensure_active_ingestion_run(data['county_id'], data.get('source_url'))
                self.record_ingestion_records(run_id, data['county_id'], [{
                    'source_record_id': payload['source_record_id'], 'source_url': data.get('source_url'),
                    'raw_payload': data.get('_raw_payload') or {}, 'normalized_payload': data,
                    'property_id': property_id, 'status': 'persisted'}])
            except Exception as exc:
                self.warn_audit('property_audit', exc)
                self.clear_active_run()
        return property_id

    def hold_deal_for_property(self, property_id: int) -> None:
        self._request('PATCH', 'deals', params={'property_id': f'eq.{property_id}', 'verification_status': 'eq.verified'},
                      json={'verification_status': 'pending_review', 'verified_at': None})

    def hold_deals_for_parcels(self, county_id: str, apns: list[str]) -> None:
        apns = sorted(set(apns))
        for offset in range(0, len(apns), 250):
            self._request('POST', 'rpc/hold_deals_for_parcels', json={'p_county_id': county_id, 'p_apns': apns[offset:offset+250]})

    def hold_deal_for_parcel(self, county_id: str, apn: str) -> None:
        rows = self._request('GET', 'properties', params={'apn': f'eq.{apn}', 'county_id': f'eq.{county_id}', 'select': 'id', 'limit': '1'}).json()
        if rows: self.hold_deal_for_property(int(rows[0]['id']))

    def save_deal(self, data: dict) -> int:
        rows = self._request('POST', 'deals', params={'on_conflict': 'property_id'},
                headers={**self.headers, 'Prefer': 'resolution=merge-duplicates,return=representation'}, json=deal_payload(data)).json()
        if not rows: raise RuntimeError('Deal upsert returned no row')
        deal_id = int(rows[0]['id'])
        if data.get('ingestion_record_id'):
            try:
                self._request('PATCH', 'ingestion_records', params={'id': f'eq.{data["ingestion_record_id"]}', 'property_id': f'eq.{data["property_id"]}'}, json={'deal_id': deal_id})
            except Exception as exc: self.warn_audit('link_deal', exc)
        return deal_id

    def save_comps(self, deal_id: int, comps: list[dict]) -> int:
        from validation.publication import validate_comp_payloads
        payload = validate_comp_payloads(comps)
        response = self._request('POST', 'rpc/replace_deal_comps', json={'p_deal_id': int(deal_id), 'p_comps': json_safe(payload)})
        return int(response.json())

    def get_deal_comps(self, deal_id: int) -> list[dict]:
        return self._request('GET', 'comps', params={'deal_id': f'eq.{deal_id}', 'select': ','.join(COMP_FIELDS), 'order': 'distance_miles.asc'}).json()

    def get_top_deals(self, limit: int = 10, min_score: int = 40, county_id: str | None = None) -> list[dict]:
        params = {'status': 'eq.discovered', 'verification_status': 'eq.verified', 'verification_expires_at': f'gt.{now()}', 'deal_score': f'gte.{int(min_score)}',
                  'select': f'{",".join(PUBLIC_DEAL_FIELDS)},properties!inner({",".join(PUBLIC_PROPERTY_FIELDS)}),comps({",".join(PUBLIC_COMP_FIELDS)})',
                  'order': 'deal_score.desc,id.asc', 'limit': str(max(1, min(int(limit), 100)))}
        if county_id: params['properties.county_id'] = f'eq.{county_id}'
        rows = self._request('GET', 'deals', params=params).json()
        return [{**{key: value for key, value in row.items() if key != 'properties'}, **row.get('properties', {})} for row in rows]

    def get_deal_for_verification(self, deal_id: int) -> dict | None:
        rows = self._request('GET', 'deals', params={'id': f'eq.{deal_id}', 'select': '*,properties!inner(*),comps(*)'}).json()
        return rows[0] if rows else None

    def verify_deal(self, deal_id: int) -> dict:
        from validation.publication import verify_persisted_deal
        deal = self.get_deal_for_verification(deal_id)
        if not deal: raise ValueError('Deal not found')
        record_id = deal.get('ingestion_record_id')
        records = self._request('GET', 'ingestion_records', params={'id': f'eq.{record_id}', 'select': '*'}).json() if record_id else []
        if not records: raise ValueError('Deal has no persisted source audit')
        run_id = records[0]['run_id']
        run = self._request('GET', 'ingestion_runs', params={'id': f'eq.{run_id}', 'select': '*'}).json()[0]
        result = verify_persisted_deal(deal, self.get_ingestion_records(run_id), run)
        rows = self._request('PATCH', 'deals', params={'id': f'eq.{deal_id}', 'revision': f'eq.{deal["revision"]}'},
                      headers={**self.headers, 'Prefer': 'return=representation'},
                      json={'verification_status': 'verified', 'verified_at': now()}).json()
        if not rows: raise RuntimeError('Deal changed during verification')
        result['verification_expires_at'] = rows[0].get('verification_expires_at')
        return result

    def get_subscribers(self, tier: str | None = None) -> list[dict]:
        params = {'is_active': 'eq.true', 'consented_at': 'not.is.null', 'select': '*'}
        if tier: params['tier'] = f'eq.{tier}'
        return self._request('GET', 'subscribers', params=params).json()

    def add_waitlist_entry(self, email: str, source: str = 'unknown') -> None:
        self._request('POST', 'waitlist', params={'on_conflict': 'email'}, headers={**self.headers, 'Prefer': 'resolution=ignore-duplicates'}, json={'email': email, 'source': source})
