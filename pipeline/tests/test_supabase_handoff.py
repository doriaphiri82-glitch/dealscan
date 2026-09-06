"""Offline Supabase management handoff contracts. No network; fixture shapes only."""
from __future__ import annotations
import pytest
from validation import supabase_handoff as sh

ORIGIN = 'https://dealscan-omega.vercel.app'
ALL_COLUMNS = {'counties': {'county_id', 'county_name', 'extra'},
               'properties': {'id', 'apn', 'county_id', 'source_record_id', 'source_payload_hash', 'vacancy_status'},
               'deals': {'id', 'property_id', 'financial_evidence', 'ingestion_record_id', 'revision',
                         'verification_expires_at', 'verification_status', 'verified_at'},
               'comps': {'id', 'deal_id', 'source_url', 'ingestion_record_id'},
               'subscribers': {'id', 'consented_at', 'unsubscribe_url', 'is_active'},
               'deliveries': {'id'}, 'waitlist': {'id'},
               'ingestion_runs': {'id', 'run_key', 'heartbeat_at', 'finished_at', 'status'},
               'ingestion_records': {'id', 'record_key', 'field_mapping', 'raw_payload_canonical'},
               'waitlist_request_limits': {'id', 'window_started_at'}}


def full_snapshot():
    fns = {'set_updated_at', 'finite_number', 'replace_deal_comps', 'hold_deals_for_parcels',
           'bump_deal_revision', 'distance_miles', 'require_publication_evidence',
           'revoke_changed_property_deals', 'revoke_changed_comp_deals', 'revoke_changed_audit_deals',
           'revoke_changed_run_deals', 'revoke_changed_county_deals', 'join_waitlist',
           'county_operational_snapshot', 'source_mapped_value', 'source_number', 'require_raw_source_evidence',
           'require_comparable_arithmetic', 'current_validation_proof', 'require_typed_source_validation',
           'revoke_changed_validation_proof'}
    trgs = {'counties_set_updated_at', 'properties_set_updated_at', 'deals_set_updated_at',
            'deals_require_raw_source_evidence', 'deals_require_comparable_arithmetic',
            'deals_require_a_typed_validation', 'counties_revoke_validation_proof'}
    return {'tables': {t: set(c) for t, c in ALL_COLUMNS.items()}, 'functions': fns, 'triggers': trgs,
            'policies': {'public read counties', 'public read published deals', 'public read deal properties',
                         'public read comps for published deals'},
            'indexes': {'idx_deals_verified_score'}, 'ledger_present': False,
            'counts': {t: 0 for t in sh.APP_TABLES}, 'function_flags': {'set_updated_at_search_path'},
            'rls_enabled': set(sh.APP_TABLES[:7])}


def test_project_ref_requires_canonical_supabase_origin():
    assert sh.project_ref('https://abcdefghijklmnop.supabase.co') == 'abcdefghijklmnop'
    for bad in ('http://ref.supabase.co', 'https://user:pw@ref.supabase.co', 'https://ref.supabase.co/rest',
                'https://example.com', '', 'https://ref.supabase.co/?x=1'):
        with pytest.raises(sh.HandoffFailure):
            sh.project_ref(bad)


def test_inspection_sql_is_provably_read_only():
    sh.assert_read_only_sql('select 1')
    sh.assert_read_only_sql('with x as (select 1) select * from x')
    for bad in ('select 1; select 2', 'select 1; drop table deals', 'insert into deals values (1)',
                'delete from deals', 'update deals set id=1', 'create index x on deals(id)' ):
        with pytest.raises(sh.HandoffFailure):
            sh.assert_read_only_sql(bad)


def test_every_repository_migration_has_registered_markers():
    files = sh.migration_files()
    assert len(files) == 11
    assert {f.name for f in files} == set(sh.MIGRATION_MARKERS)


def test_reconcile_pending_vs_applied_vs_inconsistent():
    files = [f.name for f in sh.migration_files()]
    empty = {'tables': {}, 'functions': set(), 'triggers': set(), 'policies': set(),
             'indexes': set(), 'function_flags': set()}
    recon = sh.reconcile(files, [], empty)
    assert recon['pending'] == files and recon['applicable'] == files
    recon = sh.reconcile(files, [], full_snapshot())
    assert recon['pending'] == [] and recon['inconsistent'] == []
    assert all(r['state'] == 'applied_markers' for r in recon['migrations'])
    ledger = [f.split('_')[0] for f in files[:5]]
    recon = sh.reconcile(files, ledger, full_snapshot())
    assert [r['state'] for r in recon['migrations'][:5]] == ['applied_ledger'] * 5
    stale = full_snapshot(); stale['triggers'] = set()
    recon = sh.reconcile(['20260905230000_raw_source_publication.sql'],
                         ['20260905230000'], stale)
    assert recon['inconsistent'] and recon['applicable'] == []


