import json
import pytest
import database
from database_supabase import SupabaseDatabase
from test_database_supabase import FakeResponse
from test_ingestion_integrity import ingest, verification_inputs
from validation import production_smoke as smoke


def backend(monkeypatch):
    ingest(monkeypatch)
    local=database.get_backend()
    _,records,run=verification_inputs(local)
    db=SupabaseDatabase('https://database.example','ephemeral-service-key')
    monkeypatch.setattr(db,'init_db',lambda:None)
    monkeypatch.setattr(db,'get_ingestion_records',lambda _:records)
    monkeypatch.setattr(db,'get_top_deals',lambda **kw:[])
    with local.connection() as conn: properties=[dict(row) for row in conn.execute('SELECT * FROM properties')]
    def request(method,table,**kw):
        if table=='ingestion_runs':
            assert kw['params']['id']=='eq.1'
            return FakeResponse([run])
        if table=='properties': return FakeResponse(properties)
        raise AssertionError(table)
    monkeypatch.setattr(db,'_request',request)
    monkeypatch.setattr(smoke,'get_backend',lambda:db)
    return run,records,properties


def test_smoke_checks_this_run_and_accepts_honest_zero_public_deals(monkeypatch):
    backend(monkeypatch)
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_ephemeral')
    calls=[]
    def request(url,**kwargs):
        calls.append((url,kwargs))
        if 'database.example' in url:
            assert kwargs['headers']=={'apikey':'sb_publishable_ephemeral'}
            return FakeResponse([]) if url.endswith('/deals') else FakeResponse(status_code=403)
        assert not kwargs.get('headers')  # Never forward a service credential to the website.
        if url.endswith('/api/health'): return FakeResponse({'database':'ok','database_origin':'https://database.example'})
        return FakeResponse({'deals':[],'meta':{'storage_source':'supabase'}})
    monkeypatch.setattr(smoke,'_get',request)
    result=smoke.verify_ingestion(1,county_id='fixture',max_records=10,app_url='https://app.example',require_web=True)
    assert result['properties_verified']==4 and result['available_verified']==0
    assert result['web_api']=='verified' and result['scope']=='current_run'
    assert 'PRIVATE' not in json.dumps(result)
    assert len(calls)==5


@pytest.mark.parametrize('failure',['wrong_county','old_workflow','no_persistence','partial','missing_raw','wrong_hash','wrong_mapping','wrong_fingerprint','changed_normalized','wrong_audit_run','previous_attempt'])
def test_smoke_cannot_pass_using_old_partial_or_untraceable_data(monkeypatch,failure):
    run,records,properties=backend(monkeypatch)
    county='fixture'
    if failure=='wrong_county': county='another'
    elif failure=='old_workflow': monkeypatch.setenv('GITHUB_RUN_ID','current-workflow')
    elif failure=='no_persistence': run['records_persisted']=0
    elif failure=='partial': run['status']='partial'
    elif failure=='missing_raw': records[0]['raw_payload']={}
    elif failure=='wrong_hash': properties[0]['source_payload_hash']='wrong'
    elif failure=='wrong_mapping': records[0]['field_mapping']['asking_price']='ACRES'
    elif failure=='wrong_fingerprint': properties[0]['source_fingerprint']='wrong'
    elif failure=='changed_normalized': records[0]['normalized_payload']['lot_size_acres']=2
    elif failure=='wrong_audit_run': records[0]['run_id']=999
    elif failure=='previous_attempt': monkeypatch.setenv('GITHUB_RUN_ATTEMPT','2')
    with pytest.raises(smoke.SmokeFailure): smoke.verify_ingestion(1,county_id=county,max_records=10)


def test_smoke_requires_the_actual_supabase_backend(monkeypatch):
    monkeypatch.setattr(smoke,'get_backend',lambda:object())
    with pytest.raises(smoke.SmokeFailure,match='explicit Supabase'): smoke.verify_ingestion(1)


@pytest.mark.parametrize('key',['','sb_secret_ephemeral','not-a-public-key'])
def test_service_or_unknown_keys_cannot_count_as_an_rls_smoke(monkeypatch,key):
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY',key)
    with pytest.raises(smoke.SmokeFailure,match='public SUPABASE'): smoke.public_key()


@pytest.mark.parametrize('url',['http://app.example','https://secret@app.example','https://app.example/private?token=secret',''])
def test_smoke_rejects_unsafe_or_ambiguous_application_origins(url):
    with pytest.raises(smoke.SmokeFailure): smoke.web_origin(url)


def test_empty_website_on_a_different_project_cannot_pass_smoke(monkeypatch):
    backend(monkeypatch)
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_ephemeral')
    def request(url,**kw):
        if url.endswith('/api/health'): return FakeResponse({'database':'ok','database_origin':'https://different.example'})
        if '/rest/v1/' in url: return FakeResponse([]) if url.endswith('/deals') else FakeResponse(status_code=403)
        return FakeResponse({'deals':[],'meta':{'storage_source':'supabase'}})
    monkeypatch.setattr(smoke,'_get',request)
    with pytest.raises(smoke.SmokeFailure,match='different database'):
        smoke.verify_ingestion(1,county_id='fixture',max_records=10,app_url='https://app.example',require_web=True)
