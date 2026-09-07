"""Derive an IPv4-reachable Supabase Session Pooler DSN from SUPABASE_DB_URL.

GitHub-hosted runners are IPv4-only, while the direct database host
``db.<ref>.supabase.co`` resolves to IPv6 only unless the project pays for the
IPv4 add-on. `pg_dump`/`psql` therefore fail on the runner with "Network is
unreachable" even though the secret itself is valid. Supavisor's **session**
pooler (``aws-<shard>-<region>.pooler.supabase.com`` port **5432**, user
``postgres.<ref>``) is dual-stack and speaks the full PostgreSQL protocol,
which `pg_dump` needs; transaction mode (port 6543) multiplexes statements and
is not usable for a dump, so this module never emits 6543.

Two rewrites are applied, both learned from live runs:

* a direct ``db.<ref>.supabase.co`` host becomes the session pooler endpoint;
* a host that is **already** a pooler endpoint keeps its host, but its username
  is tenant-qualified to ``postgres.<ref>`` when the project ref is known and
  its port is forced to session mode. Supavisor parses the tenant out of the
  username, so a plain ``postgres`` user against a pooler host is rejected at
  authentication — exactly what run 34158289491 reported.

Only the network endpoint and the username are ever rewritten. The password is
copied **verbatim**: it is already percent-encoded in the secret, so decoding or
re-encoding it would corrupt credentials containing ``%``, ``@`` or ``:``.
Parsing is done by hand rather than with :func:`urllib.parse.urlsplit`, which
raises ``Invalid IPv6 URL`` on an unencoded ``[``/``]`` in the password and
would abort the derivation instead of diagnosing it; the split mirrors libpq
(authority ends at the first ``/``, ``?`` or ``#``; userinfo ends at the first
``@``). No credential value is ever logged, returned in an error message or
written to a report: failures and diagnostics name categories only, and the CLI
masks the derived DSN in the Actions log before any step can capture it.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import string
import sys

POOLER_PORT = '5432'  # Session mode. 6543 is transaction mode and cannot serve pg_dump.
TRANSACTION_PORT = '6543'  # Diagnostic only: proves whether the tenant/password work at all.
POOLER_SUFFIX = '.pooler.supabase.com'
DEFAULT_REGION = 'eu-west-1'
DEFAULT_SHARD = 'aws-0'
REGION_PATTERN = re.compile(r'^[a-z]+-[a-z]+-[0-9]+$')
SHARD_PATTERN = re.compile(r'^aws-[0-9]+$')
REF_PATTERN = re.compile(r'^[a-z0-9]{8,64}$')
DIRECT_HOST_PATTERN = re.compile(r'^db\.(?P<ref>[a-z0-9]{8,64})\.supabase\.co$')
POSTGRES_SCHEMES = ('postgres', 'postgresql')
# RFC 3986 userinfo: unreserved / pct-encoded / sub-delims / ":".
_USERINFO_SAFE = set(string.ascii_letters + string.digits + "-._~!$&'()*+,;=:")
_PLACEHOLDERS = ('your-password', 'your_password', 'yourpassword', 'password-here', 'db-password')


class PoolerUrlError(RuntimeError):
    """Raised with a credential-free reason; never carries any part of the DSN."""


def region(explicit: str | None = None) -> str:
    """Pooler region, from the argument or DEALSCAN_SUPABASE_REGION."""
    value = (explicit if explicit is not None else os.getenv('DEALSCAN_SUPABASE_REGION') or '').strip()
    value = value or DEFAULT_REGION
    if not REGION_PATTERN.fullmatch(value):
        raise PoolerUrlError('DEALSCAN_SUPABASE_REGION must look like eu-west-1')
    return value


def shard() -> str:
    """Supavisor host shard prefix; Supabase has used both aws-0 and aws-1."""
    value = (os.getenv('DEALSCAN_SUPABASE_POOLER_SHARD') or '').strip() or DEFAULT_SHARD
    if not SHARD_PATTERN.fullmatch(value):
        raise PoolerUrlError('DEALSCAN_SUPABASE_POOLER_SHARD must look like aws-0')
    return value


def project_ref(explicit: str | None = None) -> str:
    """Project ref from the argument, DEALSCAN_SUPABASE_PROJECT_REF or SUPABASE_URL."""
    value = (explicit or os.getenv('DEALSCAN_SUPABASE_PROJECT_REF') or '').strip()
    if not value:
        url = (os.getenv('SUPABASE_URL') or '').strip()
        match = re.fullmatch(r'https://([a-z0-9]{8,64})\.supabase\.co/?', url)
        value = match.group(1) if match else ''
    if value and not REF_PATTERN.fullmatch(value):
        raise PoolerUrlError('Project ref must be lowercase alphanumeric')
    return value


def parse_dsn(raw: str) -> dict:
    """Split a PostgreSQL URI the way libpq does, preserving every byte.

    Returns ``scheme``, ``username``/``password`` exactly as written (still
    percent-encoded), ``host``, ``port`` and ``tail`` (path + query + fragment).
    """
    text = str(raw or '').strip()
    if not text:
        raise PoolerUrlError('SUPABASE_DB_URL is empty')
    scheme, separator, rest = text.partition('://')
    if not separator:
        raise PoolerUrlError('SUPABASE_DB_URL must be a postgres:// URI, not a keyword/value DSN')
    if scheme.lower() not in POSTGRES_SCHEMES:
        raise PoolerUrlError('SUPABASE_DB_URL must use the postgres:// or postgresql:// scheme')
    cut = len(rest)
    for character in '/?#':
        found = rest.find(character)
        if found != -1:
            cut = min(cut, found)
    authority, tail = rest[:cut], rest[cut:]
    userinfo, at_sign, hostport = authority.partition('@')
    if not at_sign:
        userinfo, hostport = '', authority
    username, _colon, password = userinfo.partition(':')
    if hostport.startswith('['):
        raise PoolerUrlError('SUPABASE_DB_URL uses an IPv6 literal host, which an IPv4-only runner cannot reach')
    host, _sep, port = hostport.rpartition(':')
    if not _sep:
        host, port = hostport, ''
    if not host:
        raise PoolerUrlError('SUPABASE_DB_URL has no host')
    if port and not port.isdigit():
        raise PoolerUrlError('SUPABASE_DB_URL has a non-numeric port (an unencoded character in the password can cause this)')
    return {'scheme': scheme.lower(), 'username': username, 'password': password,
            'host': host.lower(), 'port': port, 'tail': tail}


def _rebuild(parts: dict, username: str, host: str, port: str) -> str:
    userinfo = username
    if parts['password']:
        userinfo = f'{username}:{parts["password"]}'  # verbatim, still percent-encoded
    return f'{parts["scheme"]}://{userinfo}@{host}:{port}{parts["tail"]}'


def session_pooler_dsn(database_url: str, pooler_region: str | None = None,
                       ref: str | None = None, mode: str = 'session') -> str:
    """Return a DSN reachable and authenticable from an IPv4-only runner.

    ``db.<ref>.supabase.co`` URLs are rewritten onto the session pooler; hosts
    that are already Supavisor endpoints keep their host but get a
    tenant-qualified username and session-mode port; every other host raises,
    because silently trusting an unknown host would hide a misconfigured secret.
    """
    if mode not in ('session', 'transaction'):
        raise PoolerUrlError('Pooler mode must be session or transaction')
    port = POOLER_PORT if mode == 'session' else TRANSACTION_PORT
    parts = parse_dsn(database_url)
    host = parts['host']
    if host.endswith(POOLER_SUFFIX):
        known_ref = project_ref(ref)
        username = parts['username']
        if username and '.' not in username and known_ref:
            # Supavisor routes on the tenant suffix; plain "postgres" is rejected.
            username = f'{username}.{known_ref}'
        if username == parts['username'] and parts['port'] == port:
            return str(database_url).strip()  # already correct: pass through untouched
        return _rebuild(parts, username or 'postgres', host, port)
    match = DIRECT_HOST_PATTERN.fullmatch(host)
    if not match:
        raise PoolerUrlError('SUPABASE_DB_URL host is neither db.<ref>.supabase.co nor a *.pooler.supabase.com endpoint')
    derived_ref = match.group('ref')
    pooler_host = f'{shard()}-{region(pooler_region)}{POOLER_SUFFIX}'
    return _rebuild(parts, f'postgres.{derived_ref}', pooler_host, port)


def diagnose(database_url: str) -> dict:
    """Credential-free description of why a DSN can or cannot authenticate.

    Reports shape only — never a credential value, never which character is
    wrong. ``placeholder_suspect`` matches the dashboard's literal
    ``[YOUR-PASSWORD]`` text, which is not a real secret.
    """
    report: dict = {'parsed': False}
    try:
        parts = parse_dsn(database_url)
    except PoolerUrlError as exc:
        report['reason'] = str(exc)
        return report
    password = parts['password']
    lowered = password.lower()
    host = parts['host']
    report.update({
        'parsed': True,
        'host_class': ('session_pooler' if host.endswith(POOLER_SUFFIX) and parts['port'] == POOLER_PORT
                       else 'transaction_pooler' if host.endswith(POOLER_SUFFIX)
                       else 'direct_ipv6_only' if DIRECT_HOST_PATTERN.fullmatch(host) else 'unknown'),
        'port': parts['port'] or 'default',
        'username_tenant_qualified': bool(parts['username']) and '.' in parts['username'],
        'password_present': bool(password),
        'password_uri_safe': all(character in _USERINFO_SAFE or character == '%' for character in password)
                             and re.fullmatch(r'(?:[^%]|%[0-9A-Fa-f]{2})*', password) is not None,
        'placeholder_suspect': any(token in lowered for token in _PLACEHOLDERS)
                               or (password.startswith('[') and password.endswith(']')),
        'project_ref_available': bool(project_ref()),
    })
    blockers = []
    if not report['password_present']:
        blockers.append('password_missing')
    if report['placeholder_suspect']:
        blockers.append('password_is_the_dashboard_placeholder')
    elif not report['password_uri_safe']:
        blockers.append('password_not_percent_encoded')
    if report['host_class'] == 'unknown':
        blockers.append('unrecognised_host')
    if (not report['username_tenant_qualified'] and host.endswith(POOLER_SUFFIX)
            and not report['project_ref_available']):
        blockers.append('pooler_username_not_tenant_qualified_and_ref_unknown')
    report['blockers'] = blockers
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Derive the IPv4 Session Pooler DSN for SUPABASE_DB_URL.')
    parser.add_argument('--emit-mask', action='store_true',
                        help='Print an ::add-mask:: workflow command so the derived DSN is redacted in logs')
    parser.add_argument('--dsn', action='store_true',
                        help='Print the derived DSN on stdout (only for $() capture into GITHUB_ENV)')
    parser.add_argument('--diagnose', metavar='FILE', default=None,
                        help='Write a credential-free shape diagnosis for the operator')
    parser.add_argument('--region', default=None, help='Override DEALSCAN_SUPABASE_REGION')
    parser.add_argument('--mode', choices=('session', 'transaction'), default='session',
                        help='session (5432, required by pg_dump) or transaction (6543, diagnostic only)')
    args = parser.parse_args(argv)
    if not (args.emit_mask or args.dsn or args.diagnose):
        parser.error('choose --emit-mask, --dsn and/or --diagnose')
    raw = os.getenv('SUPABASE_DB_URL', '')
    if args.diagnose:
        report = diagnose(raw)
        with open(args.diagnose, 'w') as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
        print(f'::notice title=SUPABASE_DB_URL shape (no values)::{json.dumps(report, sort_keys=True)}',
              file=sys.stderr)
    try:
        dsn = session_pooler_dsn(raw, args.region, mode=args.mode)
    except PoolerUrlError as exc:
        # Reason only, never a value; stderr so a $() capture stays empty.
        print(f'::warning title=Session Pooler DSN not derived::{exc}', file=sys.stderr)
        return 1
    if args.emit_mask:
        print(f'::add-mask::{dsn}')
    if args.dsn:
        print(dsn)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
