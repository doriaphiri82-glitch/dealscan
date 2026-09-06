import { afterAll, beforeAll, expect, it } from 'vitest'
import { PGlite } from '@electric-sql/pglite'
import { database, asRole, publishedFixture } from './support/database'
let db: PGlite
beforeAll(async () => { db = await database() }, 30000)
afterAll(async () => { await db?.close() })

it('atomically de-duplicates signups while preserving real consent', async () => {
  await asRole(db,'service_role',`select join_waitlist('person@example.com','website',repeat('a',64))`)
  await asRole(db,'service_role',`select join_waitlist('person@example.com','website',repeat('b',64))`)
  const result = await db.query<{ total: number }>('select count(*)::integer total from waitlist where consented_at is not null')
  expect(result.rows[0].total).toBe(1)
})

it('enforces a durable limit and does not insert rejected addresses', async () => {
  const signup = `select join_waitlist('limited@example.com','website',repeat('c',64)) as accepted`
  for (let i=0;i<20;i++) expect((await asRole(db,'service_role',signup)).rows[0]).toEqual({ accepted: true })
  expect((await asRole(db,'service_role',`select join_waitlist('blocked@example.com','website',repeat('c',64)) as accepted`)).rows[0]).toEqual({ accepted: false })
  expect((await db.query("select email from waitlist where email='blocked@example.com'")).rows).toEqual([])
})

it('does not expose signup writes, emails, rate keys or private coverage RPCs to browser roles', async () => {
  for (const role of ['anon','authenticated'] as const) {
    for (const sql of [
      'select email,consented_at from waitlist', 'select request_key from waitlist_request_limits',
      `select join_waitlist('private@example.com','website',repeat('d',64))`,
      'select * from county_operational_snapshot()',
    ]) await expect(asRole(db,role,sql)).rejects.toThrow(/permission denied/)
  }
})

it('computes current verified coverage instead of trusting stale last-batch counters', async () => {
  await publishedFixture(db)
  await db.exec("update counties set published_count=999,persisted_count=999 where county_id='fixture'")
  // Updating ordinary counters does not revoke unchanged evidence.
  let rows = (await asRole(db,'service_role','select stored_total,verified_total from county_operational_snapshot()')).rows
  expect(rows).toEqual([{ stored_total: 2, verified_total: 1 }])
  await db.exec("update deals set verification_status='pending_review' where id=1")
  rows = (await asRole(db,'service_role','select stored_total,verified_total from county_operational_snapshot()')).rows
  expect(rows).toEqual([{ stored_total: 2, verified_total: 0 }])
})
