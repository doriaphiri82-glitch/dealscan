import discovery.national_source_worker as worker


def test_statewide_batch_never_etls_newly_discovered_unvalidated_source(monkeypatch):
    county = {
        "county_id": "test_aa",
        "county_name": "Test County",
        "state": "Arizona",
        "state_fips": "04",
        "county_fips": "001",
        "validation_status": None,
    }
    queue_row = {"county_id": "test_aa", "state": "Arizona", "source_url": "https://example.test/layer"}
    snapshot = {"census": {"test_aa": county}, "reconciled": [], "queue": [queue_row], "coverage": {}}

    monkeypatch.setattr(worker, "ensure_national_counties", lambda: snapshot["census"])
    monkeypatch.setattr(worker, "_statewide_snapshot", lambda states=None: snapshot)
    monkeypatch.setattr(worker, "discover_and_register", lambda **kwargs: {
        "attempted": 1,
        "found": 1,
        "results": [{
            "county_id": "test_aa",
            "status": "discovered",
            "registry_patch": {"validation_status": "valid"},
        }],
    })
    monkeypatch.setattr(worker, "list_counties", lambda: [county])
    monkeypatch.setattr(worker, "build_statewide_coverage_report", lambda *args, **kwargs: {})
    etl_calls = []
    monkeypatch.setattr(worker, "run_county", lambda *args, **kwargs: etl_calls.append(args[0]))

    result = worker.run_statewide_batch(discovery_limit=1, etl_limit=1, mode="publish")

    assert result["discovery"]["found"] == 1
    assert result["etl"]["attempted"] == 0
    assert etl_calls == []
