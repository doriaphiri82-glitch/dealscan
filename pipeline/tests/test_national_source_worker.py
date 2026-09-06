from helpers import authorized_county
from discovery import national_source_worker as worker


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
    # Newly discovered sources are not ETL-authorized until live validation.
    assert result["etl"]["attempted"] == 0
    assert result["etl"]["ok"] == 0
    assert calls == []
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
    registry = [authorized_county(c) if c.get("validation_status") == "valid" else c for c in registry]
    calls=[]
    monkeypatch.setattr(worker, "ensure_national_counties", lambda: None)
    monkeypatch.setattr(worker, "_statewide_snapshot", lambda states=None: {"census": {}, "reconciled": [], "queue": queue, "coverage": {}})
    monkeypatch.setattr(worker, "discover_and_register", lambda **kwargs: {"results": [{"county_id": "nc_new", "status": "discovered", "registry_patch": {"arcgis_layer_url": "https://example.test/new", "verification_status": "discovered_not_verified"}}], "persisted": False})
    monkeypatch.setattr(worker, "list_counties", lambda: registry)
    monkeypatch.setattr(worker, "build_statewide_coverage_report", lambda *args, **kwargs: {})
    monkeypatch.setattr(worker, "run_county", lambda cid, **kwargs: calls.append(cid) or {"county_id": cid, "status": "ok"})

    result = worker.run_statewide_batch(states=["North Carolina"], etl_limit=5, mode="dry_run")

    assert calls == ["nc_valid"]
    assert result["etl"]["attempted"] == 1
    assert result["etl"]["ok"] == 1
