"""Supabase management inspection, Auth config check and ordered migrations.

Uses only SUPABASE_ACCESS_TOKEN from the Actions secret store (Authorization
header, never printed; denial/error bodies are never echoed). SQL runs through
the Management query endpoint: inspection statements are explicit read-only
SELECTs on catalogs, and the logical "backup" is schema metadata plus row
counts — never row content, owner data or credential fields.

Migration application is additive and ordered: each repository file is applied
at most once, only when its distinguishing objects are verifiably absent, the
run stops at the first failure or inconsistent prior state, and nothing is
dropped or recreated outside the reviewed files themselves. A physical pg_dump
still requires database connection access (SUPABASE_DB_URL).
"""
from __future__ import annotations
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests

API = 'https://api.supabase.com'
PRODUCTION_ORIGIN = 'https://dealscan-omega.vercel.app'
MIGRATIONS_DIR = Path(os.getenv('DEALSCAN_MIGRATIONS_DIR') or
                      Path(__file__).resolve().parents[2] / 'supabase' / 'migrations')
APP_TABLES = ('counties', 'properties', 'deals', 'comps', 'subscribers',
              'deliveries', 'waitlist', 'ingestion_runs', 'ingestion_records', 'waitlist_request_limits')
LEDGER = 'supabase_migrations.schema_migrations'
# Mirrors SupabaseDatabase.init_db(): the required schema contract after all migrations.
REQUIRED_COLUMNS = {'counties': ['county_id'],
                    'properties': ['id', 'source_record_id', 'source_payload_hash', 'vacancy_status'],
                    'deals': ['id', 'financial_evidence', 'ingestion_record_id', 'revision', 'verification_expires_at'],
                    'comps': ['id', 'source_url', 'ingestion_record_id'],
                    'ingestion_runs': ['id', 'run_key', 'heartbeat_at', 'finished_at'],
                    'ingestion_records': ['id', 'record_key', 'field_mapping', 'raw_payload_canonical']}
_TIMEOUT = (5, 30)


class HandoffFailure(RuntimeError):
    pass


def project_ref(supabase_url: str) -> str:
    try:
        url = urlsplit(str(supabase_url or '').strip())
    except ValueError:
        raise HandoffFailure('SUPABASE_URL is not a valid URL') from None
    host = (url.hostname or '').lower()
    if (url.scheme != 'https' or not host.endswith('.supabase.co') or url.username
            or url.password or url.query or url.fragment or url.path.strip('/')):
        raise HandoffFailure('SUPABASE_URL must be the bare HTTPS https://<ref>.supabase.co origin')
    return host.split('.')[0]


def assert_read_only_sql(query: str) -> None:
    """Inspection statements are provably read-only single SELECTs."""
    text = re.sub(r'\s+', ' ', query.strip()).lower()
    if re.search(r'\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|vacuum|call|execute|do|copy)\b', text):
        raise HandoffFailure('Inspection SQL must be read-only')
    if not (text.startswith('select') or text.startswith('with') or text.startswith('explain select')):
        raise HandoffFailure('Inspection SQL must start with SELECT/WITH')
    if ';' in text.rstrip(';') or text.count(';') > 1:
        raise HandoffFailure('Inspection SQL must be a single statement')


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    files = sorted(directory.glob('*.sql'))
    names = [f.name for f in files]
    if len(set(names)) != len(names) or not all(re.fullmatch(r'[0-9]{14}_[a-z0-9_]+\.sql', n) for n in names):
        raise HandoffFailure('Migration directory contains an unordered or malformed filename')
    return files


# Distinguishing objects per migration file. Markers decide "already applied".
MIGRATION_MARKERS: dict[str, dict] = {
    '20260905170000_dealscan_production_schema.sql': {
        'tables': list(APP_TABLES[:7]), 'functions': ['set_updated_at'],
        'triggers': ['counties_set_updated_at', 'properties_set_updated_at', 'deals_set_updated_at']},
    '20260905182000_public_read_policies.sql': {
        'policies': ['public read counties', 'public read published deals',
                     'public read deal properties', 'public read comps for published deals']},
    '20260905183000_harden_updated_at_search_path.sql': {'function_flags': ['set_updated_at_search_path']},
    '20260905194000_restrict_public_columns.sql': {'indexes': ['idx_deals_verified_score']},
    '20260905200000_ingestion_integrity.sql': {
        'tables': ['ingestion_runs', 'ingestion_records'],
        'functions': ['finite_number', 'replace_deal_comps', 'hold_deals_for_parcels'],
        'columns': {'properties': ['source_payload_hash', 'vacancy_status'],
                    'ingestion_records': ['record_key', 'raw_payload_canonical', 'field_mapping'],
                    'ingestion_runs': ['run_key', 'heartbeat_at']}},
    '20260905210000_publication_evidence_gate.sql': {
        'functions': ['bump_deal_revision', 'distance_miles', 'require_publication_evidence',
                      'revoke_changed_property_deals', 'revoke_changed_comp_deals',
                      'revoke_changed_audit_deals', 'revoke_changed_run_deals', 'revoke_changed_county_deals'],
        'columns': {'deals': ['revision', 'verification_expires_at']}},
    '20260905220000_operational_contracts.sql': {
        'tables': ['waitlist_request_limits'], 'functions': ['join_waitlist', 'county_operational_snapshot']},
    '20260905230000_raw_source_publication.sql': {
        'functions': ['source_mapped_value', 'source_number', 'require_raw_source_evidence'],
        'triggers': ['deals_require_raw_source_evidence']},
    '20260905233000_subscriber_consent.sql': {'columns': {'subscribers': ['consented_at', 'unsubscribe_url']}},
    '20260906010000_comparable_arithmetic_gate.sql': {
        'functions': ['require_comparable_arithmetic'], 'triggers': ['deals_require_comparable_arithmetic']},
    '20260906020000_typed_validation_evidence.sql': {
        'functions': ['current_validation_proof', 'require_typed_source_validation', 'revoke_changed_validation_proof'],
        'triggers': ['deals_require_a_typed_validation', 'counties_revoke_validation_proof']},
    '20260907230000_audit_status_vocabulary.sql': {
        'constraints': {'ingestion_records': ['ingestion_records_status_v2']}},
    '20260912173000_index_hardening.sql': {
        'indexes': ['comps_county_id_idx', 'comps_ingestion_record_id_idx',
                    'deals_ingestion_record_id_idx', 'ingestion_records_deal_id_idx',
                    'ingestion_records_property_county_idx', 'ingestion_records_run_county_idx']},
}


