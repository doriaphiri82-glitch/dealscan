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


def merged_snapshot(base, after, applied):
    """Snapshot view where only fully-applied files contribute their markers.
    Tables created by a marker inherit their columns from the 'after' view,
    so post-write verification (never HTTP success) drives every verdict."""
    snap = {'tables': {t: set(c) for t, c in base['tables'].items()},
            'functions': set(base['functions']), 'triggers': set(base['triggers']),
            'policies': set(base['policies']), 'indexes': set(base['indexes']),
            'function_flags': set(base['function_flags']),
            'counts': dict(base['counts']), 'rls_enabled': set(base['rls_enabled']),
            'ledger_present': base['ledger_present']}
    for name in applied:
        markers = sh.MIGRATION_MARKERS[name]
        for key in ('functions', 'triggers', 'policies', 'indexes', 'function_flags'):
            snap[key] |= set(markers.get(key, []))
        for table in markers.get('tables', []):
            columns = set(after['tables'].get(table, snap['tables'].get(table, set())))
            # a real table always has columns; an empty column set would emit zero
            # catalog rows in rows_from_snapshot and shadow the table entirely
            snap['tables'][table] = columns or {'id'}
        for table, columns in (markers.get('columns') or {}).items():
            snap['tables'].setdefault(table, set())
            snap['tables'][table] |= set(cols for cols in after['tables'].get(table, set()) if cols in set(columns))
        if after.get('rls_enabled') != base['rls_enabled']:
            snap['rls_enabled'] = set(after.get('rls_enabled', base['rls_enabled']))
    return snap


class FakeMgmt:
    """Strict management-API simulator. Migration statements must arrive one at a
    time, in exact file order; a file's markers only become visible once every
    statement in it completed — mirroring the partial-application failure mode
    observed against the real endpoint. Post-write verification (never HTTP
    success alone) is what gates the ledger."""

    def __init__(self, before, *, after=None, ledger=(), auth=None, fail_at=None,
                 already_done=(), uppercase_ignored=False, writes_stick=True):
        self._base = before
        self._after = after or before
        self._ledger = list(ledger)
        self._auth = auth if auth is not None else {
            'SITE_URL': ORIGIN, 'URI_ALLOW_LIST': ORIGIN + '/auth/callback', 'EXTERNAL_EMAIL_ENABLED': True}
        self._fail_at = fail_at
        self._already_done = set(already_done)
        self._uppercase_ignored = uppercase_ignored
        self._writes_stick = writes_stick
        self._bootstrap = False
        self.applied = []
        self.completed = list(self._already_done)
        self.patches, self.ledger_inserts = [], []
        self._sequence = [(f.name, sh.file_statements(f)) for f in sh.migration_files()]
        self._file_idx = 0
        self._stmt_idx = 0
        self._pending_close = None

    def json(self, method, path, **kwargs):
        assert method == 'GET'
        if path.endswith('/config/auth'):
            return self._auth
        return {'id': 'ref111', 'name': 'dealscan', 'region': 'us-east-2', 'status': 'ACTIVE_HEALTHY'}

    def _close(self, file_name):
        if file_name not in self.applied:
            self.applied.append(file_name)
        # writes_stick=False simulates an endpoint that returns HTTP success but
        # never persists the statements — objects must then stay invisible
        if self._writes_stick and file_name not in self.completed:
            self.completed.append(file_name)

    def _served(self):
        snap = merged_snapshot(self._base, self._after, self.completed)
        snap['ledger_present'] = bool(self._ledger) or self._bootstrap
        return snap

    def _next_statement(self):
        while self._file_idx < len(self._sequence):
            file_name, statements = self._sequence[self._file_idx]
            if file_name in self._already_done:
                self._file_idx += 1
                continue
            if self._stmt_idx < len(statements):
                statement = statements[self._stmt_idx]
                position = self._stmt_idx + 1
                self._stmt_idx += 1
                if self._stmt_idx >= len(statements):
                    self._pending_close = file_name
                return file_name, position, statement, len(statements)
            self._close(file_name)
            self._file_idx += 1
            self._stmt_idx = 0
        return None

    def _flush_close(self):
        if self._pending_close is not None:
            self._close(self._pending_close)
            self._pending_close = None
            self._file_idx += 1
            self._stmt_idx = 0

    def query(self, ref, sql, *, read_only=True):
        if not read_only:
            if 'create schema' in sql:
                self._bootstrap = True
                return []
            if sql.startswith('insert into supabase_migrations.schema_migrations'):
                version = sql.split("'")[1]
                if version not in self._ledger:
                    self._ledger.append(version)
                    self._ledger.sort()
                self.ledger_inserts.append(version)
                return []
            self._flush_close()
            current = self._next_statement()
            assert current is not None, 'unexpected extra write: ' + sql[:60]
            file_name, position, expected, total = current
            assert sql == expected, f'statement mismatch for {file_name} #{position}'
            if self._fail_at == (file_name, position):
                raise sh.HandoffFailure('supabase_api_error (HTTP 400) for /v1/projects/ref111/database/query')
            return []
        if sql == 'select 1 as ok':
            return [{'ok': 1}]
        self._flush_close()
        queries = sh.snapshot_queries()
        for i, probe in enumerate(queries):
            if sql == probe:
                return rows_from_snapshot(self._served())[i]
        if sql.startswith('select version from'):
            return [{'version': v} for v in self._ledger]
        raise AssertionError('unexpected SQL: ' + sql[:80])

    def _call(self, method, path, **kwargs):
        body = kwargs.get('json') or {}
        self.patches.append((method, path, body))
        if method == 'PATCH':
            if 'SITE_URL' in body and not self._uppercase_ignored:
                self._auth['SITE_URL'] = body['SITE_URL']
                self._auth['URI_ALLOW_LIST'] = body['URI_ALLOW_LIST']
            if 'site_url' in body:
                self._auth['SITE_URL'] = body['site_url']
                self._auth['URI_ALLOW_LIST'] = body['uri_allow_list']
        class R:
            status_code = 200
        return R()


