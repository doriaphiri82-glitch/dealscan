import importlib


def test_sqlite_backend_remains_default(monkeypatch):
    monkeypatch.delenv("DEALSCAN_DB_BACKEND", raising=False)
    import database
    database = importlib.reload(database)
    assert database._USE_SUPABASE is False
    assert callable(database.init_db)


def test_supabase_backend_requires_credentials(monkeypatch):
    monkeypatch.setenv("DEALSCAN_DB_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    import database
    try:
        with __import__("pytest").raises(RuntimeError, match="SUPABASE_URL"):
            importlib.reload(database)
    finally:
        # Reload the module under the default backend after exercising the
        # fail-fast path. A failed reload can leave partially initialized
        # module globals behind, which otherwise leaks Supabase mode into
        # subsequent SQLite tests.
        monkeypatch.delenv("DEALSCAN_DB_BACKEND", raising=False)
        importlib.reload(database)
