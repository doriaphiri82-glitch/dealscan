"""Full offline ingestion and verification against an ephemeral SQLite store."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import pytest
import database
import runners
import runregistry
from config.counties.registry import _save_registry
from config.source_config import county_config
from helpers import authorized_county
from persistence import AuditRunNotFound, audit_record, record_key
from scrapers.adapter import BaseScraperAdapter
from validation.publication import verify_persisted_deal

FIELDS = {'apn':'APN','lot_size_acres':'ACRES','land_use':'USE','improvement_value':'IMPROVEMENT',
          'latitude':'LAT','longitude':'LON','asking_price':'PRICE','estimated_costs':'COSTS',
          'costs_complete':'COSTS_COMPLETE','costs_source_url':'COSTS_URL','last_sale_price':'SALE',
          'last_sale_date':'SOLD','sale_qualified':'QUALIFIED','vacant_at_sale':'VACANT_AT_SALE','owner_name':'OWNER'}


def source_rows():
    common = {'ACRES':1,'USE':'Vacant land','IMPROVEMENT':0,'LAT':35,'LON':-114,'OWNER':'PRIVATE_EPHEMERAL_FIXTURE'}
    target = {**common,'APN':'TARGET','OBJECTID':1,'PRICE':20000,'COSTS':5000,
              'COSTS_COMPLETE':True,'COSTS_URL':'https://county.example/cost-estimate'}
    date = (datetime.now(timezone.utc)-timedelta(days=90)).isoformat()
    return [target, *[{**common,'APN':f'COMP-{i}','OBJECTID':i+1,'SALE':80000+10000*i,
                       'SOLD':date,'QUALIFIED':True,'VACANT_AT_SALE':True,'LAT':35+i*.001} for i in range(1,4)]]


class FixtureAdapter(BaseScraperAdapter):
    def __init__(self, rows): self.rows = rows
    def discover(self, cfg): return self.rows[:cfg['max_records']]
    def parse(self, raw): return [raw]
    def validate(self, record): return bool(record.get('apn'))


def prepare(monkeypatch, rows=None):
    county = authorized_county({'county_id':'fixture','county_name':'Ephemeral fixture','field_mapping':FIELDS,
                                'source_object_id_field':'OBJECTID'})
    _save_registry({'counties': {'fixture': county}, 'meta': {}})
    cfg = county_config('fixture',county)
    adapter = FixtureAdapter(source_rows() if rows is None else rows)
    monkeypatch.setattr(runners,'_adapter_for',lambda _: adapter)
    return county,cfg


def ingest(monkeypatch, rows=None, **options):
    prepare(monkeypatch,rows)
    return runners.run('fixture', mode='etl-only', max_records=10, **options)


def verification_inputs(db):
    with db.connection() as conn:
        deal_id = conn.execute('SELECT id FROM deals ORDER BY id').fetchone()['id']
        run = dict(conn.execute('SELECT * FROM ingestion_runs ORDER BY id DESC').fetchone())
    run['metadata'] = json.loads(run['metadata'])
    return db.get_deal_for_verification(deal_id),db.get_ingestion_records(run['id']),run


def test_complete_ingestion_keeps_holds_and_requires_separate_evidence_verification(monkeypatch):
    result = ingest(monkeypatch)
    assert result['status'] == 'ok', result
    assert {key:result['counts'][key] for key in ('discovered','normalized','stored','rejected','held','qualified','published')} == {
        'discovered':4,'normalized':4,'stored':4,'rejected':0,'held':3,'qualified':1,'published':0}
    db = database.get_backend()
    deal,records,run = verification_inputs(db)
    assert run['status'] == 'completed' and run['finished_at']
    assert run['records_persisted'] == 4 and run['records_held'] == 3
    assert {row['status'] for row in records} == {'held','candidate'}
    assert records[0]['raw_payload'] == source_rows()[0]
    assert records[0]['field_mapping'] == FIELDS
    assert all(not key.startswith('_') for key in records[0]['normalized_payload'])
    assert db.get_top_deals(min_score=0) == []
    result = db.verify_deal(deal['id'])
    assert result['verification_status'] == 'verified' and result['comparable_count'] == 3
    rows = db.get_top_deals(min_score=0)
    assert len(rows) == 1 and len(rows[0]['comps']) == 3
    assert rows[0]['asking_price'] == 20000 and rows[0]['estimated_arv_high'] == 100000
    assert 'owner_name' not in rows[0] and 'financial_evidence' not in rows[0]
    assert all('ingestion_record_id' not in comp for comp in rows[0]['comps'])


def test_repeated_ingestion_is_idempotent_but_has_distinct_audited_runs(monkeypatch):
    prepare(monkeypatch)
    first = runners.run('fixture',mode='etl-only',max_records=10)
    second = runners.run('fixture',mode='etl-only',max_records=10)
    assert first['status'] == second['status'] == 'ok'
    assert first['audit_run_id'] != second['audit_run_id']
    with database.get_backend().connection() as conn:
        assert conn.execute('SELECT count(*) FROM properties').fetchone()[0] == 4
        assert conn.execute('SELECT count(*) FROM deals').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM comps').fetchone()[0] == 3
        assert conn.execute('SELECT count(*) FROM ingestion_records').fetchone()[0] == 8
        assert conn.execute("SELECT count(*) FROM ingestion_runs WHERE status='completed'").fetchone()[0] == 2


def test_missing_financial_and_vacancy_inputs_never_become_fake_deals(monkeypatch):
    rows = source_rows()
    rows[0].pop('PRICE')
    rows.append({'OBJECTID':5,'APN':'UNKNOWN','ACRES':1})
    rows.append({'OBJECTID':6,'APN':'IMPROVED','ACRES':1,'USE':'Vacant land','IMPROVEMENT':100000})
    rows.append({'OBJECTID':7,'ACRES':1})
    result = ingest(monkeypatch,rows)
    assert result['status'] == 'ok'
    assert result['counts']['rejected'] == 3 and result['counts']['stored'] == 4
    assert result['counts']['held'] == 4 and result['counts']['qualified'] == 0
    db = database.get_backend()
    audit = db.get_ingestion_records(result['audit_run_id'])
    assert len(audit) == 7 and sum(row['status']=='rejected' for row in audit) == 3
    assert next(row for row in audit if row['source_record_id']=='7')['raw_payload']['OBJECTID'] == 7
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM deals').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM properties WHERE market_value IS NULL').fetchone()[0] == 4


def test_audit_failure_retains_primary_data_and_reports_degraded(monkeypatch):
    prepare(monkeypatch)
    db = database.get_backend()
    monkeypatch.setattr(db,'record_ingestion_records',lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('audit offline')))
    result = runners.run('fixture',mode='etl-only',max_records=10)
    assert result['status'] == 'degraded' and result['counts']['stored'] == 4
    assert 'audit_unavailable' in result['error'] and db.audit_failures
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM properties').fetchone()[0] == 4
        assert conn.execute('SELECT status FROM ingestion_runs').fetchone()[0] == 'partial'
    assert db.get_top_deals(min_score=0) == []
    with pytest.raises(ValueError, match='persisted source audit'):
        db.verify_deal(1)


def test_dry_run_does_not_write_primary_audit_county_or_summary(monkeypatch, tmp_path):
    result = ingest(monkeypatch,dry_run=True)
    assert result['status'] == 'ok' and result['counts']['qualified'] == 1
    assert result['counts']['stored'] == 0 and result['counts']['published'] == 0
    assert not (tmp_path/'local.db').exists()
    assert not (tmp_path/'runs.json').exists()


def test_partial_source_stays_partial_and_cannot_be_published(monkeypatch):
    _,cfg = prepare(monkeypatch)
    result,props = FixtureAdapter(source_rows()).run(cfg,max_records=10)
    result.errors.append('source_error: page two failed')
    monkeypatch.setattr(runners,'fetch_parcels',lambda *a,**kw:(props,result))
    summary = runners.run('fixture',mode='etl-only',max_records=10)
    assert summary['status'] == 'degraded' and summary['counts']['stored'] == 4
    with pytest.raises(ValueError,match='Ingestion did not complete'):
        database.verify_deal(1)


@pytest.mark.parametrize('mutation', ['property','comp','record','run','county'])
def test_changing_underlying_evidence_atomically_revokes_publication(monkeypatch, mutation):
    ingest(monkeypatch)
    db = database.get_backend(); db.verify_deal(1)
    before = db.get_deal_for_verification(1)['revision']
    sql = {'property':"UPDATE properties SET has_improvements=1 WHERE id=1",
           'comp':"DELETE FROM comps WHERE id=1",
           'record':"UPDATE ingestion_records SET raw_payload='{}' WHERE id=2",
           'run':"UPDATE ingestion_runs SET status='failed' WHERE id=1",
           'county':"UPDATE counties SET payload=json_set(payload,'$.ingestion_authorized',0) WHERE county_id='fixture'"}[mutation]
    with db.connection() as conn: conn.execute(sql)
    changed = db.get_deal_for_verification(1)
    assert changed['revision'] > before and changed['verification_status'] == 'pending_review'
    assert db.get_top_deals(min_score=0) == []


@pytest.mark.parametrize('mutation', ['run_failed','raw_price','normalized_price','comp_unqualified','self_comp','distance','profit','asking_field','expired'])
def test_verification_reconstructs_evidence_instead_of_trusting_saved_status(monkeypatch, mutation):
    ingest(monkeypatch)
    deal,records,run = verification_inputs(database.get_backend())
    if mutation=='run_failed': run['status']='partial'
    elif mutation=='raw_price': records[0]['raw_payload']['PRICE']=999999
    elif mutation=='normalized_price': records[0]['normalized_payload']['asking_price']=999999
    elif mutation=='comp_unqualified': records[1]['raw_payload']['QUALIFIED']=False
    elif mutation=='self_comp': deal['comps'][0]['ingestion_record_id']=records[0]['id']
    elif mutation=='distance': deal['comps'][0]['distance_miles']=8
    elif mutation=='profit': deal['estimated_profit_low']+=1000
    elif mutation=='asking_field': records[0]['field_mapping'].pop('asking_price')
    elif mutation=='expired': run['metadata']['source_authorization']['last_validated_at']=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
    with pytest.raises(ValueError): verify_persisted_deal(deal,records,run)


def test_comp_replacement_is_atomic_and_empty_replacement_clears_stale_comps(monkeypatch):
    ingest(monkeypatch)
    db=database.get_backend(); db.verify_deal(1)
    comps=db.get_deal_comps(1)
    invalid=deepcopy(comps); invalid[1]['sale_price']=float('nan')
    with pytest.raises(ValueError): db.save_comps(1,invalid)
    assert db.get_deal_comps(1)==comps and db.get_top_deals(min_score=0)
    assert db.save_comps(1,[])==0
    assert db.get_deal_comps(1)==[] and db.get_top_deals(min_score=0)==[]


def test_run_registry_recovers_only_a_proven_missing_audit_row(monkeypatch):
    ingest(monkeypatch)
    db=database.get_backend()
    run_id=db.record_ingestion_run('fixture','running',{})
    with db.connection() as conn: conn.execute('DELETE FROM ingestion_runs WHERE id=?',(run_id,))
    entry=runregistry.record_run('fixture','ok',{},run_id=run_id)
    assert entry['audit_status']=='recovered_with_gap' and entry['status']=='degraded'
    assert entry['audit_run_id'] != run_id
    with db.connection() as conn:
        assert conn.execute('SELECT status FROM ingestion_runs WHERE id=?',(entry['audit_run_id'],)).fetchone()[0]=='partial'


def test_audit_finalization_transport_failure_does_not_create_a_second_run(monkeypatch):
    ingest(monkeypatch)
    db=database.get_backend()
    monkeypatch.setattr(db,'update_ingestion_run',lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('transport failed')))
    monkeypatch.setattr(db,'record_ingestion_run',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('Must not invent a new run')))
    entry=runregistry.record_run('fixture','ok',{},run_id=1)
    assert entry['status']=='degraded' and entry['audit_status']=='unavailable'


def test_audit_keys_are_scoped_by_source_and_preserve_nonfinite_raw_evidence():
    assert record_key('https://one.example',1,{}) != record_key('https://two.example',1,{})
    row=audit_record(1,'fixture',{'raw_payload':{'source_value':float('nan')},'status':'rejected'})
    json.dumps(row,allow_nan=False)
    assert row['raw_payload']['source_value']=='nan'


def test_scoped_audit_foreign_keys_reject_cross_county_linkage(monkeypatch):
    ingest(monkeypatch)
    db=database.get_backend()
    with pytest.raises(sqlite3.IntegrityError):
        db.record_ingestion_records(1,'other',[{'source_record_id':'bad','property_id':1,'status':'held'}])


def test_verification_loses_a_race_if_comparables_change_after_review(monkeypatch):
    ingest(monkeypatch)
    db=database.get_backend()
    import validation.publication as publication
    original=publication.verify_persisted_deal
    def racing_verifier(*args):
        result=original(*args)
        db.save_comps(1,[])
        return result
    monkeypatch.setattr(publication,'verify_persisted_deal',racing_verifier)
    with pytest.raises(RuntimeError,match='changed during verification'): db.verify_deal(1)
    assert db.get_top_deals(min_score=0)==[]


def test_ingestion_time_does_not_fabricate_source_freshness_or_verification(monkeypatch):
    ingest(monkeypatch)
    from config.counties.registry import get_county
    county=get_county('fixture')
    assert county.get('data_freshness') is None
    assert county['ingestion_status']=='ingested' and county['verification_status']=='source_verified'
    assert county['persisted_count']==4 and county['published_count']==0


def test_duplicate_county_apns_are_audited_and_held_not_arbitrarily_published(monkeypatch):
    rows=source_rows()
    rows.append({**rows[0],'OBJECTID':99,'PRICE':999999})
    result=ingest(monkeypatch,rows)
    assert result['status']=='ok' and result['counts']['qualified']==0
    assert result['counts']['skipped']==1 and result['hold_reasons']['duplicate_county_apn']==1
    assert len(database.get_backend().get_ingestion_records(result['audit_run_id']))==5
    assert database.get_top_deals(min_score=0)==[]


def test_all_invalid_identities_is_not_a_successful_ingestion(monkeypatch):
    result=ingest(monkeypatch,[{'OBJECTID':1,'ACRES':2}])
    assert result['status']=='error' and result['counts']['rejected']==1
    assert 'no_usable_parcel_identities' in result['error']


def test_mapping_replacement_cannot_bypass_source_authorization(monkeypatch):
    ingest(monkeypatch)
    deal,records,run=verification_inputs(database.get_backend())
    target=next(row for row in records if row.get('deal_id'))
    # Equivalent output is not permission to replace a reviewed mapping.
    target['field_mapping']['apn']=['APN']
    with pytest.raises(ValueError,match='mapping differs'):
        verify_persisted_deal(deal,records,run)


def test_canonical_raw_snapshot_must_match_the_stored_json_and_hash(monkeypatch):
    ingest(monkeypatch)
    deal,records,run=verification_inputs(database.get_backend())
    target=next(row for row in records if row.get('deal_id'))
    target['raw_payload_canonical']='{}'
    with pytest.raises(ValueError,match='raw source snapshot'):
        verify_persisted_deal(deal,records,run)


@pytest.mark.parametrize('classification',['Vacant house','Improved residential','SFR','Vacant commercial building'])
def test_vacant_building_or_conflicting_classification_is_not_vacant_land(monkeypatch,classification):
    rows=source_rows(); rows[0]['USE']=classification
    result=ingest(monkeypatch,rows)
    assert result['counts']['rejected']==1
    assert result['counts']['qualified']==0


@pytest.mark.parametrize('change',['price_per_acre','address','land_use','has_improvements','vacancy_evidence'])
def test_review_rejects_persisted_fields_that_no_longer_match_source(monkeypatch,change):
    ingest(monkeypatch)
    deal,records,run=verification_inputs(database.get_backend())
    if change=='price_per_acre': deal['comps'][0]['price_per_acre']=1
    elif change=='has_improvements': deal['properties'][change]=True
    elif change=='vacancy_evidence': deal['properties'][change]={}
    else: deal['properties'][change]='ALTERED_PRIVATE_VALUE'
    with pytest.raises(ValueError) as exc: verify_persisted_deal(deal,records,run)
    assert 'ALTERED_PRIVATE_VALUE' not in str(exc.value)