class _CaptureStop(Exception):
    """Raised to abandon a captured write before any network call happens."""


class _StubResponse:
    status_code = 200
    def json(self):
        return []


def _sent_columns(table: str, call) -> set:
    """Column names one writer method actually sends for `table`.

    The real method runs against a transport that returns empty results and
    stops at the first write to `table`, so the contract observes the payload
    the ETL builds rather than a second-hand copy of it. Fixture inputs are
    key-shaped only and never leave this process.
    """
    from database_supabase import SupabaseDatabase
    body: dict = {}

    class _Capture(SupabaseDatabase):
        headers: dict = {}
        def __init__(self):
            self._counties, self._active, self._active_checked_at = {}, None, 0.0
        def _request(self, method, path, **kwargs):
            payload = kwargs.get('json')
            if str(path).split('?')[0] != table or method not in {'POST', 'PATCH'}:
                return _StubResponse()
            for row in (payload if isinstance(payload, list) else [payload]):
                if isinstance(row, dict):
                    body.update(row)
            raise _CaptureStop

    try:
        call(_Capture())
    except _CaptureStop:
        pass
    if not body:
        raise RuntimeError(f'write contract observed no {table} write')
    return set(body)


def write_columns() -> dict:
    """Columns the ETL can actually send, taken from the writers themselves.

    Every set is captured from the writer method, not rebuilt here, because the
    transport layer adds columns of its own (`ingestion_runs.run_key` is created
    inside `record_ingestion_run`, not by `run_payload`). A contract that models
    only the payload builders reports columns the ETL does send as missing.
    """
    return {
        'counties': _sent_columns('counties', lambda db: db.upsert_counties(
            [{'county_id': 'contract', 'county_name': 'contract'}])),
        'properties': _sent_columns('properties', lambda db: db.save_property(
            {'apn': 'contract', 'county_id': 'contract'})),
        'deals': _sent_columns('deals', lambda db: db.save_deal({'property_id': 1})),
        'ingestion_runs': _sent_columns('ingestion_runs', lambda db: db.record_ingestion_run(
            'contract', 'running', {})),
        'ingestion_records': _sent_columns('ingestion_records', lambda db: db.record_ingestion_records(
            1, 'contract', [{}])),
    }


def write_vocabulary() -> dict:
    """Column values the ETL writes, taken from the writers' own constants.

    A check constraint narrower than one of these sets rejects an entire batched
    insert (23514) for a single offending row, which reads as a silent audit gap
    rather than a failure of the column it constrains.
    """
    from persistence import AUDIT_STATUSES, STATUS_MAP
    from database_supabase import RUN_TYPES
    return {('ingestion_records', 'status'): set(AUDIT_STATUSES),
            ('ingestion_runs', 'status'): set(STATUS_MAP.values()),
            ('ingestion_runs', 'run_type'): set(RUN_TYPES)}


ALLOWED_VALUES = re.compile(
    r"\(?([a-z_][a-z0-9_]*)\)?(?:::text)?\s*=\s*ANY\s*\(\(?ARRAY\[(.+?)\]", re.S)


def permitted_values(definition: str) -> tuple:
    """Column and value list of a `col = ANY (ARRAY[...])` check, else (None, set())."""
    match = ALLOWED_VALUES.search(definition or '')
    if not match:
        return None, set()
    return match.group(1), {literal.strip().strip("'") for literal in
                            re.findall(r"'((?:[^']|'')*)'", match.group(2))}


# Every PostgREST on_conflict= target used by database_supabase.py. Each needs a
# non-partial unique index on exactly those columns or the upsert fails 42P10.
UPSERT_TARGETS = {'counties': ('county_id',), 'ingestion_runs': ('run_key',),
                  'ingestion_records': ('record_key', 'run_id'), 'properties': ('apn', 'county_id'),
                  'deals': ('property_id',), 'waitlist': ('email',)}


