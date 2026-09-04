import json


def test_bulk_registry_upsert_is_single_write(monkeypatch, tmp_path):
    from config.counties import registry

    path=tmp_path/"registry.json"
    path.write_text(json.dumps({"counties":{},"meta":{}}),encoding="utf-8")
    monkeypatch.setattr(registry,"REGISTRY_PATH",str(path))
    writes=[]
    original=registry._save_registry
    monkeypatch.setattr(registry,"_save_registry",lambda reg:(writes.append(len(reg["counties"])),original(reg)))

    result=registry.register_counties_bulk([
        {"county_id":"alpha_01_001","county_name":"Alpha County","state":"Alabama","state_fips":"01","county_fips":"001","geoid":"01001","coverage_status":"not_covered"},
        {"county_id":"beta_01_003","county_name":"Beta County","state":"Alabama","state_fips":"01","county_fips":"003","geoid":"01003","coverage_status":"not_covered"},
    ])

    assert len(result)==2
    assert writes==[2]
    saved=json.loads(path.read_text(encoding="utf-8"))
    assert saved["meta"]["total"]==2
    assert saved["meta"]["by_state"]=={"Alabama":2}


def test_national_sync_preserves_existing_when_census_unavailable(monkeypatch, tmp_path):
    from config.counties import national_registry as nr
    from config.counties import registry

    path=tmp_path/"registry.json"
    existing={"counties":{"custom_99_001":{
        "county_id":"custom_99_001","county_name":"Custom County","state":"Test State","state_fips":"99","county_fips":"001","geoid":"99001","population":12345,
        "data_source_type":"arcgis","verification_status":"source_verified","coverage_status":"tier_3","arcgis_layer_url":"https://example.test/FeatureServer/0"
    }},"meta":{}}
    path.write_text(json.dumps(existing),encoding="utf-8")
    monkeypatch.setattr(registry,"REGISTRY_PATH",str(path))
    monkeypatch.setattr(nr,"discover_national_counties",lambda: {})

    nr.ensure_national_counties()
    saved=json.loads(path.read_text(encoding="utf-8"))
    county=saved["counties"]["custom_99_001"]
    assert county["population"]==12345
    assert county["verification_status"]=="source_verified"
    assert county["coverage_status"]=="tier_3"
    assert county["arcgis_layer_url"]=="https://example.test/FeatureServer/0"
