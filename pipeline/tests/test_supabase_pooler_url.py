"""Offline contracts for the IPv4 Session Pooler DSN derivation.

All credentials here are fixtures. No network, no secrets, no real project ref.
"""
import pytest
from validation import supabase_pooler_url as pooler

REF = 'abcdefghijklmnopqrst'
# Percent-encoded on purpose: urlsplit() does not decode it and neither may we.
PASSWORD = 'p%40ss%3Aw%25rd'
DIRECT = f'postgresql://postgres:{PASSWORD}@db.{REF}.supabase.co:5432/postgres?sslmode=require'


def test_direct_host_is_rewritten_onto_the_session_pooler(monkeypatch):
    monkeypatch.delenv('DEALSCAN_SUPABASE_REGION', raising=False)
    dsn = pooler.session_pooler_dsn(DIRECT)
    assert dsn == (f'postgresql://postgres.{REF}:{PASSWORD}'
                   '@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require')
    # Password spliced verbatim: never decoded, never re-encoded.
    assert PASSWORD in dsn and 'p@ss' not in dsn


def test_pooler_host_passes_through_unchanged(monkeypatch):
    monkeypatch.delenv('DEALSCAN_SUPABASE_REGION', raising=False)
    already = (f'postgres://postgres.{REF}:{PASSWORD}'
               '@aws-0-eu-west-1.pooler.supabase.com:5432/postgres')
    assert pooler.session_pooler_dsn(already) == already


def test_session_port_5432_is_used_even_when_the_secret_says_6543(monkeypatch):
    monkeypatch.delenv('DEALSCAN_SUPABASE_REGION', raising=False)
    dsn = pooler.session_pooler_dsn(
        f'postgresql://postgres:{PASSWORD}@db.{REF}.supabase.co:6543/postgres')
    # Transaction mode cannot serve pg_dump; derivation must never emit 6543.
    assert ':5432/postgres' in dsn and '6543' not in dsn


def test_region_override_is_honoured_and_validated(monkeypatch):
    monkeypatch.setenv('DEALSCAN_SUPABASE_REGION', 'us-east-1')
    assert 'aws-0-us-east-1.pooler.supabase.com:5432' in pooler.session_pooler_dsn(DIRECT)
    monkeypatch.setenv('DEALSCAN_SUPABASE_REGION', 'eu_west_1; drop table x')
    with pytest.raises(pooler.PoolerUrlError, match='DEALSCAN_SUPABASE_REGION'):
        pooler.session_pooler_dsn(DIRECT)


def test_unsupported_inputs_are_rejected_without_echoing_the_value():
    for value in ('',
                  f'https://db.{REF}.supabase.co:5432/postgres',
                  f'postgresql://postgres:{PASSWORD}@db.internal.example:5432/postgres',
                  f'postgresql://postgres:{PASSWORD}@supabase.co/postgres',
                  'postgresql:///postgres'):
        with pytest.raises(pooler.PoolerUrlError) as caught:
            pooler.session_pooler_dsn(value)
        message = str(caught.value)
        assert PASSWORD not in message and '@' not in message and REF not in message


def test_cli_masks_before_emitting_and_leaks_nothing_on_failure(monkeypatch, capsys):
    monkeypatch.delenv('DEALSCAN_SUPABASE_REGION', raising=False)
    monkeypatch.setenv('SUPABASE_DB_URL', DIRECT)
    assert pooler.main(['--emit-mask']) == 0
    masked = capsys.readouterr()
    assert masked.out.startswith('::add-mask::postgresql://postgres.') and masked.err == ''
    assert pooler.main(['--dsn']) == 0
    assert capsys.readouterr().out.strip().endswith('/postgres?sslmode=require')

    monkeypatch.setenv('SUPABASE_DB_URL', f'mysql://root:{PASSWORD}@db.{REF}.supabase.co/postgres')
    assert pooler.main(['--emit-mask', '--dsn']) == 1
    failed = capsys.readouterr()
    # Nothing on stdout: a $() capture must stay empty rather than take junk.
    assert failed.out == '' and failed.err.startswith('::warning title=')
    assert PASSWORD not in failed.err
