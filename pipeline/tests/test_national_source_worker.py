from discovery import national_source_worker as worker


def test_run_national_batch_only_runs_live_validated_sources_and_rotates_verified_sources(monkeypatch):
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
    assert calls == ["valid", "verified"]
    assert result["attempted"] == 2
    assert result["ok"] == 2


def test_run_national_batch_prioritizes_never_successful_counties(monkeypatch):
    counties = [
        {"county_id": "recent", "coverage_status": "tier_5", "validation_status": "valid", "arcgis_layer_url": "https://example.test/recent", "last_successful_run": "2026-09-04T12:00:00+00:00"},
        {"county_id": "old", "coverage_status": "tier_5", "validation_status": "valid", "arcgis_layer_url": "https://example.test/old", "last_successful_run": "2026-09-01T12:00:00+00:00"},
        {"county_id": "never", "coverage_status": "tier_3", "validation_status": "valid", "arcgis_layer_url": "https://example.test/never"},
    ]
    calls=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "list_counties", lambda: counties)
    monkeypatch.setattr(worker, "run_county", lambda *args, **kwargs: calls.append(args[0]) or {"status": "ok"})
    result=worker.run_national_batch(limit=2)
    assert result["attempted"] == 2
    assert calls == ["never", "old"]


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
    monkeypatch.setattr(worker, "_statewide_queue", lambda *args, **kwargs: [])
    result=worker.discover_and_register(limit=2)
    assert result["attempted"] == 2
    assert attempted == ["new", "newer"]


def test_discovery_falls_back_when_statewide_queue_fails(monkeypatch):
    counties = [{
        "county_id": "fallback", "county_name": "Fallback County", "state": "Arizona",
        "coverage_status": "tier_0",
    }]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "list_counties", lambda: counties)
    monkeypatch.setattr(worker, "_statewide_queue", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("statewide unavailable")))
    monkeypatch.setattr(worker, "update_county", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "discover_arcgis_county_config", lambda *args: None)

    result = worker.discover_and_register(limit=1)

    assert result["attempted"] == 1
    assert result["statewide_queued"] == 0
    assert "statewide_error" in result


def test_run_statewide_batch_scopes_discovery_and_runs_discovered_counties(monkeypatch):
    queue = [
        {"county_id": "nc_001", "state": "North Carolina"},
        {"county_id": "nc_002", "state": "North Carolina"},
    ]
    registry = [
        {"county_id": "nc_001", "county_name": "Alpha", "state": "North Carolina", "state_fips": "37", "county_fips": "001", "arcgis_layer_url": "https://example.test/nc1"},
        {"county_id": "nc_002", "county_name": "Beta", "state": "North Carolina", "state_fips": "37", "county_fips": "003", "arcgis_layer_url": "https://example.test/nc2"},
    ]
    calls=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "_statewide_queue", lambda states=None: queue)
    monkeypatch.setattr(worker, "discover_and_register", lambda limit=25, states=None: {"attempted": 2, "found": 2, "results":[{"county_id":"nc_001","status":"discovered"},{"county_id":"nc_002","status":"discovered"}]})
    monkeypatch.setattr(worker, "list_counties", lambda: registry)
    monkeypatch.setattr(worker, "run_county", lambda cid, **kwargs: calls.append((cid, kwargs["mode"])) or {"county_id":cid,"status":"ok"})

    result = worker.run_statewide_batch(states=["North Carolina"], discovery_limit=10, etl_limit=1, mode="dry_run")

    assert result["states"] == ["north carolina"]
    assert result["statewide_queued"] == 2
    assert result["etl"]["attempted"] == 1
    assert result["etl"]["ok"] == 1
    assert calls == [("nc_001", "dry_run")]


def test_discover_and_register_scopes_fallback_candidates_to_requested_states(monkeypatch):
    counties = [
        {"county_id":"nc","county_name":"NC County","state":"North Carolina","coverage_status":"tier_0"},
        {"county_id":"az","county_name":"AZ County","state":"Arizona","coverage_status":"tier_0"},
    ]
    attempted=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "list_counties", lambda: counties)
    monkeypatch.setattr(worker, "_statewide_queue", lambda states=None: [])
    monkeypatch.setattr(worker, "update_county", lambda cid, **fields: attempted.append(cid))
    monkeypatch.setattr(worker, "discover_arcgis_county_config", lambda *args: None)

    result = worker.discover_and_register(limit=10, states=["North Carolina"])

    assert result["attempted"] == 1
    assert attempted == ["nc"]