def test_marker_missing_is_specific():
    snap = full_snapshot()
    snap['functions'] = set()
    missing = sh.marker_missing(snap, '20260905200000_ingestion_integrity.sql')
    assert 'function:replace_deal_comps' in missing and 'table:ingestion_runs' not in missing


def test_auth_sanitize_and_verdict():
    loud = {'SITE_URL': ORIGIN, 'URI_ALLOW_LIST': ORIGIN + '/auth/callback,http://localhost:3000/**',
            'EXTERNAL_EMAIL_ENABLED': True, 'MAILER_AUTOCONFIRM': False, 'SMTP_PASS': 'SECRET', 'GOTRUE_KEY': 'SECRET2'}
    config = sh.sanitize_auth_config(loud)
    assert 'SECRET' not in str(config) and 'smtp' not in str(config).lower()
    verdict = sh.auth_verdict(config, ORIGIN)
    assert verdict['status'] == 'passed' and verdict['localhost_urls_present'] is True
    camel = sh.sanitize_auth_config({'site_url': 'http://localhost:3000', 'uri_allow_list': ['http://localhost:3000/**']})
    verdict = sh.auth_verdict(camel, ORIGIN)
    assert verdict['missing'] == ['site_url', 'callback_redirect_url']
    body = sh.auth_fix_body(camel, ORIGIN)
    assert body['SITE_URL'] == ORIGIN
    assert 'http://localhost:3000/**' in body['URI_ALLOW_LIST'] and ORIGIN + '/auth/callback' in body['URI_ALLOW_LIST']
    assert sh.auth_fix_body(sh.sanitize_auth_config(loud), ORIGIN) == {}


def test_required_columns_contract():
    assert sh.required_columns_status(full_snapshot())['status'] == 'passed'
    snap = full_snapshot(); snap['tables']['deals'] = {'id'}
    status = sh.required_columns_status(snap)
    assert status['status'] == 'failed' and 'deals.revision' in status['missing']


def rows_from_snapshot(snap):
    columns = [{'table_name': t, 'column_name': c} for t, cols in sorted(snap['tables'].items()) for c in sorted(cols)]
    return [columns,
            [{'name': n} for n in sorted(snap['functions'])],
            [{'name': n} for n in sorted(snap['triggers'])],
            [{'name': n} for n in sorted(snap['policies'])],
            [{'name': n} for n in sorted(snap['indexes'])],
            [{'exists': snap['ledger_present']}],
            [snap['counts']],
            [{'hardened': 'set_updated_at_search_path' in snap['function_flags']}],
            [{'name': n, 'enabled': n in snap['rls_enabled']} for n in sorted(sh.APP_TABLES)]]


class FakeMgmt:
    def __init__(self, snapshots, *, ledger=(), auth=None, fail_on=()):
        assert len(snapshots) >= 1
        self._snapshots = snapshots; self._index = 0
        self._ledger = list(ledger); self._auth = auth if auth is not None else {
            'SITE_URL': ORIGIN, 'URI_ALLOW_LIST': ORIGIN + '/auth/callback', 'EXTERNAL_EMAIL_ENABLED': True}
        self._fail_on = set(fail_on); self._file_calls = 0
        self.applied = []; self.patches = []; self.ledger_inserts = []

    def json(self, method, path, **kwargs):
        assert method == 'GET'
        if path.endswith('/config/auth'):
            return self._auth
        return {'id': 'ref111', 'name': 'dealscan', 'region': 'us-east-2', 'status': 'ACTIVE_HEALTHY'}

    def query(self, ref, sql, *, read_only=True):
        if not read_only:
            if 'create schema' in sql:
                return []
            if sql.startswith('insert into supabase_migrations.schema_migrations'):
                version = sql.split("'")[1]
                self._ledger.append(version)
                self.ledger_inserts.append(version)
                return []
            name = list(sh.MIGRATION_MARKERS)[self._file_calls]
            self._file_calls += 1
            if name in self._fail_on:
                raise sh.HandoffFailure('supabase_api_error (HTTP 400) for /v1/projects/ref111/database/query')
            self.applied.append(name)
            return []
        queries = sh.snapshot_queries()
        for i, probe in enumerate(queries):
            if sql == probe:
                snap = self._snapshots[min(self._index, len(self._snapshots) - 1)]
                block = rows_from_snapshot(snap)[i]
                if i == len(queries) - 1:
                    self._index += 1
                return block
        if sql.startswith('select version from'):
            return [{'version': v} for v in self._ledger]
        raise AssertionError('unexpected SQL: ' + sql[:80])

    def _call(self, method, path, **kwargs):
        self.patches.append((method, path, kwargs.get('json')))
        self._auth.update(kwargs.get('json') or {})
        class R:
            status_code = 200
        return R()


