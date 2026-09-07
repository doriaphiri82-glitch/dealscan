"""Offline contracts for the IPv4 Session Pooler DSN derivation.

All credentials here are fixtures. No network, no secrets, no real project ref.
"""
import json
import pytest
from validation import supabase_pooler_url as pooler

REF = 'abcdefghijklmnopqrst'
# Percent-encoded on purpose: the secret stores it encoded and we must not touch it.
PASSWORD = 'p%40ss%3Aw%25rd'
DIRECT = f'postgresql://postgres:{PASSWORD}@db.{REF}.supabase.co:5432/postgres?sslmode=require'


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ('DEALSCAN_SUPABASE_REGION', 'DEALSCAN_SUPABASE_POOLER_SHARD',
                 'DEALSCAN_SUPABASE_PROJECT_REF', 'SUPABASE_URL', 'SUPABASE_DB_URL'):
        monkeypatch.delenv(name, raising=False)


def test_direct_host_is_rewritten_onto_the_session_pooler():
    dsn = pooler.session_pooler_dsn(DIRECT)
    assert dsn == (f'postgresql://postgres.{REF}:{PASSWORD}'
                   '@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require')
    # Password spliced verbatim: never decoded, never re-encoded.
    assert PASSWORD in dsn and 'p@ss' not in dsn


def test_correct_pooler_host_passes_through_unchanged():
    already = (f'postgres://postgres.{REF}:{PASSWORD}'
               '@aws-1-eu-west-1.pooler.supabase.com:5432/postgres')
    assert pooler.session_pooler_dsn(already) == already


def test_session_port_5432_is_used_even_when_the_secret_says_6543():
    dsn = pooler.session_pooler_dsn(
        f'postgresql://postgres:{PASSWORD}@db.{REF}.supabase.co:6543/postgres')
    # Transaction mode cannot serve pg_dump; derivation must never emit 6543.
    assert ':5432/postgres' in dsn and '6543' not in dsn


def test_region_and_shard_overrides_are_honoured_and_validated(monkeypatch):
    monkeypatch.setenv('DEALSCAN_SUPABASE_REGION', 'us-east-1')
    monkeypatch.setenv('DEALSCAN_SUPABASE_POOLER_SHARD', 'aws-1')
    assert 'aws-1-us-east-1.pooler.supabase.com:5432' in pooler.session_pooler_dsn(DIRECT)
    monkeypatch.setenv('DEALSCAN_SUPABASE_REGION', 'eu_west_1; drop table x')
    with pytest.raises(pooler.PoolerUrlError, match='DEALSCAN_SUPABASE_REGION'):
        pooler.session_pooler_dsn(DIRECT)


def test_unsupported_inputs_are_rejected_without_echoing_the_value():
    for value in ('',
                  f'https://db.{REF}.supabase.co:5432/postgres',
                  f'postgresql://postgres:{PASSWORD}@db.internal.example:5432/postgres',
                  f'postgresql://postgres:{PASSWORD}@supabase.co/postgres',
                  f'host=db.{REF}.supabase.co user=postgres password={PASSWORD}',
                  'postgresql:///postgres'):
        with pytest.raises(pooler.PoolerUrlError) as caught:
            pooler.session_pooler_dsn(value)
        message = str(caught.value)
        assert PASSWORD not in message and '@' not in message and REF not in message


def test_cli_masks_before_emitting_and_leaks_nothing_on_failure(monkeypatch, capsys):
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


# --- Contracts added from live run 34158289491 evidence -------------------

def test_pooler_username_is_tenant_qualified_from_the_project_ref(monkeypatch):
    """Supavisor routes on the tenant suffix; plain postgres fails auth."""
    monkeypatch.setenv('SUPABASE_URL', f'https://{REF}.supabase.co')
    stored = f'postgresql://postgres:{PASSWORD}@aws-1-eu-west-1.pooler.supabase.com:5432/postgres'
    assert pooler.session_pooler_dsn(stored) == (
        f'postgresql://postgres.{REF}:{PASSWORD}@aws-1-eu-west-1.pooler.supabase.com:5432/postgres')
    # Host and shard are preserved exactly; only the username changed.
    monkeypatch.delenv('SUPABASE_URL')
    assert pooler.session_pooler_dsn(stored) == stored  # unknown ref: never guess


def test_transaction_mode_pooler_is_moved_to_session_mode(monkeypatch):
    monkeypatch.setenv('DEALSCAN_SUPABASE_PROJECT_REF', REF)
    dsn = pooler.session_pooler_dsn(
        f'postgresql://postgres.{REF}:{PASSWORD}@aws-1-eu-west-1.pooler.supabase.com:6543/postgres')
    assert dsn.endswith('@aws-1-eu-west-1.pooler.supabase.com:5432/postgres')


def test_unencoded_bracket_password_is_parsed_not_crashed():
    """urlsplit() raises 'Invalid IPv6 URL' here; libpq-style parsing must not."""
    parts = pooler.parse_dsn(
        'postgresql://postgres:[YOUR-PASSWORD]@aws-1-eu-west-1.pooler.supabase.com:5432/postgres')
    assert parts['host'] == 'aws-1-eu-west-1.pooler.supabase.com' and parts['port'] == '5432'
    assert parts['username'] == 'postgres' and parts['password'] == '[YOUR-PASSWORD]'


def test_diagnosis_names_blockers_without_revealing_any_credential(tmp_path, capsys):
    report = pooler.diagnose(
        'postgresql://postgres:[YOUR-PASSWORD]@aws-1-eu-west-1.pooler.supabase.com:5432/postgres')
    assert report['host_class'] == 'session_pooler'
    assert report['username_tenant_qualified'] is False
    assert report['placeholder_suspect'] is True
    assert 'password_is_the_dashboard_placeholder' in report['blockers']
    healthy = pooler.diagnose(f'postgresql://postgres.{REF}:{PASSWORD}'
                              '@aws-1-eu-west-1.pooler.supabase.com:5432/postgres')
    assert healthy['blockers'] == [] and healthy['password_uri_safe'] is True
    assert PASSWORD not in json.dumps(healthy)


def test_transaction_mode_is_available_only_as_an_explicit_diagnostic(monkeypatch):
    """pg_dump needs session mode; 6543 exists solely to classify auth failures."""
    monkeypatch.setenv('DEALSCAN_SUPABASE_PROJECT_REF', REF)
    stored = f'postgresql://postgres.{REF}:{PASSWORD}@aws-1-eu-west-1.pooler.supabase.com:5432/postgres'
    assert pooler.session_pooler_dsn(stored, mode='transaction').endswith(':6543/postgres')
    assert pooler.session_pooler_dsn(stored).endswith(':5432/postgres')
    with pytest.raises(pooler.PoolerUrlError, match='session or transaction'):
        pooler.session_pooler_dsn(stored, mode='6543')
