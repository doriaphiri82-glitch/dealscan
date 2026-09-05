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
        importlib.reload(database)
    except RuntimeError as exc:
        assert "SUPABASE_URL" in str(exc)
    else:
        raise AssertionError("Supabase mode should fail fast without credentials")
