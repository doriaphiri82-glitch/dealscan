"""Publish adapter tests; no network."""
import importlib


class FakeResponse:
    ok = True

    def json(self):
        return {"result": '{"generated_at":"now","deals":[]}'}


def test_redis_rest_uses_token_and_encodes_keys(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "https://redis.example")
    monkeypatch.setenv("REDIS_TOKEN", "secret-token")
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_TOKEN", raising=False)

    import publish
    importlib.reload(publish)

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(publish, "_request", fake_request)
    assert publish._set_key("deal:APN/123", '{"ok":true}')
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/set/deal%3AAPN%2F123")
    assert calls[0][2]["headers"]["Authorization"] == "Bearer secret-token"

    calls.clear()
    assert publish.read_top() == {"generated_at": "now", "deals": []}
    assert calls[0][2]["headers"]["Authorization"] == "Bearer secret-token"


def test_cache_export_cannot_publish_a_supplied_bundle(monkeypatch):
    import publish,database
    monkeypatch.setenv('ENABLE_CACHE_EXPORT','true')
    monkeypatch.setattr(database,'get_top_deals',lambda **kw:[])
    captured=[]
    monkeypatch.setattr(publish,'_set_key',lambda key,payload:captured.append(payload) or True)
    assert publish.publish_top({'deals':[{'apn':'untrusted','owner_name':'PRIVATE'}]})
    assert 'PRIVATE' not in captured[0] and 'untrusted' not in captured[0]
    assert '"deals":[]' in captured[0]


def test_disabled_cache_export_is_not_a_successful_publication(monkeypatch):
    import publish_live
    monkeypatch.delenv('ENABLE_CACHE_EXPORT',raising=False)
    assert publish_live.main()==1