def write_contract(snapshot: dict) -> dict:
    """Can the ETL actually write? Structure only; no row is read or written."""
    missing_columns = {}
    for table, columns in sorted(write_columns().items()):
        present = snapshot['tables'].get(table)
        if present is None:
            missing_columns[table] = ['<table absent>']
            continue
        absent = sorted(columns - present)
        if absent:
            missing_columns[table] = absent
    # The reverse direction: a legacy NOT NULL column with no default that the
    # ETL never sends rejects every row (23502) even though every declared
    # column exists. Primary keys are excluded: the database assigns them.
    unwritable = {}
    for table, columns in sorted(write_columns().items()):
        required = (snapshot.get('mandatory_columns') or {}).get(table, set()) - {'id'}
        absent = sorted(required - columns)
        if absent:
            unwritable[table] = absent
    # A value vocabulary narrower than the writer's rejects whole batches.
    rejected_values = {}
    for table, defs in sorted((snapshot.get('constraints') or {}).items()):
        for name, definition in sorted(dict(defs).items()):
            column, allowed = permitted_values(definition if isinstance(definition, str) else '')
            if not column:
                continue
            written = write_vocabulary().get((table, column))
            unsupported = sorted(written - allowed) if written else []
            if unsupported:
                rejected_values[f'{table}.{column}'] = {'constraint': name, 'unsupported': unsupported}
    unique_indexes = snapshot.get('unique_indexes') or {}
    missing_upserts = []
    for table, target in sorted(UPSERT_TARGETS.items()):
        if table not in snapshot['tables']:
            continue  # a missing table is already reported by the schema contract
        if tuple(sorted(target)) not in {tuple(sorted(columns)) for columns in unique_indexes.get(table, [])}:
            missing_upserts.append(f'{table}({",".join(target)})')
    status = ('passed' if not missing_columns and not missing_upserts and not unwritable
              and not rejected_values else 'failed')
    return {'status': status, 'missing_columns': missing_columns,
            'missing_upsert_indexes': missing_upserts,
            'unwritable_required_columns': unwritable,
            'rejected_values': rejected_values,
            'note': 'Columns the ETL writes must exist and every on_conflict target needs a '
                    'non-partial unique index; a NOT NULL column with no default that the ETL never '
                    'sends rejects every row, and a check constraint narrower than the writer\'s '
                    'vocabulary rejects the whole batch. All of these fail only at write time.'}


def marker_missing(snapshot: dict, filename: str) -> list[str]:
    """Everything a migration must have created, evaluated on the snapshot."""
    markers = MIGRATION_MARKERS.get(filename)
    if markers is None:
        raise HandoffFailure(f'No registered marker set for {filename}')
    missing = []
    for table in markers.get('tables', []):
        if table not in snapshot['tables']:
            missing.append('table:' + table)
    for function in markers.get('functions', []):
        if function not in snapshot['functions']:
            missing.append('function:' + function)
    for trigger in markers.get('triggers', []):
        if trigger not in snapshot['triggers']:
            missing.append('trigger:' + trigger)
    for policy in markers.get('policies', []):
        if policy not in snapshot['policies']:
            missing.append('policy:' + policy)
    for index in markers.get('indexes', []):
        if index not in snapshot['indexes']:
            missing.append('index:' + index)
    for table, columns in (markers.get('columns') or {}).items():
        for column in columns:
            if column not in snapshot['tables'].get(table, set()):
                missing.append(f'column:{table}.{column}')
    for table, constraints in (markers.get('constraints') or {}).items():
        for constraint in constraints:
            if constraint not in ((snapshot.get('constraints') or {}).get(table) or {}):
                missing.append(f'constraint:{table}.{constraint}')
    for flag in markers.get('function_flags', []):
        if flag not in snapshot['function_flags']:
            missing.append('flag:' + flag)
    return missing


def split_sql_statements(sql: str) -> list[str]:
    """Split a migration file into top-level statements at ';', respecting single
    quotes, line/block comments and dollar-quoted plpgsql bodies ($$..$$, $tag$..$tag$).
    Multi-statement POST bodies can be partially applied by management endpoints
    without a hard error; executing statements one at a time makes any failure
    positioned and falsifiable instead of trusting whole-file HTTP success."""
    statements, current = [], []
    i, n = 0, len(sql)
    quote = None  # "'" or the active dollar-quote tag like '$$'
    while i < n:
        ch = sql[i]
        if quote is None:
            if sql.startswith('--', i):
                end = sql.find('\n', i)
                i = n if end == -1 else end + 1
                continue
            if sql.startswith('/*', i):
                end = sql.find('*/', i)
                i = n if end == -1 else end + 2
                continue
            if ch == "'":
                quote = "'"
                current.append(ch)
                i += 1
                continue
            if ch == '$':
                match = re.match(r'\$[A-Za-z0-9_]*\$', sql[i:])
                if match:
                    quote = match.group(0)
                    current.append(quote)
                    i += len(quote)
                    continue
                current.append(ch)
                i += 1
                continue
            if ch == ';':
                statement = ''.join(current).strip()
                if statement:
                    statements.append(statement)
                current = []
                i += 1
                continue
            current.append(ch)
            i += 1
        elif quote == "'":
            current.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    current.append("'")
                    i += 2
                    continue
                quote = None
            i += 1
        else:  # dollar-quoted body: only the matching tag closes it
            if sql.startswith(quote, i):
                current.append(quote)
                i += len(quote)
                quote = None
            else:
                current.append(ch)
                i += 1
    tail = ''.join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def file_statements(path: Path) -> list[str]:
    return split_sql_statements(path.read_text(encoding='utf-8'))


