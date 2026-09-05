import pytest
from database_supabase import SupabaseDatabase

class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self._payload = payload if payload is not None else []
        self.status_code = status_code; self.text = text; self.ok = status_code < 400
    def json(self): return self._payload

def test_requires_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False); monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        SupabaseDatabase()

def test_property_and_deal_round_trip_payloads(monkeypatch):
    db = SupabaseDatabase("https://example.supabase.co", "service-key"); calls=[]
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        calls.append((method,url,kwargs.get("params"),kwargs.get("json")))
        if url.endswith("/counties") and method == "GET": return FakeResponse([])
        if url.endswith("/counties") and method == "POST": return FakeResponse([{"county_id":"test_county"}])
        if url.endswith("/properties"): return FakeResponse([{"id":42}])
        if url.endswith("/deals") and method == "GET": return FakeResponse([])
        if url.endswith("/deals") and method == "POST": return FakeResponse([{"id":77}])
        raise AssertionError((method,url))
    monkeypatch.setattr("database_supabase.requests.request", fake_request)
    pid=db.save_property({"apn":"A-1","county_id":"test_county","county_name":"Test County","address":"1 Main St"})
    did=db.save_deal({"property_id":pid,"deal_score":81,"source_url":"https://source.test/1"})
    assert pid == 42 and did == 77
    assert any(x[0]=="POST" and x[1].endswith("/properties") for x in calls)
    assert any(x[0]=="POST" and x[1].endswith("/deals") for x in calls)

def test_source_validation_never_promotes_a_deal_to_verified(monkeypatch):
    db = SupabaseDatabase("https://example.supabase.co", "service-key"); captured={}
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        if url.endswith("/deals") and method == "GET": return FakeResponse([])
        if url.endswith("/deals") and method == "POST":
            captured["payload"] = kwargs.get("json")
            return FakeResponse([{"id":88}])
        raise AssertionError((method,url))
    monkeypatch.setattr("database_supabase.requests.request", fake_request)
    did = db.save_deal({"property_id":42,"deal_score":81,"verification_status":"source_verified"})
    assert did == 88
    assert captured["payload"]["verification_status"] == "source_verified"

def test_get_top_deals_requires_verified_publication(monkeypatch):
    db = SupabaseDatabase("https://example.supabase.co", "service-key"); calls=[]
    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        calls.append((method,url,kwargs.get("params")))
        return FakeResponse([])
    monkeypatch.setattr("database_supabase.requests.request", fake_request)
    assert db.get_top_deals(limit=25, min_score=40) == []
    params = next(item[2] for item in calls if item[0] == "GET" and item[1].endswith("/deals"))
    assert params["status"] == "eq.discovered"
    assert params["verification_status"] == "eq.verified"

def test_errors_include_http_detail(monkeypatch):
    db=SupabaseDatabase("https://example.supabase.co","service-key")
    monkeypatch.setattr("database_supabase.requests.request", lambda *a,**k: FakeResponse(status_code=500,text="database unavailable"))
    with pytest.raises(RuntimeError, match="database unavailable"): db.get_top_deals()
