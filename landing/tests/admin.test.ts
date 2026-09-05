import { expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ user: vi.fn(), read: vi.fn() }))
vi.mock('../lib/supabase-server', () => ({ currentUser: mocks.user }))
vi.mock('../lib/public-deals', () => ({ supabaseRead: mocks.read }))
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
