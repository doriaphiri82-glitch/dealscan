"""Offline tests must never inherit production credentials or write real stores."""
import os
import pytest

# Apply before test-module imports: database.py selects its backend on import.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DEALSCAN_DB_BACKEND'] = 'sqlite'
for name in ('DEALSCAN_ENV', 'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'DEALSCAN_ACTIVE_AUDIT_RUN_ID', 'KV_REST_API_URL', 'KV_REST_API_TOKEN', 'REDIS_URL', 'EMAIL_API_KEY'):
    os.environ.pop(name, None)


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    import config.counties.registry as registry
    import runregistry
    import config.settings as settings
    import database
    database.get_backend().clear_active_run()
    database.get_backend().audit_failures.clear()
    monkeypatch.setattr(registry, 'REGISTRY_PATH', str(tmp_path / 'counties.json'))
    monkeypatch.setattr(runregistry, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(runregistry, 'REGISTRY_PATH', str(tmp_path / 'runs.json'))
    monkeypatch.setattr(runregistry, 'BUNDLE_PATH', str(tmp_path / 'bundle.json'))
    monkeypatch.setattr(settings, 'DATABASE_PATH', str(tmp_path / 'local.db'))
    monkeypatch.setattr(database, 'DATABASE_PATH', str(tmp_path / 'local.db'))
    monkeypatch.setattr('scrapers.base.CACHE_DIR', str(tmp_path / 'http-cache'))

    def no_network(*args, **kwargs):
        raise AssertionError('Offline tests must mock network transport')
    monkeypatch.setattr('requests.sessions.Session.request', no_network)
    monkeypatch.setattr('urllib.request.urlopen', no_network)
