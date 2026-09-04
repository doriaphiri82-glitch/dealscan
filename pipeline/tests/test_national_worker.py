from discovery import national_source_worker


def test_national_etl_only_runs_live_validated_counties(monkeypatch):
    counties = [
        {"county_id": "invalid", "validation_status": "invalid", "coverage_status": "tier_1", "arcgis_layer_url": "https://invalid"},
        {"county_id": "pending", "validation_status": "pending", "coverage_status": "tier_1", "arcgis_layer_url": "https://pending"},
        {"county_id": "valid", "validation_status": "valid", "coverage_status": "tier_3", "arcgis_layer_url": "https://valid"},
        {"county_id": "published", "validation_status": "valid", "coverage_status": "tier_5", "arcgis_layer_url": "https://published"},
    ]
    calls = []
    monkeypatch.setattr(national_source_worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(national_source_worker, "list_counties", lambda: counties)
    monkeypatch.setattr(national_source_worker, "run_county", lambda county_id, **kwargs: calls.append(county_id) or {"county_id": county_id, "status": "ok"})

    result = national_source_worker.run_national_batch(limit=10)

    assert result["attempted"] == 2
    assert calls == ["valid", "published"]


def test_national_etl_rotates_oldest_successful_run_first(monkeypatch):
    counties = [
        {"county_id": "recent", "county_name": "Recent County", "state": "Arizona", "validation_status": "valid", "coverage_status": "tier_5", "arcgis_layer_url": "https://recent", "last_successful_run": "2026-09-03T12:00:00+00:00"},
        {"county_id": "never", "county_name": "Never County", "state": "Arizona", "validation_status": "valid", "coverage_status": "tier_3", "arcgis_layer_url": "https://never"},
        {"county_id": "old", "county_name": "Old County", "state": "Arizona", "validation_status": "valid", "coverage_status": "tier_5", "arcgis_layer_url": "https://old", "last_successful_run": "2026-09-01T12:00:00+00:00"},
    ]
    calls = []
    monkeypatch.setattr(national_source_worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(national_source_worker, "list_counties", lambda: counties)
    monkeypatch.setattr(national_source_worker, "run_county", lambda county_id, **kwargs: calls.append(county_id) or {"county_id": county_id, "status": "ok"})

    result = national_source_worker.run_national_batch(limit=2)

    assert result["attempted"] == 2
    assert calls == ["never", "old"]


def test_discovery_prioritizes_never_attempted_counties(monkeypatch):
    counties = [
        {"county_id": "old", "county_name": "Old County", "state": "Arizona", "coverage_status": "tier_1", "discovery_attempted_at": "2026-09-01T00:00:00+00:00"},
        {"county_id": "new", "county_name": "New County", "state": "Arizona", "coverage_status": "tier_1"},
    ]
    attempted = []
    monkeypatch.setattr(national_source_worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(national_source_worker, "list_counties", lambda: counties)
    monkeypatch.setattr(national_source_worker, "update_county", lambda cid, **kwargs: attempted.append(cid))
    monkeypatch.setattr(national_source_worker, "discover_arcgis_county_config", lambda *args: None)

    result = national_source_worker.discover_and_register(limit=1)

    assert result["attempted"] == 1
    assert attempted == ["new"]
