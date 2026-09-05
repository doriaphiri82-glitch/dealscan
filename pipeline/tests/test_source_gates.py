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