def reconcile(files: list[str], ledger: list[str], snapshot: dict) -> dict:
    """applied (ledger or full markers) vs pending vs inconsistent, in order."""
    rows = []
    for name in files:
        missing = marker_missing(snapshot, name)
        if name.split('_')[0] in ledger:
            state, detail = 'applied_ledger', [] if not missing else missing
        elif not missing:
            state, detail = 'applied_markers', []
        else:
            state, detail = 'pending', missing
        rows.append({'file': name, 'state': state, **({'missing': detail} if detail and state != 'applied_ledger' else {})})
        if state == 'applied_ledger' and missing:
            rows[-1]['state'] = 'inconsistent'
            rows[-1]['missing'] = missing
    pending = [r['file'] for r in rows if r['state'] == 'pending']
    inconsistent = [r['file'] for r in rows if r['state'] == 'inconsistent']
    return {'migrations': rows, 'pending': pending, 'inconsistent': inconsistent,
            'applicable': pending if not inconsistent else []}


def sanitize_auth_config(config: object) -> dict:
    """Only non-secret shape: site URL, redirect URLs, core email toggles."""
    if not isinstance(config, dict):
        return {}
    def pick(*names):
        for name in names:
            value = config.get(name)
            if value is not None:
                return value
        return None
    site = pick('SITE_URL', 'site_url')
    allow = pick('URI_ALLOW_LIST', 'uri_allow_list', 'redirect_urls')
    if isinstance(allow, str):
        urls = [u.strip() for u in allow.split(',') if u.strip()]
    elif isinstance(allow, list):
        urls = [u for u in allow if isinstance(u, str)]
    else:
        urls = []
    out = {'site_url': site if isinstance(site, str) else None, 'redirect_urls': urls}
    for camel, snake in (('EXTERNAL_EMAIL_ENABLED', 'external_email_enabled'),
                         ('MAILER_AUTOCONFIRM', 'mailer_autoconfirm'),
                         ('DISABLE_SIGNUP', 'disable_signup')):
        value = pick(camel, snake)
        if isinstance(value, bool):
            out[snake] = value
    return out


def auth_verdict(config: dict, origin: str) -> dict:
    production = origin.rstrip('/')
    callback = production + '/auth/callback'
    site_ok = isinstance(config.get('site_url'), str) and config['site_url'].rstrip('/') == production
    urls = config.get('redirect_urls') or []
    callback_allowed = any(u.rstrip('/') == callback or u.rstrip('/') == production + '/**'
                           or u.rstrip('/') == production for u in urls)
    missing = []
    if not site_ok:
        missing.append('site_url')
    if not callback_allowed:
        missing.append('callback_redirect_url')
    return {'status': 'passed' if not missing else 'failed', 'missing': missing,
            'site_url': config.get('site_url'), 'callback_url_expected': callback,
            'callback_allowed': callback_allowed,
            'localhost_urls_present': any('localhost' in u or '127.0.0.1' in u for u in urls),
            'email_enabled': config.get('external_email_enabled'),
            'mailer_autoconfirm': config.get('mailer_autoconfirm')}


def auth_fix_body(config: dict, origin: str) -> dict:
    """Only the two URL settings; every other Auth setting/URL is untouched."""
    verdict = auth_verdict(config, origin)
    if not verdict['missing']:
        return {}
    urls = list(config.get('redirect_urls') or [])
    wanted = verdict['callback_url_expected']
    if wanted not in [u.rstrip('/') for u in urls] and wanted not in urls:
        urls.append(wanted)
    return {'SITE_URL': origin, 'URI_ALLOW_LIST': ','.join(urls)}


def auth_fix_body_lower(config: dict, origin: str) -> dict:
    """Lowercase variant of the fix body: newer Management API revisions accept
    site_url/uri_allow_list instead of the GOTRUE-style uppercase keys. Only
    used when the uppercase PATCH replied 200 but the setting did not persist."""
    upper = auth_fix_body(config, origin)
    if not upper:
        return {}
    return {'site_url': upper['SITE_URL'], 'uri_allow_list': upper['URI_ALLOW_LIST']}


def required_columns_status(snapshot: dict) -> dict:
    missing = [f'{table}.{column}' for table, columns in REQUIRED_COLUMNS.items()
               for column in columns if column not in snapshot['tables'].get(table, set())]
    return {'status': 'passed' if not missing else 'failed', 'missing': missing}


