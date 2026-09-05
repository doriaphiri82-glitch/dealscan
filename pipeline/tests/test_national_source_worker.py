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


def test_run_statewide_batch_reuses_snapshot_queue_and_refreshes_coverage(monkeypatch):
    queue = [{"county_id": "nc_001", "state": "North Carolina"}, {"county_id": "nc_002", "state": "North Carolina"}]
    reconciled = [{"county_id": "nc_001", "state": "North Carolina", "county_fips": "001", "state_fips": "37", "reconciliation_status": "matched"}]
    census = {"nc_001": {"county_id": "nc_001"}}
    registry = [
        {"county_id": "nc_001", "county_name": "Alpha", "state": "North Carolina", "state_fips": "37", "county_fips": "001", "arcgis_layer_url": "https://example.test/nc1"},
        {"county_id": "nc_002", "county_name": "Beta", "state": "North Carolina", "state_fips": "37", "county_fips": "003", "arcgis_layer_url": "https://example.test/nc2"},
    ]
    calls=[]; seen={"queue": None, "coverage_registry": None, "etl_kwargs": None}
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "_statewide_snapshot", lambda states=None: {"census": census, "reconciled": reconciled, "queue": queue, "coverage": {"before": True}})
    def fake_discover(limit=25, states=None, statewide_queue=None, persist=True):
        seen["queue"] = statewide_queue
        return {"attempted": 2, "found": 2, "persisted": persist, "results":[{"county_id":"nc_001","status":"discovered","registry_patch":{"arcgis_layer_url":"https://example.test/nc1","verification_status":"discovered_not_verified"}},{"county_id":"nc_002","status":"discovered","registry_patch":{"arcgis_layer_url":"https://example.test/nc2","verification_status":"discovered_not_verified"}}]}
    monkeypatch.setattr(worker, "discover_and_register", fake_discover)
    monkeypatch.setattr(worker, "list_counties", lambda: registry)
    def fake_coverage(reconciled_arg, census_arg, registry_arg, states=None):
        seen["coverage_registry"] = list(registry_arg)
        return {"refreshed": True}
    monkeypatch.setattr(worker, "build_statewide_coverage_report", fake_coverage)
    def fake_run_county(cid, **kwargs):
        calls.append((cid, kwargs["mode"]))
        seen["etl_kwargs"] = kwargs
        return {"county_id":cid,"status":"ok"}
    monkeypatch.setattr(worker, "run_county", fake_run_county)
    result = worker.run_statewide_batch(states=["North Carolina"], discovery_limit=10, etl_limit=1, mode="dry_run")
    assert result["states"] == ["north carolina"]
    assert result["statewide_queued"] == 2
    assert seen["queue"] == queue
    assert seen["coverage_registry"] != registry
    assert seen["coverage_registry"][0]["arcgis_layer_url"] == "https://example.test/nc1"
    assert seen["coverage_registry"][0]["verification_status"] == "discovered_not_verified"
    assert registry[0].get("verification_status") is None
    assert result["coverage"] == {"refreshed": True}
    assert result["etl"]["attempted"] == 1
    assert result["etl"]["ok"] == 1
    assert calls == [("nc_001", "dry_run")]
    assert seen["etl_kwargs"]["dry_run"] is True
    assert result["discovery"]["persisted"] is False


def test_discover_and_register_persist_false_never_writes_registry(monkeypatch):
    counties = [{"county_id":"nc","county_name":"NC County","state":"North Carolina","coverage_status":"tier_0"}]
    writes=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "list_counties", lambda: counties)
    monkeypatch.setattr(worker, "_statewide_queue", lambda states=None: [])
    monkeypatch.setattr(worker, "update_county", lambda *args, **kwargs: writes.append((args, kwargs)))
    monkeypatch.setattr(worker, "discover_arcgis_county_config", lambda *args: {"arcgis_root":"https://example.test/root","arcgis_layer_url":"https://example.test/layer","fields":{"apn":"APN"},"source_quality":"strong","source_quality_score":90,"useful_field_count":5,"discovery_score":10})
    result = worker.discover_and_register(limit=1, states=["North Carolina"], persist=False)
    assert result["attempted"] == 1
    assert result["found"] == 1
    assert result["persisted"] is False
    assert writes == []
    assert result["results"][0]["registry_patch"]["arcgis_layer_url"] == "https://example.test/layer"


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
    result=worker.discover_and_register(limit=10, states=["North Carolina"])
    assert result["attempted"] == 1
    assert attempted == ["nc"]


def test_run_statewide_batch_etls_already_valid_counties(monkeypatch):
    queue = [{"county_id": "nc_valid", "state": "North Carolina"}, {"county_id": "nc_new", "state": "North Carolina"}]
    registry = [
        {"county_id": "nc_valid", "state": "North Carolina", "state_fips": "37", "county_fips": "001", "validation_status": "valid", "arcgis_layer_url": "https://example.test/valid"},
        {"county_id": "nc_new", "state": "North Carolina", "state_fips": "37", "county_fips": "003", "validation_status": "pending", "arcgis_layer_url": "https://example.test/new"},
    ]
    calls=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "_statewide_snapshot", lambda states=None: {"census": {}, "reconciled": [], "queue": queue, "coverage": {}})
    monkeypatch.setattr(worker, "discover_and_register", lambda **kwargs: {"results": [{"county_id": "nc_new", "status": "discovered", "registry_patch": {"arcgis_layer_url": "https://example.test/new", "verification_status": "discovered_not_verified"}}], "persisted": False})
    monkeypatch.setattr(worker, "list_counties", lambda: registry)
    monkeypatch.setattr(worker, "build_statewide_coverage_report", lambda *args, **kwargs: {})
    monkeypatch.setattr(worker, "run_county", lambda cid, **kwargs: calls.append(cid) or {"county_id": cid, "status": "ok"})

    result = worker.run_statewide_batch(states=["North Carolina"], etl_limit=5, mode="dry_run")

    assert calls == ["nc_valid", "nc_new"]
    assert result["etl"]["attempted"] == 2
    assert result["etl"]["ok"] == 2
