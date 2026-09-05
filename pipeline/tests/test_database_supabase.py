import os

import pytest

from database_supabase import SupabaseDatabase


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self._payload = payload if payload is not None else []
        self.status_code = status_code
        self.text = text
        self.ok = status_code < 400

    def json(self):
        return self._payload


def test_supabase_requires_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(RuntimeError):
        SupabaseDatabase()


def test_property_upsert_and_deal_queries(monkeypatch):
    db = SupabaseDatabase("https://example.supabase.co", "service-key")
    calls = []

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        calls.append((method, url, kwargs.get("params"), kwargs.get("json")))
        if url.endswith("/counties") and method == "GET":
            return FakeResponse([])
        if url.endswith("/counties") and method == "POST":
            return FakeResponse([{"county_id": "test_county"}])
        if url.endswith("/properties"):
            return FakeResponse([{"id": 42}])
        if url.endswith("/deals") and method == "GET":
            return FakeResponse([])
        if url.endswith("/deals") and method == "POST":
            return FakeResponse([{"id": 77}])
        raise AssertionError((method, url, kwargs))

    monkeypatch.setattr("database_supabase.requests.request", fake_request)
    pid = db.save_property({"apn": "A-1", "county_id": "test_county", "address": "1 Main St"})
    did = db.save_deal({"property_id": pid, "deal_score": 81, "source_url": "https://source.test/1"})
    assert pid == 42
    assert did == 77
    assert any(c[0] == "POST" and c[1].endswith("/properties") for c in calls)
    assert any(c[0] == "POST" and c[1].endswith("/deals") for c in calls)


def test_supabase_errors_are_actionable(monkeypatch):
    db = SupabaseDatabase("https://example.supabase.co", "service-key")

    def fake_request(*args, **kwargs):
        return FakeResponse(status_code=500, text="database unavailable")

    monkeypatch.setattr("database_supabase.requests.request", fake_request)
    with pytest.raises(RuntimeError, match="database unavailable"):
        db.get_top_deals()
