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


def test_national_sync_preserves_existing_source_metadata_on_census_refresh(monkeypatch, tmp_path):
    from config.counties import national_registry as nr
    from config.counties import registry

    path=tmp_path/"registry.json"
    existing={"counties":{"alpha_01_001":{
        "county_id":"alpha_01_001","county_name":"Alpha County","state":"Alabama","state_fips":"01","county_fips":"001","geoid":"01001",
        "population":111,"data_source_type":"arcgis","verification_status":"verified","coverage_status":"tier_5",
        "arcgis_layer_url":"https://example.test/FeatureServer/0","parcel_source_url":"https://example.test/parcels",
        "last_successful_run":"2026-09-04T10:00:00+00:00","last_record_count":42,"validation_status":"valid",
        "source_quality":"complete","field_mapping":{"apn":"APN"}
    }},"meta":{}}
    path.write_text(json.dumps(existing),encoding="utf-8")
    monkeypatch.setattr(registry,"REGISTRY_PATH",str(path))
    monkeypatch.setattr(nr,"discover_national_counties",lambda:{
        "alpha_01_001":{"county_name":"Alpha County","state":"Alabama","state_fips":"01","county_fips":"001","geoid":"01001","population":999,"coverage_status":"not_covered","verification_status":"not_started"},
        "beta_01_003":{"county_name":"Beta County","state":"Alabama","state_fips":"01","county_fips":"003","geoid":"01003","population":222,"coverage_status":"not_covered","verification_status":"not_started"},
    })

    nr.ensure_national_counties()
    saved=json.loads(path.read_text(encoding="utf-8"))
    alpha=saved["counties"]["alpha_01_001"]
    beta=saved["counties"]["beta_01_003"]
    assert alpha["population"]==111
    assert alpha["verification_status"]=="verified"
    assert alpha["coverage_status"]=="tier_5"
    assert alpha["arcgis_layer_url"]=="https://example.test/FeatureServer/0"
    assert alpha["parcel_source_url"]=="https://example.test/parcels"
    assert alpha["last_successful_run"]=="2026-09-04T10:00:00+00:00"
    assert alpha["last_record_count"]==42
    assert alpha["validation_status"]=="valid"
    assert alpha["source_quality"]=="complete"
    assert alpha["field_mapping"]=={"apn":"APN"}
    assert beta["population"]==222
    assert beta["verification_status"]=="not_started"
    assert beta["coverage_status"]=="not_covered"


def test_census_refresh_preserves_pilot_runtime_state_and_authorization(monkeypatch):
    from config.counties import national_registry as nr, registry
    from helpers import authorized_county
    county = authorized_county({**nr.PILOT_COUNTIES['cochise_az'], 'county_id': 'cochise_az'})
    county.update(last_successful_run='2026-09-01T00:00:00+00:00', verification_status='verified', coverage_status='tier_4', discovery_attempted_at='2026-09-01T00:00:00+00:00')
    registry.register_counties_bulk([county])
    monkeypatch.setattr(nr, 'discover_national_counties', lambda: {})
    result = nr.ensure_national_counties()['cochise_az']
    assert result['ingestion_authorized'] is True and result['last_successful_run'] == county['last_successful_run']
    assert result['coverage_status'] == 'tier_4' and result['discovery_attempted_at'] == county['discovery_attempted_at']


def test_pilot_and_census_use_one_county_identity(monkeypatch):
    from config.counties import national_registry as nr, registry
    registry.register_counties_bulk([{**nr.PILOT_COUNTIES['cochise_az'], 'county_id': 'cochise_az'}])
    monkeypatch.setattr(nr, 'discover_national_counties', lambda: {'cochise_county_04_003': {**nr.PILOT_COUNTIES['cochise_az'], 'county_id': 'cochise_county_04_003'}})
    result = nr.ensure_national_counties()
    assert [row['county_id'] for row in result.values() if row['geoid'] == '04003'] == ['cochise_az']


def test_gazetteer_parser_preserves_geography_without_inventing_source_coverage():
    from config.counties.national_registry import parse_gazetteer
    rows = parse_gazetteer('USPS|GEOID|NAME\nAZ|04003|Cochise County\n')
    row = next(iter(rows.values()))
    assert row['geoid'] == '04003' and row['county_fips'] == '003'
    assert row['coverage_status'] == 'tier_0' and row['verification_status'] == 'not_started'
    assert 'arcgis_layer_url' not in row


def test_source_changes_and_explicit_nulls_invalidate_authorization():
    from config.counties import registry
    from helpers import authorized_county
    row = authorized_county({'county_id': 'fixture', 'county_name': 'Fixture', 'state': 'Arizona', 'state_fips': '99', 'county_fips': '001'})
    registry.register_counties_bulk([row])
    result = registry.update_county('fixture', arcgis_layer_url='https://new.example/0', last_validated_at=None)
    assert result['ingestion_authorized'] is False and result['validation_status'] == 'pending'
    assert result['last_validated_at'] is None and result['validated_source_fingerprint'] is None
