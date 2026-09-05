from datetime import datetime, timedelta, timezone
import time
import requests
import pytest
from database_supabase import SupabaseDatabase
from persistence import AuditRunNotFound
from test_database_supabase import FakeResponse


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr('database_supabase.time.sleep',lambda _:None)
    return SupabaseDatabase('https://database.example','ephemeral-service-key')


def test_transport_is_pooled_bounded_and_does_not_follow_credential_redirects(db,monkeypatch):
    calls=[]
    def request(*args,**kwargs):
        calls.append(kwargs)
        return FakeResponse(status_code=503 if len(calls)<3 else 200)
    monkeypatch.setattr(db.session,'request',request)
    assert db.get_top_deals()==[]
    assert len(calls)==3 and all(call['allow_redirects'] is False for call in calls)
    assert all(call['timeout']==(5,30.0) for call in calls)
    assert 'owner_name' not in calls[-1]['params']['select']
    assert 'financial_evidence' not in calls[-1]['params']['select']
    assert 'ingestion_record_id' not in calls[-1]['params']['select']
    assert calls[-1]['params']['verification_expires_at'].startswith('gt.')


def test_transport_errors_never_log_credentials_or_response_payloads(db,monkeypatch,caplog):
    def request(*a,**kw): raise requests.Timeout('ephemeral-service-key PRIVATE_OWNER')
    monkeypatch.setattr(db.session,'request',request)
    with pytest.raises(RuntimeError,match='transport failed') as exc: db.get_top_deals()
    assert 'ephemeral-service-key' not in str(exc.value)+caplog.text
    assert 'PRIVATE_OWNER' not in str(exc.value)+caplog.text


def test_resume_checks_county_source_status_and_heartbeat(db,monkeypatch):
    monkeypatch.setenv('DEALSCAN_ACTIVE_AUDIT_RUN_ID','91'); calls=[]
    def request(method,url,**kw):
        calls.append((method,kw))
        assert method=='GET'
        assert kw['params']['county_id']=='eq.fixture' and kw['params']['status']=='eq.running'
        return FakeResponse([{'id':91,'county_id':'fixture','source_url':'https://county.example',
                              'heartbeat_at':datetime.now(timezone.utc).isoformat(),'metadata':{'test':True}}])
    monkeypatch.setattr(db.session,'request',request)
    assert db.ensure_active_ingestion_run('fixture','https://county.example')==91
    assert db.active_run_id('other') is None
    assert db.ensure_active_ingestion_run('fixture','https://county.example')==91
    assert len(calls)==1


@pytest.mark.parametrize('invalid', ['missing','other_source','stale','future'])
def test_invalid_active_audit_context_is_not_reused(db,monkeypatch,invalid):
    monkeypatch.setenv('DEALSCAN_ACTIVE_AUDIT_RUN_ID','91'); calls=[]
    def request(method,url,**kw):
        calls.append((method,kw))
        if method=='GET':
            if invalid=='missing': return FakeResponse([])
            when=datetime.now(timezone.utc)+({'stale':timedelta(hours=-3),'future':timedelta(hours=1)}.get(invalid,timedelta()))
            return FakeResponse([{'id':91,'county_id':'fixture','source_url':'https://other.example' if invalid=='other_source' else 'https://county.example', 'heartbeat_at':when.isoformat()}])
        if method=='PATCH':
            assert kw['params']['county_id']=='eq.fixture' and kw['params']['heartbeat_at'].startswith('lt.')
            assert kw['json']['status']=='failed'
            return FakeResponse([])
        if method=='POST':
            assert kw['json']['status']=='running' and kw['params']['on_conflict']=='run_key'
            return FakeResponse([{'id':92}])
        raise AssertionError(method)
    monkeypatch.setattr(db.session,'request',request)
    assert db.ensure_active_ingestion_run('fixture','https://county.example')==92
    assert sum(method=='POST' for method,_ in calls)==1


def test_cached_run_context_is_periodically_rechecked(db,monkeypatch):
    db._active={'id':1,'county_id':'fixture','source_url':'https://county.example'}
    db._active_checked_at=time.monotonic()-60
    monkeypatch.setattr(db,'recover_stale_runs',lambda _:None)
    monkeypatch.setattr(db,'record_ingestion_run',lambda *a,**kw:2)
    monkeypatch.setattr(db.session,'request',lambda method,*a,**kw:FakeResponse([]))
    assert db.ensure_active_ingestion_run('fixture','https://county.example')==2


def test_a_timeout_during_resume_does_not_masquerade_as_a_missing_run(db,monkeypatch):
    monkeypatch.setenv('DEALSCAN_ACTIVE_AUDIT_RUN_ID','91')
    monkeypatch.setattr(db.session,'request',lambda *a,**kw: (_ for _ in ()).throw(requests.Timeout()))
    monkeypatch.setattr(db,'record_ingestion_run',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('Must not create another run')))
    with pytest.raises(RuntimeError,match='transport failed'):
        db.ensure_active_ingestion_run('fixture','https://county.example')


def test_audit_write_failure_does_not_rollback_primary_property_or_deal(db,monkeypatch):
    def request(method,url,**kw):
        if url.endswith('/properties'): return FakeResponse([{'id':7}])
        if url.endswith('/deals'): return FakeResponse([{'id':8}])
        if url.endswith('/counties'): return FakeResponse([{'county_id':'fixture'}])
        return FakeResponse(status_code=503)
    monkeypatch.setattr(db.session,'request',request)
    assert db.save_property({'county_id':'fixture','apn':'PRIMARY'})==7
    assert db.save_deal({'property_id':7,'ingestion_record_id':99})==8
    assert len(db.audit_failures)==2


def test_record_batches_are_deduplicated_and_bounded(db,monkeypatch):
    batches=[]
    def request(method,url,**kw):
        assert method=='POST' and kw['params']['on_conflict']=='run_id,record_key'
        batches.append(kw['json']); return FakeResponse([])
    monkeypatch.setattr(db.session,'request',request)
    records=[{'source_record_id':str(i),'raw_payload':{'OID':i},'status':'held'} for i in range(501)]
    assert db.record_ingestion_records(1,'fixture',records+records[:1])==501
    assert [len(batch) for batch in batches]==[250,250,1]


def test_terminal_update_is_scoped_and_a_different_failure_is_not_a_missing_row(db,monkeypatch):
    def request(method,url,**kw):
        if method=='PATCH':
            assert kw['params']=={'id':'eq.1','county_id':'eq.fixture','status':'eq.running'}
            return FakeResponse([])
        return FakeResponse([{'id':1,'status':'failed'}])
    monkeypatch.setattr(db.session,'request',request)
    with pytest.raises(RuntimeError) as exc: db.update_ingestion_run(1,'fixture','ok',{})
    assert not isinstance(exc.value,AuditRunNotFound)


def test_run_upsert_retries_preserve_one_operation_key(db,monkeypatch):
    payloads=[]
    def request(method,url,**kw):
        if method=='GET': return FakeResponse([{'id':42}])
        payloads.append(kw['json'])
        return FakeResponse(status_code=503) if len(payloads)==1 else FakeResponse([])
    monkeypatch.setattr(db.session,'request',request)
    assert db.record_ingestion_run('fixture','running',{})==42
    assert len({payload['run_key'] for payload in payloads})==1


@pytest.mark.parametrize('url',['http://database.example','https://user:secret@database.example','https://database.example/path','https://database.example?key=secret'])
def test_backend_rejects_unsafe_credential_destinations(url):
    with pytest.raises(RuntimeError,match='HTTPS origin'): SupabaseDatabase(url,'ephemeral-key')
