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
    for prop in properties:
        prop['vacancy_evidence']=json.loads(prop['vacancy_evidence'])
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


@pytest.mark.parametrize('field,value',[
    ('lot_size_acres',2),('assessed_value',100),('market_value',100),
    ('owner_name','ALTERED_PRIVATE_VALUE'),('address','ALTERED_PRIVATE_VALUE'),
    ('latitude',1),('has_improvements',True),('vacancy_status','rejected'),
    ('vacancy_evidence',{}),('source_record_id','wrong'),
])
def test_smoke_replays_actual_persisted_properties_not_only_their_hash(monkeypatch,field,value):
    _,_,properties=backend(monkeypatch)
    properties[0][field]=value
    with pytest.raises(smoke.SmokeFailure) as exc:
        smoke.verify_ingestion(1,county_id='fixture',max_records=10)
    assert 'ALTERED_PRIVATE_VALUE' not in str(exc.value)


@pytest.mark.parametrize('mutation',['duplicate_property','extra_property','duplicate_audit','missing_audit','relabel_audit','wrong_key','inflated_count','boolean_count','future_finish','finish_before_start'])
def test_smoke_rejects_incomplete_accounting_and_duplicate_response_rows(monkeypatch,mutation):
    run,records,properties=backend(monkeypatch)
    if mutation=='duplicate_property': properties[-1]=properties[0].copy()
    elif mutation=='extra_property': properties[-1]['id']=999
    elif mutation=='duplicate_audit': records.append(records[0].copy())
    elif mutation=='missing_audit': records.pop()
    elif mutation=='relabel_audit': records[0]['status']='held'
    elif mutation=='wrong_key': records[0]['record_key']='wrong'
    elif mutation=='inflated_count': run['records_seen']=5
    elif mutation=='boolean_count': run['records_seen']=True
    elif mutation=='future_finish': run['finished_at']='2999-01-01T00:00:00Z'
    elif mutation=='finish_before_start': run['finished_at']='2000-01-01T00:00:00Z'
    with pytest.raises(smoke.SmokeFailure): smoke.verify_ingestion(1,county_id='fixture',max_records=10)


def public_snapshot():
    from datetime import datetime,timedelta,timezone
    return {'apn':'fixture','county_id':'fixture','status':'discovered','verification_status':'verified',
        'verified_at':datetime.now(timezone.utc).isoformat(),
        'verification_expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        'asking_price':20000,'estimated_costs':5000,'estimated_profit_low':55000,
        'estimated_profit_high':75000,'source_url':'https://county.example/0','source_record_id':'1'}


@pytest.mark.parametrize('change',[{'asking_price':1},{'estimated_costs':0},{'estimated_profit_high':999999},
    {'lot_size_acres':0},{'source_record_id':'another'},{'verification_expires_at':'2000-01-01T00:00:00Z'}])
def test_same_parcel_ids_do_not_prove_public_financial_or_provenance_agreement(change):
    original=public_snapshot()
    with pytest.raises(smoke.SmokeFailure): smoke.verify_api_snapshot([original],[{**original,**change}])


def test_public_snapshot_rejects_duplicates_and_accepts_equivalent_numeric_storage():
    original=public_snapshot()
    smoke.verify_api_snapshot([{**original,'asking_price':'20000.00'}],[original])
    with pytest.raises(smoke.SmokeFailure): smoke.verify_api_snapshot([original],[original,original])


def test_origin_comparison_normalizes_case_and_default_port_without_accepting_credentials():
    assert smoke.web_origin('https://DATABASE.example:443/')=='https://database.example'
    with pytest.raises(smoke.SmokeFailure): smoke.web_origin('https://database.example:bad')


def test_unfiltered_public_read_must_deny_expired_reviews(monkeypatch):
    backend(monkeypatch)
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_ephemeral')
    monkeypatch.setattr(smoke,'_get',lambda *a,**kw:FakeResponse([{**public_snapshot(),'verification_expires_at':'2000-01-01T00:00:00Z'}]))
    with pytest.raises(smoke.SmokeFailure,match='RLS exposed'):
        smoke.verify_public_api(smoke.get_backend(),'https://app.example')
