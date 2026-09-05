import { PGlite } from '@electric-sql/pglite'
import { afterAll, beforeAll, expect, it } from 'vitest'
import { database, publishedFixture, asRole as queryAsRole } from './support/database'

let db: PGlite
beforeAll(async () => {
  db = await database()
  await publishedFixture(db)
}, 30000)
afterAll(async () => { await db?.close() })

const asRole = (role: 'anon' | 'authenticated', sql: string) => queryAsRole(db, role, sql)

it.each(['anon', 'authenticated'] as const)('RLS exposes only verified deals to %s', async role => {
  expect((await asRole(role, 'select property_id from deals')).rows).toEqual([{ property_id: 1 }])
  expect((await asRole(role, 'select apn from properties')).rows).toEqual([{ apn: 'fixture-public' }])
})
it.each(['anon', 'authenticated'] as const)('column grants prevent %s from reading owners or private metadata', async role => {
  await expect(asRole(role, 'select owner_name from properties')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select notes from deals')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select extra from counties')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select * from waitlist')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select raw_payload from ingestion_records')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select metadata from ingestion_runs')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select financial_evidence from deals')).rejects.toThrow(/permission denied/)
})
it.each(['anon', 'authenticated'] as const)('browser role %s cannot write or self-verify deals', async role => {
  await expect(asRole(role, "update deals set verification_status='verified' where property_id=2")).rejects.toThrow(/permission denied/)
  await expect(asRole(role, "insert into properties(apn,county_id) values('forbidden','fixture')")).rejects.toThrow(/permission denied/)
})
it('all public application tables retain RLS', async () => {
  const result = await db.query<{ relname: string; relrowsecurity: boolean }>("select relname,relrowsecurity from pg_class join pg_namespace n on n.oid=relnamespace where n.nspname='public' and relkind='r'")
  expect(result.rows.length).toBeGreaterThanOrEqual(7)
  expect(result.rows.every(row => row.relrowsecurity)).toBe(true)
})