class SupabaseManagement:
    def __init__(self, token: str) -> None:
        if not token or not token.strip():
            raise HandoffFailure('SUPABASE_ACCESS_TOKEN is missing')
        self.token = token.strip()

    def _call(self, method: str, path: str, **kwargs) -> requests.Response:
        try:
            response = requests.request(method, API + path, headers={'Authorization': 'Bearer ' + self.token},
                                        timeout=_TIMEOUT, allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise HandoffFailure('supabase_management_api_unavailable') from None
        if response.status_code in (401, 403):
            raise HandoffFailure(f'supabase_token_denied (HTTP {response.status_code})')
        return response

    @staticmethod
    def error_struct(response: requests.Response) -> dict:
        """Only machine-shaped error codes; free-text bodies may echo SQL."""
        try:
            body = response.json()
        except ValueError:
            return {}
        if not isinstance(body, dict):
            return {}
        detail = {}
        for key in ('code', 'error', 'name'):
            value = body.get(key)
            if isinstance(value, (str, int)) and re.fullmatch(r'[A-Za-z0-9_.\-]{1,48}', str(value)):
                detail[key] = str(value)
        return detail

    def json(self, method: str, path: str, **kwargs):
        response = self._call(method, path, **kwargs)
        if response.status_code != 200:
            raise HandoffFailure(f'supabase_api_error (HTTP {response.status_code}) for {path.split("?")[0]}')
        try:
            return response.json()
        except ValueError:
            raise HandoffFailure('supabase_api_returned_non_json') from None

    def query(self, ref: str, sql: str, *, read_only: bool = True):
        if read_only:
            assert_read_only_sql(sql)
        body = {'query': sql}
        if read_only:
            body['read_only'] = True
        # The Management query endpoint answers 201 with the row array.
        response = self._call('POST', f'/v1/projects/{ref}/database/query', json=body)
        if response.status_code not in (200, 201):
            detail = self.error_struct(response)
            suffix = f' {json.dumps(detail)}' if detail else ''
            raise HandoffFailure(f'supabase_api_error (HTTP {response.status_code}) for /v1/projects/{ref}/database/query{suffix}')
        try:
            result = response.json()
        except ValueError:
            raise HandoffFailure('supabase_api_returned_non_json') from None
        if not read_only:
            # Structural diagnosis only: shape and keys, never values. Some upstream
            # proxies answer DDL with HTTP success while embedding an error object.
            if isinstance(result, list):
                self.last_write_diag = {'shape': 'list', 'rows': len(result)}
            elif isinstance(result, dict):
                code = result.get('code')
                diag = {'shape': 'dict', 'keys': sorted(str(k) for k in result.keys())[:8]}
                if isinstance(code, str) and re.fullmatch(r'[0-9A-Z]{3,8}', code):
                    diag['pg_code'] = code
                self.last_write_diag = diag
            else:
                self.last_write_diag = {'shape': type(result).__name__}
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ('result', 'rows', 'data'):
                if isinstance(result.get(key), list):
                    return result[key]
        raise HandoffFailure('supabase_query_returned_an_unexpected_shape')


SAFE_COUNT_TABLES = {t: t for t in APP_TABLES}


def snapshot_queries() -> list[str]:
    table_list = ','.join(repr(t) for t in APP_TABLES)
    counts_select = ', '.join(f"(select count(*) from public.{t}) as {t}" for t in APP_TABLES)
    return [
        f"select table_name, column_name, is_nullable, column_default, is_identity, is_generated "
        f"from information_schema.columns where table_schema='public' "
        f"and table_name in ({table_list}) order by 1,2",
        "select p.proname as name from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
        "where n.nspname='public' order by 1",
        # information_schema.triggers is privilege-filtered and came back EMPTY on the live
        # project while pg_trigger held all 15 triggers; read the catalog instead.
        "select t.tgname as name from pg_trigger t join pg_class c on t.tgrelid=c.oid "
        "join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and not t.tgisinternal order by 1",
        "select distinct policyname as name from pg_policies where schemaname='public' order by 1",
        f"select indexname as name from pg_indexes where schemaname='public' and tablename in ({table_list}) order by 1",
        "select to_regclass('" + LEDGER + "') is not null as exists",
        f"select {counts_select}",
        # pg_get_functiondef renders the option as 'SET search_path TO ...' (uppercase),
        # so the case-sensitive LIKE could never match.
        "select pg_get_functiondef('public.set_updated_at()'::regprocedure) ilike '%set search_path%' as hardened",
        "select relname as name, relrowsecurity as enabled from pg_class c join pg_namespace n on n.oid=c.relnamespace "
        f"where n.nspname='public' and relname in ({table_list}) order by 1",
        # Unique index definitions back every PostgREST on_conflict= upsert. A
        # missing one fails only at write time (SQLSTATE 42P10), which is how a
        # whole ingestion audit can come back empty while the run looks healthy.
        "select t.relname as table_name, pg_get_indexdef(x.indexrelid) as definition "
        "from pg_index x join pg_class i on i.oid=x.indexrelid join pg_class t on t.oid=x.indrelid "
        "join pg_namespace n on n.oid=t.relnamespace "
        f"where n.nspname='public' and x.indisunique and t.relname in ({table_list}) order by 1,2",
        # Constraint names only: a check or foreign key the migrations never
        # declared is legacy drift that rejects writes (23514/23503) long after
        # the schema contract passes. Definitions are omitted, names are enough
        # to spot an object this repository does not own.
        "select c.relname as table_name, con.conname as name, con.contype::text as kind, "
        "case when con.contype='c' then pg_get_constraintdef(con.oid) else 'foreign key' end as definition "
        "from pg_constraint con "
        "join pg_class c on c.oid=con.conrelid join pg_namespace n on n.oid=c.relnamespace "
        f"where n.nspname='public' and con.contype in ('c','f') and c.relname in ({table_list}) order by 1,2",
    ]


CROSS_CHECK_SQL = (
    "select (select count(*) from pg_trigger t join pg_class c on t.tgrelid=c.oid "
    "join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and not t.tgisinternal) as pg_triggers_public, "
    "(select count(distinct trigger_name) from information_schema.triggers where trigger_schema='public') as info_triggers_public, "
    "(select count(*) from pg_policies where schemaname='public') as pg_policies_public, "
    "(select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public') as pg_functions_public")


def build_snapshot(rows: list[list[dict]]) -> dict:
    tables: dict[str, set] = {}
    # Columns the database will not fill by itself: NOT NULL, no default, not an
    # identity/generated column. Anything here that the ETL does not send makes
    # every insert fail 23502 at write time while the schema still looks correct.
    mandatory: dict[str, set] = {}
    for row in rows[0]:
        if isinstance(row, dict) and isinstance(row.get('table_name'), str) and isinstance(row.get('column_name'), str):
            tables.setdefault(row['table_name'], set()).add(row['column_name'])
            if (str(row.get('is_nullable','YES')).upper()=='NO' and row.get('column_default') in (None,'')
                    and str(row.get('is_identity','NO')).upper()=='NO'
                    and str(row.get('is_generated','NEVER')).upper()=='NEVER'):
                mandatory.setdefault(row['table_name'], set()).add(row['column_name'])
    def names(items, key='name'):
        return {item[key] for item in items if isinstance(item, dict) and isinstance(item.get(key), str)}
    counts = rows[6][0] if rows[6] and isinstance(rows[6][0], dict) else {}
    flags = set()
    if rows[7] and isinstance(rows[7][0], dict) and rows[7][0].get('hardened') is True:
        flags.add('set_updated_at_search_path')
    rls = {item['name'] for item in rows[8]
           if isinstance(item, dict) and item.get('enabled') is True and isinstance(item.get('name'), str)}
    unique_indexes: dict[str, list[tuple]] = {}
    for row in (rows[9] if len(rows) > 9 else []):
        if not (isinstance(row, dict) and isinstance(row.get('table_name'), str)
                and isinstance(row.get('definition'), str)):
            continue
        definition = row['definition']
        if ' WHERE ' in definition.upper():
            continue  # a partial index cannot serve ON CONFLICT
        body = definition[definition.rfind('(') + 1:definition.rfind(')')]
        columns = tuple(sorted(part.strip().strip('"').split(' ')[0] for part in body.split(',') if part.strip()))
        unique_indexes.setdefault(row['table_name'], []).append(columns)
    constraints: dict[str, dict] = {}
    for row in (rows[10] if len(rows) > 10 else []):
        if isinstance(row, dict) and isinstance(row.get('table_name'), str) and isinstance(row.get('name'), str):
            definition = row.get('definition')
            constraints.setdefault(row['table_name'], {})[row['name']] = (
                definition if isinstance(definition, str) else 'unknown')
    return {'tables': tables, 'mandatory_columns': mandatory, 'constraints': constraints, 'functions': names(rows[1]), 'triggers': names(rows[2]),
            'policies': names(rows[3]), 'indexes': names(rows[4]), 'unique_indexes': unique_indexes,
            'ledger_present': bool(rows[5] and isinstance(rows[5][0], dict) and rows[5][0].get('exists')),
            'counts': {key: value for key, value in counts.items() if isinstance(value, int) and value >= 0},
            'function_flags': flags, 'rls_enabled': rls}


LEDGER_BOOTSTRAP = ("create schema if not exists supabase_migrations; "
                    "create table if not exists supabase_migrations.schema_migrations ("
                    "version text primary key, name text, inserted_at timestamptz not null default now())")


def snapshot_for_report(snapshot: dict) -> dict:
    """Reportable shape: column NAME sets are structure, not data."""
    return {'tables': {table: sorted(columns) for table, columns in sorted(snapshot['tables'].items())},
            'functions': sorted(snapshot['functions']), 'triggers': sorted(snapshot['triggers']),
            'policies': sorted(snapshot['policies']), 'indexes': sorted(snapshot['indexes']),
            'unique_indexes': {table: sorted(columns) for table, columns in sorted((snapshot.get('unique_indexes') or {}).items())},
            'mandatory_columns': {table: sorted(columns) for table, columns in sorted((snapshot.get('mandatory_columns') or {}).items())},
            'constraints': {table: dict(sorted(defs.items())) for table, defs in sorted((snapshot.get('constraints') or {}).items())
                            if table in write_columns()},
            'ledger_present': snapshot['ledger_present'], 'counts': snapshot['counts'],
            'function_flags': sorted(snapshot['function_flags']), 'rls_enabled': sorted(snapshot['rls_enabled']),
            **({'query_failures': snapshot['query_failures']} if snapshot.get('query_failures') else {})}


def run_handoff(client: SupabaseManagement, ref: str, *, apply: bool, origin: str = PRODUCTION_ORIGIN) -> dict:
    checks: dict = {}
    project = client.json('GET', f'/v1/projects/{ref}')
    checks['project'] = {'status': 'passed',
                         **{key: project[key] for key in ('id', 'name', 'region', 'status')
                            if isinstance(project.get(key), str)}}
    files = migration_files()
    names = [f.name for f in files]

    def take_snapshot() -> dict:
        failures = []
        rows = []
        for index, sql in enumerate(snapshot_queries()):
            try:
                rows.append(client.query(ref, sql))
            except HandoffFailure as exc:
                failures.append({'query_index': index, 'reason': str(exc)})
                rows.append([])
        snapshot = build_snapshot(rows)
        if failures:
            snapshot['query_failures'] = failures
        return snapshot

    try:
        client.query(ref, 'select 1 as ok')
        checks['query_endpoint'] = {'status': 'passed'}
    except HandoffFailure as exc:
        checks['query_endpoint'] = {'status': 'failed', 'reason': str(exc)}
        return {'status': 'blocked', 'scope': 'supabase_management_handoff',
                'checked_at': datetime.now(timezone.utc).isoformat(), 'commit': os.getenv('GITHUB_SHA'),
                'project_ref': ref, 'checks': checks, 'migrations_applied_this_run': [], 'failure': str(exc),
                'note': 'The Management query endpoint is required for schema inspection. '
                        'Grant/retry with SUPABASE_DB_URL operator access for psql fallback.'}

    before = take_snapshot()
    checks['schema_before'] = snapshot_for_report(before)
    try:
        rows = client.query(ref, CROSS_CHECK_SQL)
        checks['catalog_cross_check'] = rows[0] if rows and isinstance(rows[0], dict) else {'rows': rows}
    except HandoffFailure as exc:
        checks['catalog_cross_check'] = {'status': 'failed', 'reason': str(exc)}
    ledger = []
    if before['ledger_present']:
        rows = client.query(ref, f"select version from {LEDGER} order by 1")
        ledger = [row['version'] for row in rows if isinstance(row, dict) and isinstance(row.get('version'), str)]
    recon = reconcile(names, [v.split('_')[0] for v in ledger], before)
    checks['reconciliation'] = recon

    applied_now: list[str] = []
    repair_inconsistent = apply and os.getenv('DEALSCAN_REPAIR_INCONSISTENT') == '1'
    targets = list(recon['applicable'])
    repairstargets = recon['inconsistent'] if repair_inconsistent else []
    application: dict = {'performed': False, 'applied': applied_now, 'stopped_at': None,
                         'repair_inconsistent': repairstargets,
                         'note': 'Statement-by-statement application of reviewed files, in order; a file is '
                                 'ledgered only after its post-write markers verify. Idempotent re-application '
                                 'of ledgered-but-incomplete files is opt-in (DEALSCAN_REPAIR_INCONSISTENT=1).'}
    final_snapshot = before
    if apply and (targets or repairstargets):
        if before['ledger_present'] or targets:
            client.query(ref, LEDGER_BOOTSTRAP, read_only=False)
        application['performed'] = True
        wanted = targets + repairstargets
        write_diary = []
        for path in files:
            if path.name not in wanted:
                continue
            statements = file_statements(path)
            failed = None
            for index, statement in enumerate(statements, 1):
                try:
                    client.query(ref, statement, read_only=False)
                except HandoffFailure as exc:
                    failed = {'file': path.name, 'statement': f'{index}/{len(statements)}', 'reason': str(exc)}
                    break
                diag = getattr(client, 'last_write_diag', None) or {}
                if diag.get('shape') != 'list' or diag.get('rows') not in (0, None):
                    entry = {'file': path.name, 'statement': f'{index}/{len(statements)}', 'diag': diag}
                    if len(write_diary) < 40:
                        write_diary.append(entry)
            if failed is not None:
                application['stopped_at'] = failed
                break
            probe = take_snapshot()
            missing = marker_missing(probe, path.name)
            if missing:
                application['stopped_at'] = {'file': path.name, 'post_apply_markers_missing': missing,
                                             'note': 'Statements returned HTTP success but objects are missing; '
                                                     'file NOT ledgered, staying visible as a failure.'}
                break
            version = path.name.split('_')[0]
            client.query(ref, "insert into supabase_migrations.schema_migrations (version, name) values "
                              f"('{version}', '{path.name}') on conflict (version) do nothing", read_only=False)
            applied_now.append(path.name)
        final_snapshot = take_snapshot()
        recon = reconcile(names, [s.split('_')[0] for s in [*ledger, *applied_now]], final_snapshot)
        checks['reconciliation'] = recon
        if write_diary:
            application['non_empty_or_non_list_write_responses'] = write_diary
            application['note'] += ' Some write calls returned non-empty or non-list bodies; see the diary.'
    checks['application'] = application
    checks['schema_contract'] = required_columns_status(final_snapshot)
    checks['write_contract'] = write_contract(final_snapshot)

    try:
        raw_config = client.json('GET', f'/v1/projects/{ref}/config/auth')
    except HandoffFailure as exc:
        checks['auth'] = {'status': 'failed', 'reason': str(exc)}
        raw_config = None
    else:
        config = sanitize_auth_config(raw_config)
        verdict = auth_verdict(config, origin)
        if verdict['status'] != 'passed' and apply:
            attempts = []
            body = auth_fix_body(config, origin)
            if body:
                response = client._call('PATCH', f'/v1/projects/{ref}/config/auth', json=body)
                attempts.append({'keys': 'uppercase', 'http_status': response.status_code})
                if response.status_code == 200:
                    config = sanitize_auth_config(client.json('GET', f'/v1/projects/{ref}/config/auth'))
                    verdict = auth_verdict(config, origin)
                    verdict['fix_applied'] = True
                    if verdict['status'] != 'passed':
                        lower = auth_fix_body_lower(config, origin)
                        if lower:
                            retry = client._call('PATCH', f'/v1/projects/{ref}/config/auth', json=lower)
                            attempts.append({'keys': 'lowercase', 'http_status': retry.status_code})
                            if retry.status_code == 200:
                                config = sanitize_auth_config(client.json('GET', f'/v1/projects/{ref}/config/auth'))
                                verdict = {**auth_verdict(config, origin), 'fix_applied': True}
                else:
                    verdict['fix'] = {'status': 'failed', 'http_status': response.status_code}
            if attempts:
                verdict['patch_attempts'] = attempts
        checks['auth'] = verdict

    reconciled = not checks['reconciliation']['pending'] and not checks['reconciliation']['inconsistent']
    healthy = (reconciled and checks['schema_contract']['status'] == 'passed'
               and checks['write_contract']['status'] == 'passed'
               and checks['auth']['status'] == 'passed')
    return {'status': 'supabase_verified' if healthy else 'blocked',
            'scope': 'supabase_management_handoff', 'migrations_applied_this_run': applied_now,
            'checked_at': datetime.now(timezone.utc).isoformat(), 'commit': os.getenv('GITHUB_SHA'),
            'project_ref': ref, 'checks': checks,
            'note': 'Logical schema/count snapshot, not a physical pg_dump (needs SUPABASE_DB_URL). '
                    'SQL ran read-only except the reviewed migration files and their ledger rows. '
                    'No secret values, row content or owner data are included.'}


def annotation_summary(report: dict) -> dict:
    """Minimized Check-annotation payload (<4KB); the full report stays in the artifact."""
    checks = report.get('checks') or {}
    recon = checks.get('reconciliation') or {}
    contract = checks.get('schema_contract') or {}
    auth = checks.get('auth') or {}
    before = checks.get('schema_before') or {}
    return {'status': report.get('status'), 'scope': report.get('scope'),
            'checked_at': report.get('checked_at'), 'commit': report.get('commit'),
            'failure': report.get('failure'),
            'query_endpoint': (checks.get('query_endpoint') or {}).get('status'),
            'catalog_cross_check': checks.get('catalog_cross_check'),
            'project': checks.get('project'),
            'applied_this_run': report.get('migrations_applied_this_run'),
            'application_stopped_at': (checks.get('application') or {}).get('stopped_at'),
            'pending': recon.get('pending'), 'inconsistent': recon.get('inconsistent'),
            'schema_contract': contract,
            'write_contract': checks.get('write_contract'),
            'auth': {key: auth.get(key) for key in ('status', 'missing', 'site_url', 'callback_allowed',
                                                    'localhost_urls_present', 'fix_applied', 'reason')
                     if auth.get(key) is not None},
            'tables_present': sorted((before.get('tables') or {}).keys()),
            # Names only, for the two tables that carry ingestion lineage. A
            # check or foreign key these migrations never declared, or a trigger
            # raising P0001, rejects audit writes long after the schema and
            # write contracts both pass. The artifact is unreadable in CI, so
            # this evidence has to travel in the annotation.
            'audit_constraints': {table: dict(sorted(((before.get('constraints') or {}).get(table) or {}).items()))
                                  for table in ('ingestion_records', 'ingestion_runs')},
            'triggers': sorted(before.get('triggers') or []),
            'counts': before.get('counts'), 'ledger_present': before.get('ledger_present'),
            'legacy_objects_note': 'Schema had pre-existing legacy objects; application was additive, ordered, main-sourced.'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true',
                        help='Apply pending ordered migrations and required Auth URL alignment (operator authorized)')
    parser.add_argument('--app-url', default=os.getenv('PRODUCTION_APP_URL', PRODUCTION_ORIGIN))
    parser.add_argument('--report-file', required=True)
    args = parser.parse_args(argv)
    try:
        origin = args.app_url.rstrip('/')
        if not origin.startswith('https://'):
            raise HandoffFailure('The production app URL must be an HTTPS origin')
        client = SupabaseManagement(os.getenv('SUPABASE_ACCESS_TOKEN', ''))
        report = run_handoff(client, project_ref(os.getenv('SUPABASE_URL', '')),
                             apply=args.apply, origin=origin)
    except HandoffFailure as exc:
        report = {'status': 'blocked', 'scope': 'supabase_management_handoff',
                  'checked_at': datetime.now(timezone.utc).isoformat(),
                  'commit': os.getenv('GITHUB_SHA'), 'failure': str(exc), 'checks': {}}
    path = Path(args.report_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if os.getenv('GITHUB_ACTIONS') == 'true':
        summary = annotation_summary(report)
        message = json.dumps(summary, separators=(',', ':')).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        level = 'notice' if report['status'] == 'supabase_verified' else 'error'
        print(f'::{level} title=Supabase production handoff (minimized; full report in artifact)::{message}')
    return 0 if report['status'] == 'supabase_verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
