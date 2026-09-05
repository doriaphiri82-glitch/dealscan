import { beforeEach, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
const mocks = vi.hoisted(() => ({ createServerClient: vi.fn(), getUser: vi.fn(), exchange: vi.fn(), setCookie: vi.fn() }))
vi.mock('@supabase/ssr', () => ({ createServerClient: mocks.createServerClient }))
vi.mock('next/headers', () => ({ cookies: async () => ({ getAll: () => [], set: mocks.setCookie }) }))
import { middleware } from '../middleware'
import { GET as callback } from '../app/auth/callback/route'
import { currentUser } from '../lib/supabase-server'

beforeEach(() => {
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', 'https://example.supabase.co')
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY', 'sb_publishable_fixture')
  mocks.createServerClient.mockReturnValue({ auth: { getUser: mocks.getUser, exchangeCodeForSession: mocks.exchange } })
  mocks.getUser.mockResolvedValue({ data: { user: null }, error: null })
  mocks.exchange.mockResolvedValue({ error: null })
})

it('redirects anonymous protected requests internally and preserves the requested path', async () => {
  const res = await middleware(new NextRequest('https://app.example/dashboard?tab=saved'))
  const location = new URL(res.headers.get('location')!)
  expect(location.origin).toBe('https://app.example')
  expect(location.pathname).toBe('/auth')
  expect(location.searchParams.get('next')).toBe('/dashboard?tab=saved')
  expect(res.headers.get('cache-control')).toContain('no-store')
})
it('fails closed when configuration or the auth server is unavailable', async () => {
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', '')
  expect((await middleware(new NextRequest('https://app.example/dashboard'))).status).toBe(307)
  expect(await currentUser()).toBeNull()
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', 'https://example.supabase.co')
  mocks.getUser.mockRejectedValue(new Error('network down'))
  expect((await middleware(new NextRequest('https://app.example/dashboard'))).status).toBe(307)
  expect(await currentUser()).toBeNull()
})
it('passes refreshed cookies to both the request and browser', async () => {
  mocks.createServerClient.mockImplementation((_url, _key, options) => {
    options.cookies.setAll([{ name: 'session', value: 'refreshed', options: { httpOnly: true } }])
    return { auth: { getUser: async () => ({ data: { user: { id: 'fixture-user' } }, error: null }) } }
  })
  const req = new NextRequest('https://app.example/dashboard')
  const res = await middleware(req)
  expect(req.cookies.get('session')?.value).toBe('refreshed')
  expect(res.cookies.get('session')?.value).toBe('refreshed')
})
it('does not accept an unverified session when getUser reports an error', async () => {
  mocks.getUser.mockResolvedValue({ data: { user: { id: 'invalid' } }, error: new Error('invalid token') })
  expect(await currentUser()).toBeNull()
})
it('does not allow a backslash open redirect after successful OAuth exchange', async () => {
  const res = await callback(new Request('https://app.example/auth/callback?code=fixture&next=%2F%5Cevil.example'))
  expect(res.headers.get('location')).toBe('https://app.example/my-dealscan')
})
it('handles missing codes, configuration, rejected exchanges and thrown auth errors', async () => {
  expect((await callback(new Request('https://app.example/auth/callback'))).headers.get('location')).toContain('missing_code')
  mocks.exchange.mockResolvedValue({ error: new Error('invalid code') })
  expect((await callback(new Request('https://app.example/auth/callback?code=fixture'))).headers.get('location')).toContain('callback_failed')
  mocks.exchange.mockRejectedValue(new Error('network down'))
  expect((await callback(new Request('https://app.example/auth/callback?code=fixture'))).headers.get('location')).toContain('callback_failed')
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', '')
  expect((await callback(new Request('https://app.example/auth/callback?code=fixture'))).headers.get('location')).toContain('auth_unavailable')
})
