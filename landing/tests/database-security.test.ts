import { PGlite } from '@electric-sql/pglite'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll, expect, it } from 'vitest'

let db: PGlite
beforeAll(async () => {
  db = new PGlite()
  await db.exec('create role anon; create role authenticated; create role service_role bypassrls;')
  const migrations = fileURLToPath(new URL('../../supabase/migrations/', import.meta.url))
  for (const file of readdirSync(migrations).filter(file => file.endsWith('.sql')).sort()) {
    await db.exec(readFileSync(`${migrations}/${file}`, 'utf8'))
  }
  // Ephemeral Postgres-only security fixtures; never sent to any live backend.
  await db.exec(`
    insert into counties(county_id,county_name) values('fixture','Security fixture');
    insert into properties(id,apn,county_id,owner_name) values(1,'fixture-public','fixture','PRIVATE'),(2,'fixture-held','fixture','PRIVATE');
    insert into deals(property_id,status,verification_status) values(1,'discovered','verified'),(2,'discovered','source_verified');
  `)
}, 30000)
afterAll(async () => { await db?.close() })

async function asRole(role: string, sql: string) {
  await db.exec(`set role ${role}`)
  try { return await db.query(sql) }
  finally { await db.exec('reset role') }
}

it.each(['anon', 'authenticated'])('RLS exposes only verified deals to %s', async role => {
  expect((await asRole(role, 'select property_id from deals')).rows).toEqual([{ property_id: 1 }])
  expect((await asRole(role, 'select apn from properties')).rows).toEqual([{ apn: 'fixture-public' }])
})
it.each(['anon', 'authenticated'])('column grants prevent %s from reading owners or private metadata', async role => {
  await expect(asRole(role, 'select owner_name from properties')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select notes from deals')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select extra from counties')).rejects.toThrow(/permission denied/)
  await expect(asRole(role, 'select * from waitlist')).rejects.toThrow(/permission denied/)
})
it.each(['anon', 'authenticated'])('browser role %s cannot write or self-verify deals', async role => {
  await expect(asRole(role, "update deals set verification_status='verified' where property_id=2")).rejects.toThrow(/permission denied/)
  await expect(asRole(role, "insert into properties(apn,county_id) values('forbidden','fixture')")).rejects.toThrow(/permission denied/)
})
it('all public application tables retain RLS', async () => {
  const result = await db.query<{ relname: string; relrowsecurity: boolean }>("select relname,relrowsecurity from pg_class join pg_namespace n on n.oid=relnamespace where n.nspname='public' and relkind='r'")
  expect(result.rows.length).toBeGreaterThanOrEqual(7)
  expect(result.rows.every(row => row.relrowsecurity)).toBe(true)
})
