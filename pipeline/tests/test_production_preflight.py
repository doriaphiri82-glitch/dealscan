import json
from types import SimpleNamespace
import pytest
import main
from validation import production_preflight as preflight
from validation import production_smoke as smoke
from database_supabase import SupabaseDatabase
from test_database_supabase import FakeResponse


def configure(monkeypatch):
    monkeypatch.setenv('DEALSCAN_ENV','production')
    monkeypatch.setenv('DEALSCAN_DB_BACKEND','supabase')
    monkeypatch.setenv('SUPABASE_URL','https://database.example')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY','ephemeral-service-key')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_ephemeral')
    monkeypatch.setenv('WAITLIST_CONTACT_EMAIL',preflight.EXPECTED_CONTACT)


def test_preflight_reports_missing_secrets_without_sqlite_or_writes(monkeypatch):
    for name in ('SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_PUBLISHABLE_KEY','SUPABASE_ANON_KEY'):
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setattr(preflight,'deployment_probe',lambda *a:{'status':'failed','http_status':500})
    monkeypatch.setattr(preflight,'probe_source',lambda *a:{'status':'passed','ingestion_authorized':False})
    report=preflight.run_preflight('el_paso_tx','https://app.example')
    assert report['status']=='blocked'
    assert report['checks']['database']['status']=='not_checked'
    assert report['production_writes_performed'] is False
    assert report['ingestion_status']=='not_attempted'
    assert 'SUPABASE_SERVICE_ROLE_KEY' in report['checks']['configuration']['missing']


def test_database_counts_are_head_only_and_contain_no_records():
    calls=[]
    class DB:
        headers={'apikey':'ephemeral'}
        def _request(self,method,table,**kw):
            calls.append((method,table,kw))
            return SimpleNamespace(headers={'Content-Range':'*/0'})
    assert preflight.database_counts(DB())==dict.fromkeys(('counties','properties','deals','ingestion_runs','ingestion_records'),0)
    assert all(method=='HEAD' and kw['params']['limit']=='0' for method,_,kw in calls)


def test_unknown_count_is_not_a_fabricated_zero():
    class DB:
        headers={}
        def _request(self,*a,**kw): return SimpleNamespace(headers={'Content-Range':'*/*'})
    with pytest.raises(smoke.SmokeFailure,match='exact count'): preflight.database_counts(DB())


def test_failed_public_boundary_preserves_successful_database_evidence(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(SupabaseDatabase,'init_db',lambda _:None)
    monkeypatch.setattr(preflight,'database_counts',lambda db:{'properties':0})
    monkeypatch.setattr(preflight,'deployment_probe',lambda *a:{'status':'passed'})
    monkeypatch.setattr(preflight,'probe_source',lambda *a:{'status':'passed'})
    monkeypatch.setattr(preflight,'verify_public_api',lambda *a,**k:(_ for _ in ()).throw(smoke.SmokeFailure('Deployed API failed')))
    report=preflight.run_preflight('el_paso_tx','https://app.example')
    assert report['status']=='blocked'
    assert report['checks']['database']=={'status':'passed','schema_columns_checked':True,'counts':{'properties':0}}
    assert report['checks']['public_boundary']['status']=='failed'
    assert 'ephemeral-service-key' not in json.dumps(report)


def test_readiness_success_does_not_claim_ingestion_or_migration(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(SupabaseDatabase,'init_db',lambda _:None)
    monkeypatch.setattr(preflight,'database_counts',lambda db:{'properties':0})
    monkeypatch.setattr(preflight,'deployment_probe',lambda *a:{'status':'passed'})
    monkeypatch.setattr(preflight,'probe_source',lambda *a:{'status':'passed','ingestion_authorized':False})
    monkeypatch.setattr(preflight,'verify_public_api',lambda *a,**k:{'status':'verified'})
    monkeypatch.setenv('HAS_VERCEL_TOKEN','true')
    report=preflight.run_preflight('el_paso_tx','https://app.example')
    assert report['status']=='ready_for_bounded_smoke'
    assert report['ingestion_status']=='not_attempted' and not report['production_writes_performed']
    assert report['checks']['platform_access']['VERCEL_TOKEN'] is True


def test_production_command_checks_deployment_before_registry_or_ingestion_writes(monkeypatch):
    configure(monkeypatch)
    db=SupabaseDatabase()
    monkeypatch.setattr(main,'get_backend',lambda:db)
    monkeypatch.setattr(main,'init_db',lambda:None)
    monkeypatch.setattr(smoke,'verify_public_api',lambda *a,**k:(_ for _ in ()).throw(smoke.SmokeFailure('Deployed API failed')))
    calls=[]
    for name in ('pull_registry','push_registry','ensure_pilot_counties','run_county'):
        monkeypatch.setattr(main,name,lambda *a,_name=name,**kw:calls.append(_name))
    assert main.main(['--production-smoke','el_paso_tx','--app-url','https://app.example','--max-records','250'])==1
    assert calls==[]


def test_read_only_source_probe_does_not_authorize_or_export_samples(monkeypatch):
    from scrapers import arcgis
    from config import source_config
    from config.counties import registry
    from helpers import layer_metadata
    cfg={'county_id':'el_paso_tx','arcgis_layer_url':'https://county.example/FeatureServer/0','fields':{'apn':'APN','lot_size_acres':'ACRES','improvement_value':'IMP'},'acreage_units':'acres'}
    monkeypatch.setattr(source_config,'county_config',lambda *a:cfg.copy())
    monkeypatch.setattr(arcgis,'layer_metadata',lambda *a,**kw:layer_metadata(('APN','ACRES','IMP')))
    monkeypatch.setattr(arcgis,'query_count',lambda *a:10)
    def query(*a,**kw):
        kw['diagnostics']['pages']=3
        return [{'OBJECTID':i+1,'APN':str(i),'ACRES':1,'IMP':0,'OWNER':'PRIVATE'} for i in range(5)]
    monkeypatch.setattr(arcgis,'query_layer',query)
    monkeypatch.setattr(registry,'_save_registry',lambda *a:(_ for _ in ()).throw(AssertionError('No writes allowed')))
    result=preflight.probe_source('el_paso_tx')
    assert result['status']=='passed' and result['sample_checked']==5
    assert result['ingestion_authorized'] is False
    assert 'PRIVATE' not in json.dumps(result) and 'raw_payload' not in result
