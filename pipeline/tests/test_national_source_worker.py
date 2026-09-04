from discovery import national_source_worker as worker


def test_run_national_batch_only_runs_live_validated_sources(monkeypatch):
    counties = [
        {"county_id": "invalid", "coverage_status": "tier_1", "validation_status": "invalid", "arcgis_layer_url": "https://example.test/invalid"},
        {"county_id": "pending", "coverage_status": "tier_1", "validation_status": "pending", "arcgis_layer_url": "https://example.test/pending"},
        {"county_id": "valid", "coverage_status": "tier_1", "validation_status": "valid", "arcgis_layer_url": "https://example.test/valid"},
        {"county_id": "verified", "coverage_status": "tier_5", "validation_status": "valid", "arcgis_layer_url": "https://example.test/verified"},
    ]
    calls=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "list_counties", lambda: counties)
    monkeypatch.setattr(worker, "run_county", lambda *args, **kwargs: calls.append(args[0]) or {"status": "ok"})
    result=worker.run_national_batch(limit=10)
    assert calls == ["valid"]
    assert result["attempted"] == 1
    assert result["ok"] == 1


def test_discovery_prioritizes_never_attempted_counties(monkeypatch):
    counties = [
        {"county_id": "old_failed", "county_name": "Old Failed", "state": "Arizona", "coverage_status": "tier_0", "discovery_attempted_at": "2026-09-01T00:00:00+00:00"},
        {"county_id": "new", "county_name": "New County", "state": "Alabama", "coverage_status": "tier_0"},
        {"county_id": "newer", "county_name": "Newer County", "state": "Alaska", "coverage_status": "tier_0"},
    ]
    attempted=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "list_counties", lambda: counties)
    monkeypatch.setattr(worker, "update_county", lambda cid, **fields: attempted.append(cid))
    monkeypatch.setattr(worker, "discover_arcgis_county_config", lambda *args: None)
    result=worker.discover_and_register(limit=2)
    assert result["attempted"] == 2
    assert attempted == ["new", "newer"]
