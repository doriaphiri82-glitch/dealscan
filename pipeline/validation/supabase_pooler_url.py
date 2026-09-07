"""Derive an IPv4-reachable Supabase Session Pooler DSN from SUPABASE_DB_URL.

GitHub-hosted runners are IPv4-only, while the direct database host
``db.<ref>.supabase.co`` resolves to IPv6 only unless the project pays for the
IPv4 add-on. `pg_dump`/`psql` therefore fail on the runner with "Network is
unreachable" even though the secret itself is valid. Supavisor's **session**
pooler (``aws-0-<region>.pooler.supabase.com`` port **5432**, user
``postgres.<ref>``) is dual-stack and speaks the full PostgreSQL protocol,
which `pg_dump` needs; transaction mode (port 6543) multiplexes statements and
is not usable for a dump, so this module never emits 6543.

Only the network endpoint and the username are rewritten. The password is
spliced **verbatim** out of the original URL: :func:`urllib.parse.urlsplit`
returns the still-percent-encoded substring, so decoding or re-encoding it
would corrupt credentials containing ``%``, ``@`` or ``:``. No credential value
is ever logged, returned in an error message or written to a report: failures
name the category only, and the CLI masks the derived DSN in the Actions log
before any step can capture it.
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from urllib.parse import urlsplit

POOLER_PORT = 5432  # Session mode. 6543 is transaction mode and cannot serve pg_dump.
POOLER_SUFFIX = '.pooler.supabase.com'
DEFAULT_REGION = 'eu-west-1'
REGION_PATTERN = re.compile(r'^[a-z]+-[a-z]+-[0-9]+$')
DIRECT_HOST_PATTERN = re.compile(r'^db\.(?P<ref>[a-z0-9]{8,64})\.supabase\.co$')
POSTGRES_SCHEMES = ('postgres', 'postgresql')


class PoolerUrlError(RuntimeError):
    """Raised with a credential-free reason; never carries any part of the DSN."""


def region(explicit: str | None = None) -> str:
    """Pooler region, from the argument or DEALSCAN_SUPABASE_REGION."""
    value = (explicit if explicit is not None else os.getenv('DEALSCAN_SUPABASE_REGION') or '').strip()
    value = value or DEFAULT_REGION
    if not REGION_PATTERN.fullmatch(value):
        raise PoolerUrlError('DEALSCAN_SUPABASE_REGION must look like eu-west-1')
    return value


def _split_userinfo(netloc: str) -> tuple[str, str]:
    """Return (raw_username, raw_password) exactly as written, still encoded."""
    userinfo, separator, _host = netloc.rpartition('@')
    if not separator:
        return '', ''
    username, _colon, password = userinfo.partition(':')
    return username, password


def session_pooler_dsn(database_url: str, pooler_region: str | None = None) -> str:
    """Return a DSN reachable from an IPv4-only runner.

    ``db.<ref>.supabase.co`` URLs are rewritten onto the session pooler; hosts
    that are already Supavisor pooler endpoints are returned unchanged; every
    other input raises, because silently trusting an unknown host would hide a
    misconfigured secret behind a connection error.
    """
    raw = str(database_url or '').strip()
    if not raw:
        raise PoolerUrlError('SUPABASE_DB_URL is empty')
    try:
        parts = urlsplit(raw)
    except ValueError:
        raise PoolerUrlError('SUPABASE_DB_URL is not a parseable URL') from None
    if parts.scheme.lower() not in POSTGRES_SCHEMES:
        raise PoolerUrlError('SUPABASE_DB_URL must use the postgres:// or postgresql:// scheme')
    try:
        host = (parts.hostname or '').lower()
    except ValueError:
        raise PoolerUrlError('SUPABASE_DB_URL has an unparseable host') from None
    if not host:
        raise PoolerUrlError('SUPABASE_DB_URL has no host')
    if host.endswith(POOLER_SUFFIX):
        return raw  # Already a pooler endpoint: pass through untouched.
    match = DIRECT_HOST_PATTERN.fullmatch(host)
    if not match:
        raise PoolerUrlError('SUPABASE_DB_URL host is neither db.<ref>.supabase.co nor a *.pooler.supabase.com endpoint')
    ref = match.group('ref')
    _username, password = _split_userinfo(parts.netloc)
    userinfo = f'postgres.{ref}'
    if password:
        userinfo = f'{userinfo}:{password}'  # verbatim, still percent-encoded
    netloc = f'{userinfo}@aws-0-{region(pooler_region)}{POOLER_SUFFIX}:{POOLER_PORT}'
    rebuilt = f'{parts.scheme}://{netloc}{parts.path}'
    if parts.query:
        rebuilt += f'?{parts.query}'
    if parts.fragment:
        rebuilt += f'#{parts.fragment}'
    return rebuilt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Derive the IPv4 Session Pooler DSN for SUPABASE_DB_URL.')
    parser.add_argument('--emit-mask', action='store_true',
                        help='Print an ::add-mask:: workflow command so the derived DSN is redacted in logs')
    parser.add_argument('--dsn', action='store_true',
                        help='Print the derived DSN on stdout (only for $() capture into GITHUB_ENV)')
    parser.add_argument('--region', default=None, help='Override DEALSCAN_SUPABASE_REGION')
    args = parser.parse_args(argv)
    if not (args.emit_mask or args.dsn):
        parser.error('choose --emit-mask and/or --dsn')
    try:
        dsn = session_pooler_dsn(os.getenv('SUPABASE_DB_URL', ''), args.region)
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