def test_handoff_verified_when_schema_and_auth_already_complete():
    client = FakeMgmt(full_snapshot(), ledger=[f.split('_')[0] for f in sh.MIGRATION_MARKERS])
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
    client = FakeMgmt(before, after=after, auth=auth)
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
    client = FakeMgmt(before, fail_at=(target, 1))
    report = sh.run_handoff(client, 'ref111', apply=True)
    applied = report['migrations_applied_this_run']
    assert applied == ['20260905170000_dealscan_production_schema.sql',
                       '20260905182000_public_read_policies.sql',
                       '20260905183000_harden_updated_at_search_path.sql',
                       '20260905194000_restrict_public_columns.sql']
    stopped = report['checks']['application']['stopped_at']
    assert stopped['file'] == target and stopped['statement'].startswith('1/')
    assert target not in client.applied
    later = [n for n in sh.MIGRATION_MARKERS if n > target]
    assert not any(n in client.applied for n in later)
    assert report['status'] == 'blocked'


def test_handoff_never_applies_after_inconsistent_state():
    files = list(sh.MIGRATION_MARKERS)
    stale = full_snapshot(); stale['indexes'] = set(); stale['ledger_present'] = True
    ledger = [f.split('_')[0] for f in files]
    client = FakeMgmt(stale, ledger=ledger)
    report = sh.run_handoff(client, 'ref111', apply=True)
    assert report['checks']['application']['performed'] is False
    assert report['checks']['reconciliation']['inconsistent']
    assert report['status'] == 'blocked'


def test_inspection_is_read_only_without_apply():
    client = FakeMgmt(full_snapshot(), ledger=[f.split('_')[0] for f in sh.MIGRATION_MARKERS])
    report = sh.run_handoff(client, 'ref111', apply=False)
    assert client.applied == [] and client.patches == []
    assert report['status'] == 'supabase_verified'


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


def test_annotation_summary_stays_minimized_and_complete():
    before = {'tables': {}, 'functions': set(), 'triggers': set(), 'policies': set(),
              'indexes': set(), 'function_flags': set(), 'ledger_present': False,
              'counts': {t: 0 for t in sh.APP_TABLES}, 'rls_enabled': set()}
    after = full_snapshot()
    client = FakeMgmt(before, after=after)
    report = sh.run_handoff(client, 'ref111', apply=True)
    assert report['status'] == 'supabase_verified'
    summary = sh.annotation_summary(report)
    import json as _json
    encoded = _json.dumps(summary, separators=(',', ':'))
    assert len(encoded) < 3900
    assert summary['status'] == 'supabase_verified'
    assert summary['applied_this_run'] == list(sh.MIGRATION_MARKERS)
    assert summary['schema_contract']['status'] == 'passed'
    assert summary['auth']['status'] == 'passed'


def test_split_statements_respects_dollar_quoted_bodies_and_quotes():
    sql = ("-- lead comment\n"
           "create function demo() returns trigger as $$\n"
           "begin\n  raise notice 'a;b';\n  perform 1;\nend;\n$$ language plpgsql;\n"
           "create table if not exists t (x text default 'a;b');\n"
           "/* block ; comment */ select $tag$still;one;stmt$tag$;\n")
    statements = sh.split_sql_statements(sql)
    assert len(statements) == 3
    assert 'a;b' in statements[0] and statements[0].startswith('create function demo()')
    assert statements[1].startswith('create table')
    assert statements[2] == 'select $tag$still;one;stmt$tag$'


