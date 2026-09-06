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
}


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
    for flag in markers.get('function_flags', []):
        if flag not in snapshot['function_flags']:
            missing.append('flag:' + flag)
    return missing


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
        f"select table_name, column_name from information_schema.columns where table_schema='public' "
        f"and table_name in ({table_list}) order by 1,2",
        "select p.proname as name from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
        "where n.nspname='public' order by 1",
        "select distinct trigger_name as name from information_schema.triggers where trigger_schema='public' order by 1",
        "select distinct policyname as name from pg_policies where schemaname='public' order by 1",
        f"select indexname as name from pg_indexes where schemaname='public' and tablename in ({table_list}) order by 1",
        "select to_regclass('" + LEDGER + "') is not null as exists",
        f"select {counts_select}",
        "select pg_get_functiondef('public.set_updated_at()'::regprocedure) like '%set search_path%' as hardened",
        "select relname as name, relrowsecurity as enabled from pg_class c join pg_namespace n on n.oid=c.relnamespace "
        f"where n.nspname='public' and relname in ({table_list}) order by 1",
    ]


def build_snapshot(rows: list[list[dict]]) -> dict:
    tables: dict[str, set] = {}
    for row in rows[0]:
        if isinstance(row, dict) and isinstance(row.get('table_name'), str) and isinstance(row.get('column_name'), str):
            tables.setdefault(row['table_name'], set()).add(row['column_name'])
    def names(items, key='name'):
        return {item[key] for item in items if isinstance(item, dict) and isinstance(item.get(key), str)}
    counts = rows[6][0] if rows[6] and isinstance(rows[6][0], dict) else {}
    flags = set()
    if rows[7] and isinstance(rows[7][0], dict) and rows[7][0].get('hardened') is True:
        flags.add('set_updated_at_search_path')
    rls = {item['name'] for item in rows[8]
           if isinstance(item, dict) and item.get('enabled') is True and isinstance(item.get('name'), str)}
    return {'tables': tables, 'functions': names(rows[1]), 'triggers': names(rows[2]),
            'policies': names(rows[3]), 'indexes': names(rows[4]),
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
    ledger = []
    if before['ledger_present']:
        rows = client.query(ref, f"select version from {LEDGER} order by 1")
        ledger = [row['version'] for row in rows if isinstance(row, dict) and isinstance(row.get('version'), str)]
    recon = reconcile(names, [v.split('_')[0] for v in ledger], before)
    checks['reconciliation'] = recon

    applied_now: list[str] = []
    application: dict = {'performed': False, 'applied': applied_now, 'stopped_at': None,
                         'note': 'Idempotent reviewed files only; each is applied at most once, in order.'}
    final_snapshot = before
    if apply and recon['applicable']:
        client.query(ref, LEDGER_BOOTSTRAP, read_only=False)
        application['performed'] = True
        for path in files:
            if path.name not in recon['applicable']:
                continue
            sql = path.read_text(encoding='utf-8')
            try:
                client.query(ref, sql, read_only=False)
                version = path.name.split('_')[0]
                client.query(ref, "insert into supabase_migrations.schema_migrations (version, name) values "
                                  f"('{version}', '{path.name}') on conflict (version) do nothing", read_only=False)
                applied_now.append(path.name)
            except HandoffFailure as exc:
                application['stopped_at'] = {'file': path.name, 'reason': str(exc)}
                break
        final_snapshot = take_snapshot()
        recon = reconcile(names, [s.split('_')[0] for s in [*ledger, *applied_now]], final_snapshot)
        checks['reconciliation'] = recon
    checks['application'] = application
    checks['schema_contract'] = required_columns_status(final_snapshot)

    try:
        raw_config = client.json('GET', f'/v1/projects/{ref}/config/auth')
    except HandoffFailure as exc:
        checks['auth'] = {'status': 'failed', 'reason': str(exc)}
        raw_config = None
    else:
        config = sanitize_auth_config(raw_config)
        verdict = auth_verdict(config, origin)
        if verdict['status'] != 'passed' and apply:
            body = auth_fix_body(config, origin)
            if body:
                response = client._call('PATCH', f'/v1/projects/{ref}/config/auth', json=body)
                if response.status_code == 200:
                    config = sanitize_auth_config(client.json('GET', f'/v1/projects/{ref}/config/auth'))
                    verdict = {**auth_verdict(config, origin), 'fix_applied': True}
                else:
                    verdict['fix'] = {'status': 'failed', 'http_status': response.status_code}
        checks['auth'] = verdict

    reconciled = not checks['reconciliation']['pending'] and not checks['reconciliation']['inconsistent']
    healthy = (reconciled and checks['schema_contract']['status'] == 'passed'
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
            'project': checks.get('project'),
            'applied_this_run': report.get('migrations_applied_this_run'),
            'application_stopped_at': (checks.get('application') or {}).get('stopped_at'),
            'pending': recon.get('pending'), 'inconsistent': recon.get('inconsistent'),
            'schema_contract': contract,
            'auth': {key: auth.get(key) for key in ('status', 'missing', 'site_url', 'callback_allowed',
                                                    'localhost_urls_present', 'fix_applied', 'reason')
                     if auth.get(key) is not None},
            'tables_present': sorted((before.get('tables') or {}).keys()),
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
