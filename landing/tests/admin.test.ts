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
