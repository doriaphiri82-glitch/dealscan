import { PGlite } from '@electric-sql/pglite'
import { afterAll, beforeAll, beforeEach, expect, it } from 'vitest'
import { database, publishedFixture, asRole } from './support/database'

let db: PGlite
beforeAll(async () => { db = await database() }, 30000)
beforeEach(async () => { await publishedFixture(db) })
afterAll(async () => { await db?.close() })

it('a service credential cannot publish an assessment without evidence', async () => {
  await expect(asRole(db, 'service_role', "update deals set verification_status='verified' where id=2")).rejects.toThrow(/Publication requires/)
  expect((await asRole(db, 'anon', 'select id from deals')).rows).toEqual([{ id: 1 }])
})

it.each([
  "update properties set has_improvements=true where id=1",
  "delete from comps where id=1",
  "update comps set sale_price=1 where id=1",
  "update ingestion_records set raw_payload='{}' where id=11",
  "update ingestion_runs set status='failed' where id=1",
  "update counties set extra=jsonb_set(extra,'{ingestion_authorized}','false') where county_id='fixture'",
])('underlying changes atomically revoke publication: %s', async sql => {
  const before = (await db.query<{ revision: number }>('select revision from deals where id=1')).rows[0].revision
  await asRole(db, 'service_role', sql)
  const after = (await db.query<{ revision: number; verification_status: string; verified_at: string | null }>('select revision,verification_status,verified_at from deals where id=1')).rows[0]
  expect(Number(after.revision)).toBeGreaterThan(Number(before))
  expect(after.verification_status).toBe('pending_review')
  expect(after.verified_at).toBeNull()
  expect((await asRole(db, 'anon', 'select id from deals')).rows).toEqual([])
})

it('observing the same unchanged property does not revoke a completed review', async () => {
  await asRole(db, 'service_role', 'update properties set last_seen_at=now() where id=1')
  expect((await asRole(db, 'anon', 'select id from deals')).rows).toEqual([{ id: 1 }])
})

it('financial evidence cannot be replaced with invented profit', async () => {
  await expect(asRole(db, 'service_role', 'update deals set estimated_profit_high=1000000 where id=1')).rejects.toThrow(/calculations do not match/)
  expect((await asRole(db, 'anon', 'select estimated_profit_high from deals')).rows).toEqual([{ estimated_profit_high: '75000' }])
})

it.each([null, {}, [{ source_url: 'https://county.example', source_record_id: '1' }],
  [{ source_url: 'https://county.example', source_record_id: '1', sale_price: 'NaN', lot_size_acres: 1, distance_miles: 1, sale_date: '2026-01-01' }],
])('invalid comparable replacement is non-destructive (%j)', async payload => {
  await expect(db.query('select public.replace_deal_comps(1,$1::jsonb)', [JSON.stringify(payload)])).rejects.toThrow()
  expect((await db.query('select count(*)::int n from comps where deal_id=1')).rows).toEqual([{ n: 3 }])
  expect((await asRole(db, 'anon', 'select id from deals')).rows).toEqual([{ id: 1 }])
})

it('empty comparable replacement removes stale sales and revokes the deal', async () => {
  await asRole(db, 'service_role', "select public.replace_deal_comps(1,'[]')")
  expect((await db.query('select count(*)::int n from comps')).rows).toEqual([{ n: 0 }])
  expect((await asRole(db, 'anon', 'select id from deals')).rows).toEqual([])
})

it.each(['anon', 'authenticated'] as const)('browser role %s cannot invoke write RPCs', async role => {
  await expect(asRole(db, role, "select public.replace_deal_comps(1,'[]')")).rejects.toThrow(/permission denied/)
  await expect(asRole(db, role, "select public.hold_deals_for_parcels('fixture',array['fixture-public'])")).rejects.toThrow(/permission denied/)
})

it('uniqueness and county-scoped foreign keys protect idempotency and lineage', async () => {
  await expect(db.exec('insert into deals(property_id) values(1)')).rejects.toThrow(/unique/)
  await db.exec("insert into counties(county_id,county_name) values('other','Other fixture')")
  await expect(db.exec("insert into ingestion_records(run_id,county_id,record_key,status) values(1,'other','wrong-county','held')")).rejects.toThrow(/foreign key/)
})

it('expired validation cannot renew publication', async () => {
  await db.exec("update ingestion_runs set metadata=jsonb_set(metadata,'{source_validated_at}',to_jsonb(now()-interval '8 days')) where id=1")
  await expect(asRole(db, 'service_role', "update deals set verification_status='verified' where id=1")).rejects.toThrow(/Publication requires/)
})

it('upgrades the earlier audit schema without treating legacy history as publication evidence', async () => {
  const legacy = await database(`
    insert into counties(county_id,county_name) values('legacy','Legacy fixture');
    create table ingestion_runs(id bigserial primary key,county_id text,status text check(status in ('completed','partial','failed')),
      records_seen integer default 0,records_normalized integer default 0,records_persisted integer default 0,
      records_rejected integer default 0,metadata jsonb default '{}');
    create table ingestion_records(id bigserial primary key,run_id bigint,county_id text,raw_payload jsonb,
      normalized_payload jsonb,property_id bigint,status text);
    alter table ingestion_records enable row level security;
    create policy legacy_open_audit on ingestion_records for select to anon using (true);
    grant select(raw_payload) on ingestion_records to anon;
    grant select(owner_name) on properties to anon;
    create policy legacy_open_properties on properties for select to anon using (true);
    insert into ingestion_runs(county_id,status,records_seen) values('legacy','completed',1);
    insert into ingestion_records(run_id,county_id,raw_payload,normalized_payload,status) values(1,'legacy','{"APN":"legacy"}','{}','normalized');
  `)
  try {
    const rows = (await legacy.query<{ status: string; metadata: { legacy_status: string; audit_gap: boolean } }>('select status,metadata from ingestion_runs')).rows
    expect(rows[0].status).toBe('partial')
    expect(rows[0].metadata).toMatchObject({ legacy_status: 'completed', audit_gap: true })
    expect((await legacy.query('select record_key from ingestion_records')).rows).toEqual([{ record_key: 'legacy-1' }])
    await asRole(legacy, 'service_role', "insert into ingestion_runs(county_id,run_key,status) values('legacy','new-contract','running')")
    await expect(asRole(legacy, 'anon', 'select raw_payload from ingestion_records')).rejects.toThrow(/permission denied/)
    await expect(asRole(legacy, 'anon', 'select owner_name from properties')).rejects.toThrow(/permission denied/)
    await legacy.exec("insert into properties(apn,county_id) values('private-legacy','legacy')")
    expect((await asRole(legacy, 'anon', 'select apn from properties')).rows).toEqual([])
  } finally { await legacy.close() }
}, 30000)

it('fails explicitly on an unsupported legacy audit key type rather than destroying history', async () => {
  await expect(database('create table ingestion_runs(id uuid primary key);')).rejects.toThrow(/Audit IDs must be/)
}, 30000)
