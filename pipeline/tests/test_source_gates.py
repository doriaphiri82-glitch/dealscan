import pytest
from datetime import datetime, timedelta, timezone
from helpers import authorized_county
from config.source_config import county_config
from validation.gates import authorization_error, source_fingerprint
from discovery import national_source_worker as worker
import runners


def test_authorization_requires_all_steps_and_same_source():
    county = authorized_county({'county_id': 'fixture'})
    cfg = county_config('fixture', county)
    assert authorization_error(county, cfg) == ''
    for changes in ({'validation_status': 'pending'}, {'ingestion_authorized': False},
                    {'validation_pagination_checked': False}, {'validated_source_fingerprint': 'old'},
                    {'authorized_source_fingerprint': None}, {'last_validated_at': (datetime.now(timezone.utc)-timedelta(days=8)).isoformat()}):
        assert authorization_error({**county, **changes}, cfg)
    assert authorization_error(county, {**cfg, 'source_object_id_field': 'OTHER_ID'})
    assert authorization_error(county, {**cfg, 'where': 'different = 1'})
    assert authorization_error(county, {**cfg, 'fields': {'apn': 'OTHER'}})
    assert authorization_error(county, {**cfg, 'arcgis_layer_url': 'https://other.example/FeatureServer/0'})


def test_technical_validation_does_not_prove_government_ownership():
    county = authorized_county({'county_id': 'fixture'})
    cfg = county_config('fixture', county); cfg['authority_reviewed'] = False
    fingerprint = source_fingerprint(cfg)
    county.update(validated_source_fingerprint=fingerprint, authorized_source_fingerprint=fingerprint)
    assert authorization_error(county, cfg) == 'source_authority_not_reviewed'


def test_direct_county_runner_cannot_bypass_authorization(monkeypatch):
    monkeypatch.setattr(runners, '_county_config', lambda _: {'arcgis_layer_url': 'https://county.example/FeatureServer/0'})
    monkeypatch.setattr(runners, 'get_county', lambda _: {'validation_status': 'valid'})
    monkeypatch.setattr(runners, 'fetch_parcels', lambda *a, **k: (_ for _ in ()).throw(AssertionError('Must not query')))
    result = runners.run('fixture')
    assert result['status'] == 'skipped' and result['error'] == 'source_changed_since_validation'


def test_new_discovery_resets_inherited_validation_and_authorization(monkeypatch):
    county = authorized_county({'county_id': 'fixture', 'county_name': 'Fixture', 'state': 'Arizona'})
    county.update(arcgis_layer_url=None, parcel_source_url=None)
    patches = []
    monkeypatch.setattr(worker, 'ensure_national_counties', lambda: None)
    monkeypatch.setattr(worker, 'list_counties', lambda: [county])
    monkeypatch.setattr(worker, 'update_county', lambda cid, **fields: patches.append(fields))
    monkeypatch.setattr(worker, 'discover_arcgis_county_config', lambda *a: {'arcgis_layer_url': 'https://new.example/FeatureServer/0', 'fields': {'apn': 'APN'}})
    worker.discover_and_register(limit=1, statewide_queue=[])
    patch = patches[-1]
    assert patch['validation_status'] == 'pending' and patch['ingestion_authorized'] is False
    assert patch['validated_source_fingerprint'] is None and patch['last_validated_at'] is None


def test_national_worker_does_not_ingest_valid_but_unauthorized_sources(monkeypatch):
    monkeypatch.setattr(worker, 'ensure_national_counties', lambda: None)
    monkeypatch.setattr(worker, 'list_counties', lambda: [{'county_id': 'fixture', 'validation_status': 'valid', 'arcgis_layer_url': 'https://county.example/FeatureServer/0'}])
    monkeypatch.setattr(worker, 'run_county', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Must not ingest')))
    assert worker.run_national_batch(limit=1)['attempted'] == 0


@pytest.mark.parametrize('field',['validation_source_fields_checked','validation_pagination_checked'])
@pytest.mark.parametrize('value',['false','true',1,[],{},None])
def test_truthy_values_are_not_boolean_validation_evidence(field,value):
    county=authorized_county({'county_id':'fixture'})
    cfg=county_config('fixture',county)
    assert authorization_error({**county,field:value},cfg)=='source_validation_incomplete'


@pytest.mark.parametrize('value',[True,False,'5',-1,0,6,2.5,None,float('inf')])
def test_sample_count_must_be_a_real_bounded_integer(value):
    county=authorized_county({'county_id':'fixture'})
    cfg=county_config('fixture',county)
    assert authorization_error({**county,'validation_sample_checked':value},cfg)=='source_validation_incomplete'


@pytest.mark.parametrize('url',['https://user:password@county.example/gis','https://county.example:bad/gis','https://county.example/\nGIS','http://county.example/gis'])
def test_review_evidence_cannot_hide_credentials_or_invalid_origins(url):
    from validation.gates import authority_verified
    county=authorized_county({'county_id':'fixture'})
    cfg=county_config('fixture',county)
    assert not authority_verified({**cfg,'authority_evidence_url':url})


@pytest.mark.parametrize('geoid',['',12345,'1234','abcde','123456'])
def test_county_identity_needs_a_five_digit_geoid(geoid):
    from validation.gates import authority_verified
    county=authorized_county({'county_id':'fixture'})
    cfg=county_config('fixture',county)
    assert not authority_verified({**cfg,'geoid':geoid,'source_county_geoid':geoid})


@pytest.mark.parametrize('patch',[{'source_fields_checked':'false'},{'pagination_checked':'false'},{'sample_checked':True},{'sample_checked':'5'},{'status':'unknown'}])
def test_registry_does_not_coerce_invalid_proof_into_permission(monkeypatch,patch):
    from config.counties import registry
    monkeypatch.setattr(registry,'update_county',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('No write allowed')))
    with pytest.raises(ValueError): registry.mark_county_validation('fixture',**{'status':'valid',**patch})