def test_mid_file_failure_leaves_file_unledgered_and_reports_position():
    before = {'tables': {}, 'functions': set(), 'triggers': set(), 'policies': set(),
              'indexes': set(), 'function_flags': set(), 'ledger_present': False,
              'counts': {t: 0 for t in sh.APP_TABLES}, 'rls_enabled': set()}
    target = '20260905200000_ingestion_integrity.sql'  # 104 statements
    client = FakeMgmt(before, fail_at=(target, 2))
    report = sh.run_handoff(client, 'ref111', apply=True)
    stopped = report['checks']['application']['stopped_at']
    assert stopped['file'] == target and stopped['statement'].startswith('2/')
    assert report['migrations_applied_this_run'] == ['20260905170000_dealscan_production_schema.sql',
                                                     '20260905182000_public_read_policies.sql',
                                                     '20260905183000_harden_updated_at_search_path.sql',
                                                     '20260905194000_restrict_public_columns.sql']
    assert client.ledger_inserts == ['20260905170000', '20260905182000', '20260905183000', '20260905194000']
    assert target not in client.applied
    later = [n for n in sh.MIGRATION_MARKERS if n > target]
    assert not any(n in client.applied for n in later)
    assert report['status'] == 'blocked'


def test_untrusted_write_success_is_caught_by_marker_verification():
    """If all statements claim success but markers never appear, the file is NOT
    ledgered and the run reports the missing markers — success is never assumed."""
    before = {'tables': {}, 'functions': set(), 'triggers': set(), 'policies': set(),
              'indexes': set(), 'function_flags': set(), 'ledger_present': False,
              'counts': {t: 0 for t in sh.APP_TABLES}, 'rls_enabled': set()}
    client = FakeMgmt(before, writes_stick=False)  # HTTP success, nothing persists
    report = sh.run_handoff(client, 'ref111', apply=True)
    stopped = report['checks']['application']['stopped_at']
    assert stopped['file'] == '20260905170000_dealscan_production_schema.sql'
    assert stopped['post_apply_markers_missing']
    assert report['migrations_applied_this_run'] == [] and client.ledger_inserts == []
    assert report['status'] == 'blocked'


def test_inconsistent_repair_requires_opt_in_and_verifies(monkeypatch):
    broken = '20260905183000_harden_updated_at_search_path.sql'
    state = full_snapshot()
    state['function_flags'] = set()  # ledgered, but the hardened search_path flag is gone
    state['ledger_present'] = True
    ledger = [f.split('_')[0] for f in sh.MIGRATION_MARKERS]
    monkeypatch.delenv('DEALSCAN_REPAIR_INCONSISTENT', raising=False)
    client = FakeMgmt(state, ledger=ledger)
    report = sh.run_handoff(client, 'ref111', apply=True)
    assert report['checks']['application']['performed'] is False
    assert report['checks']['reconciliation']['inconsistent'] == [broken]
    assert report['status'] == 'blocked'

    monkeypatch.setenv('DEALSCAN_REPAIR_INCONSISTENT', '1')
    client = FakeMgmt(state, after=full_snapshot(), ledger=ledger,
                      already_done=[f for f in sh.MIGRATION_MARKERS if f != broken])
    report = sh.run_handoff(client, 'ref111', apply=True)
    assert client.applied == [broken]
    assert report['migrations_applied_this_run'] == [broken]
    assert report['checks']['reconciliation']['inconsistent'] == []
    assert report['status'] == 'supabase_verified'


def test_auth_lowercase_fallback_when_uppercase_patch_does_not_persist():
    auth = {'SITE_URL': 'http://localhost:3000', 'URI_ALLOW_LIST': 'http://localhost:3000/**'}
    client = FakeMgmt(full_snapshot(), ledger=[f.split('_')[0] for f in sh.MIGRATION_MARKERS],
                      auth=auth, uppercase_ignored=True)
    report = sh.run_handoff(client, 'ref111', apply=True)
    verdict = report['checks']['auth']
    assert verdict['status'] == 'passed' and verdict['fix_applied'] is True
    assert verdict['patch_attempts'] == [{'keys': 'uppercase', 'http_status': 200},
                                         {'keys': 'lowercase', 'http_status': 200}]
    assert client.patches[0][2]['SITE_URL'] == ORIGIN
    assert client.patches[1][2]['site_url'] == ORIGIN
    assert report['status'] == 'supabase_verified'
