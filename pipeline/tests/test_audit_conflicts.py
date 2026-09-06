from copy import deepcopy
import pytest
import database
from database_supabase import SupabaseDatabase
from persistence import AuditRecordConflict,audit_records
from test_ingestion_integrity import ingest,source_rows


def receipt(value='A'):
    return {'source_url':'https://county.example/0','source_record_id':'same-source-id',
            'raw_payload':{'APN':value},'normalized_payload':{'apn':value},'status':'rejected'}


def test_identical_retries_are_idempotent_without_losing_different_evidence():
    record=receipt()
    assert len(audit_records(1,'fixture',[record,deepcopy(record)]))==1
    with pytest.raises(AuditRecordConflict): audit_records(1,'fixture',[record,receipt('different')])


def test_supabase_conflicts_are_detected_before_any_batch_write(monkeypatch):
    db=SupabaseDatabase('https://database.example','ephemeral-service-key')
    calls=[]
    monkeypatch.setattr(db,'_request',lambda *a,**kw:calls.append(a))
    with pytest.raises(AuditRecordConflict): db.record_ingestion_records(1,'fixture',[receipt(),receipt('PRIVATE_CONFLICT')])
    assert calls==[]


def test_sqlite_conflicts_do_not_overwrite_existing_audit(monkeypatch):
    ingest(monkeypatch)
    db=database.get_backend()
    before=db.get_ingestion_records(1)
    with pytest.raises(AuditRecordConflict): db.record_ingestion_records(1,'fixture',[receipt(),receipt('conflict')])
    assert db.get_ingestion_records(1)==before


def test_conflicting_identity_cannot_finish_as_a_successful_ingestion(monkeypatch):
    rows=source_rows();rows[1]['OBJECTID']=rows[0]['OBJECTID']
    result=ingest(monkeypatch,rows)
    assert result['status']=='degraded'
    assert result['counts']['published']==0
    assert any('AuditRecordConflict' in warning for warning in database.get_backend().audit_failures)
    assert database.get_backend().get_top_deals(min_score=0)==[]
