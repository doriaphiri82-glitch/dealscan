import { expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ user: vi.fn(), read: vi.fn() }))
vi.mock('../lib/supabase-server', () => ({ currentUser: mocks.user }))
vi.mock('../lib/supabase-private', () => ({ privateRpc: mocks.read }))
import { GET } from '../app/api/admin/coverage/route'

it('authorizes admin API independently of middleware', async () => {
  mocks.user.mockResolvedValue(null)
  expect((await GET()).status).toBe(401)
  mocks.user.mockResolvedValue({ user_metadata: { role: 'admin' }, app_metadata: {} })
  expect((await GET()).status).toBe(403)
  expect(mocks.read).not.toHaveBeenCalled()
})
it('reads real persisted coverage and does not assume local files ship to Vercel', async () => {
  mocks.user.mockResolvedValue({ app_metadata: { role: 'admin' } })
  mocks.read.mockResolvedValue([])
  const res = await GET()
  expect(res.status).toBe(200)
  expect((await res.json()).counties).toEqual([])
  expect(res.headers.get('cache-control')).toContain('private')
})


it('does not expose raw county metadata or stale batch publication counts', async () => {
  mocks.user.mockResolvedValue({ app_metadata: { role: 'admin' } })
  mocks.read.mockResolvedValue([{ county: { county_id:'fixture', county_name:'Fixture',
    published_count:999, data_freshness:null, last_successful_run:new Date().toISOString(),
    extra: { token:'PRIVATE', notes:'PRIVATE', last_validated_at:'2020-01-01T00:00:00Z' },
    validation_status:'valid' }, stored_total:25, verified_total:0 }])
  const body = await (await GET()).json()
  expect(body.counties[0].published).toBe(0)
  expect(body.counties[0].records).toBe(25)
  expect(body.counties[0].ingestion_ready).toBe(false)
  expect(body.counties[0].source_stage).toBe('validation_expired')
  expect(body.counties[0].data_freshness).toBeNull()
  expect(JSON.stringify(body)).not.toContain('PRIVATE')
})

it('returns a failure rather than a truncated or malformed successful snapshot', async () => {
  mocks.user.mockResolvedValue({ app_metadata: { role: 'admin' } })
  mocks.read.mockResolvedValue({ error:'PRIVATE' })
  expect((await GET()).status).toBe(503)
})


it('rejects repeated county pages instead of inflating national totals',async()=>{
  mocks.user.mockResolvedValue({app_metadata:{role:'admin'}})
  const county={county:{county_id:'fixture'},stored_total:0,verified_total:0}
  mocks.read.mockResolvedValue([county,county])
  expect((await GET()).status).toBe(503)
})

it.each([null,-1,'25',Number.MAX_SAFE_INTEGER+1])('does not convert malformed inventory counts into a successful zero: %s',async count=>{
  mocks.user.mockResolvedValue({app_metadata:{role:'admin'}})
  mocks.read.mockResolvedValue([{county:{county_id:'fixture'},stored_total:count,verified_total:0}])
  expect((await GET()).status).toBe(503)
})

it('does not report more public opportunities than persisted properties',async()=>{
  mocks.user.mockResolvedValue({app_metadata:{role:'admin'}})
  mocks.read.mockResolvedValue([{county:{county_id:'fixture'},stored_total:0,verified_total:1}])
  expect((await GET()).status).toBe(503)
})

it('keeps private errors out of the response and never falls back to local registry files',async()=>{
  mocks.user.mockResolvedValue({app_metadata:{role:'admin'}})
  mocks.read.mockRejectedValue(new Error('PRIVATE_OWNER_OR_DATABASE_DETAIL'))
  const response=await GET()
  expect(response.status).toBe(503)
  expect(JSON.stringify(await response.json())).not.toContain('PRIVATE_OWNER')
  expect(response.headers.get('cache-control')).toContain('no-store')
})