def test_handoff_verified_when_schema_and_auth_already_complete():
    client = FakeMgmt([full_snapshot()], ledger=[f.split('_')[0] for f in sh.MIGRATION_MARKERS])
    report = sh.run_handoff(client, 'ref111', apply=True)
    assert report['status'] == 'supabase_verified'
    assert report['migrations_applied_this_run'] == []
    assert report['checks']['application']['performed'] is False
    assert report['checks']['auth']['status'] == 'passed'


def test_handoff_applies_pending_migrations_in_order_and_fixes_auth():
    before = {'tables': {}, 'functions': set(), 'triggers': set(), 'policies': set(),
              'indexes': set(), 'function_flags': set(), 'ledger_present': False,
              'counts': {t: 0 for t in sh.APP_TABLES}, 'rls_enabled': set()}
    after = full_snapshot(); after['ledger_present'] = True
    auth = {'SITE_URL': 'http://localhost:3000', 'URI_ALLOW_LIST': 'http://localhost:3000/**'}
    client = FakeMgmt([before, after], auth=auth)
    report = sh.run_handoff(client, 'ref111', apply=True)
    assert report['migrations_applied_this_run'] == list(sh.MIGRATION_MARKERS)
    assert client.applied == list(sh.MIGRATION_MARKERS)  # exact timestamp order, no skips
    assert len(client.ledger_inserts) == 11
    assert client.patches and client.patches[0][2]['SITE_URL'] == ORIGIN
    assert report['checks']['auth']['status'] == 'passed' and report['checks']['auth']['fix_applied'] is True
    assert report['status'] == 'supabase_verified'


def test_handoff_halts_on_first_application_failure():
    before = {'tables': {}, 'functions': set(), 'triggers': set(), 'policies': set(),
              'indexes': set(), 'function_flags': set(), 'ledger_present': False,
              'counts': {t: 0 for t in sh.APP_TABLES}, 'rls_enabled': set()}
    target = '20260905200000_ingestion_integrity.sql'
    client = FakeMgmt([before, before], fail_on={target})
    report = sh.run_handoff(client, 'ref111', apply=True)
    applied = report['migrations_applied_this_run']
    assert applied == ['20260905170000_dealscan_production_schema.sql',
                       '20260905182000_public_read_policies.sql',
                       '20260905183000_harden_updated_at_search_path.sql',
                       '20260905194000_restrict_public_columns.sql']
    assert report['checks']['application']['stopped_at']['file'] == target
    assert target not in client.applied or client.applied[-1] != target
    later = [n for n in sh.MIGRATION_MARKERS if n > target]
    assert not any(n in client.applied for n in later)
    assert report['status'] == 'blocked'


def test_handoff_never_applies_after_inconsistent_state():
    files = list(sh.MIGRATION_MARKERS)
    stale = full_snapshot(); stale['indexes'] = set(); stale['ledger_present'] = True
    ledger = [f.split('_')[0] for f in files]
    client = FakeMgmt([stale, stale], ledger=ledger)
    report = sh.run_handoff(client, 'ref111', apply=True)
    assert report['checks']['application']['performed'] is False
    assert report['checks']['reconciliation']['inconsistent']
    assert report['status'] == 'blocked'


def test_inspection_is_read_only_without_apply():
    client = FakeMgmt([full_snapshot()], ledger=[f.split('_')[0] for f in sh.MIGRATION_MARKERS])
    report = sh.run_handoff(client, 'ref111', apply=False)
    assert client.applied == [] and client.patches == []
    assert report['status'] == 'supabase_verified'
EOF_MARKER = None


def test_real_query_accepts_201_and_enforces_read_only(monkeypatch):
    client = sh.SupabaseManagement('token')
    calls = []

    class R:
        def __init__(self, status, payload):
            self.status_code = status; self._p = payload
        def json(self):
            return self._p

    monkeypatch.setattr(sh.SupabaseManagement, '_call',
                        lambda self, method, path, **kw: (calls.append((method, path, kw.get('json'))), R(201, [{'one': 1}]))[1])
    rows = client.query('ref111', 'select 1')
    assert rows == [{'one': 1}]
    assert calls[0][2] == {'query': 'select 1', 'read_only': True}
    with pytest.raises(sh.HandoffFailure):
        client.query('ref111', 'delete from deals')
    assert len(calls) == 1  # the mutating statement never reached the wire

    monkeypatch.setattr(sh.SupabaseManagement, '_call',
                        lambda self, method, path, **kw: R(400, {'error': 'hidden'}))
    with pytest.raises(sh.HandoffFailure, match='HTTP 400'):
        client.query('ref111', 'select 1', read_only=False)
