import { beforeEach, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET, POST } from '../app/api/waitlist/route'

const request = (input: unknown = { email: 'person@example.com', consent: true }, extra: Record<string, string> = {}) =>
  new NextRequest('https://app.example/api/waitlist', { method: 'POST',
    headers: { origin: 'https://app.example', 'content-type': 'application/json', ...extra }, body: JSON.stringify(input) })

beforeEach(() => {
  vi.stubEnv('WAITLIST_CONTACT_EMAIL','privacy@example.com')
  vi.stubEnv('SUPABASE_URL', 'https://database.example')
  vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY', 'sb_secret_ephemeral_test')
})

it('saves one consented address through an atomic private RPC', async () => {
  const fetch = vi.fn().mockImplementation(async () => Response.json(true)); vi.stubGlobal('fetch', fetch)
  const response = await POST(request({ email: '  Person@Example.COM ', consent: true }))
  expect(response.status).toBe(202)
  expect(await response.json()).not.toHaveProperty('position')
  expect(fetch).toHaveBeenCalledTimes(1)
  const [url, init] = fetch.mock.calls[0]
  expect(url).toBe('https://database.example/rest/v1/rpc/join_waitlist')
  const body = JSON.parse(init.body)
  expect(body.p_email).toBe('person@example.com')
  expect(body.p_request_key).toMatch(/^[a-f0-9]{64}$/)
  expect(init.headers).not.toHaveProperty('Authorization')
  expect(init.redirect).toBe('error'); expect(init.cache).toBe('no-store')
  expect(init.signal).toBeInstanceOf(AbortSignal)
})

it('returns the same response for duplicate submissions without reading any emails', async () => {
  const fetch = vi.fn().mockImplementation(async () => Response.json(true)); vi.stubGlobal('fetch', fetch)
  const first = await POST(request()); const second = await POST(request())
  expect(await first.json()).toEqual(await second.json())
  expect(fetch.mock.calls.every(([,init]) => init.method === 'POST')).toBe(true)
})

it.each([false, { unexpected: 'PRIVATE' }])('does not pretend a rejected or malformed write succeeded', async value => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(value)))
  const response = await POST(request())
  expect(response.status).toBe(value === false ? 429 : 503)
  expect(JSON.stringify(await response.json())).not.toContain('PRIVATE')
})

it('fails closed without credentials instead of storing personal data in tmp or cache', async () => {
  vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY', '')
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  expect((await POST(request())).status).toBe(503)
  expect(fetch).not.toHaveBeenCalled()
})

it('does not forward private credentials through redirects or print private database errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('PRIVATE', { status: 307, headers: { Location: 'https://other.example' } })))
  const response = await POST(request())
  expect(response.status).toBe(503)
  expect(JSON.stringify(await response.json())).not.toContain('PRIVATE')
})

it.each([{}, [], null, { email: 'a@b.test' }, { email: 'bad', consent: true }, { email: 'a'.repeat(300)+'@b.test', consent: true }])('rejects invalid or unconsented input before private writes', async input => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  expect((await POST(request(input))).status).toBe(400)
  expect(fetch).not.toHaveBeenCalled()
})

it('rejects cross-origin and form-based signup attempts', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  expect((await POST(request(undefined, { origin: 'https://other.example' }))).status).toBe(403)
  expect((await POST(request(undefined, { 'content-type': 'text/plain' }))).status).toBe(415)
  expect(fetch).not.toHaveBeenCalled()
})

it('caps streamed bodies even without a declared content length', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  expect((await POST(request({ email: 'x'.repeat(10000) }))).status).toBe(413)
  expect(fetch).not.toHaveBeenCalled()
})

it('never exposes waitlist emails, counts or membership over GET', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  const response = await GET()
  expect(response.status).toBe(405); expect(response.headers.get('allow')).toBe('POST')
  expect(fetch).not.toHaveBeenCalled()
})


it('requires an operator contact before collecting personal data',async()=>{
  vi.stubEnv('WAITLIST_CONTACT_EMAIL','')
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
  expect((await POST(request())).status).toBe(503)
  expect(fetch).not.toHaveBeenCalled()
})


it('does not mix one project auth with a different private database',async()=>{
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL','https://different.example')
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
  expect((await POST(request())).status).toBe(503)
  expect(fetch).not.toHaveBeenCalled()
})


it.each(['http://app.example','https://app.example/path','https://user@app.example','https://app.example?extra=1','null'])('rejects non-origin and cross-scheme origin headers: %s',async origin=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
  expect((await POST(request(undefined,{origin,host:'app.example'}))).status).toBe(403)
  expect(fetch).not.toHaveBeenCalled()
})

it('accepts the HTTPS preview host without trusting an injected forwarded protocol',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json(true)))
  const send=(origin:string)=>new NextRequest('http://0.0.0.0:3000/api/waitlist',{method:'POST',
    headers:{origin,host:'3000-example.e2b.app','content-type':'application/json','x-forwarded-proto':'http'},
    body:JSON.stringify({email:'person@example.com',consent:true})})
  expect((await POST(send('https://3000-example.e2b.app'))).status).toBe(202)
  expect((await POST(send('http://3000-example.e2b.app'))).status).toBe(403)
})

it('rejects invalid UTF-8 before invoking private storage',async()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
  const body=new Uint8Array([...new TextEncoder().encode('{"email":"'),0xff,...new TextEncoder().encode('@example.com","consent":true}')])
  const incoming=new NextRequest('https://app.example/api/waitlist',{method:'POST',headers:{origin:'https://app.example','content-type':'application/json'},body})
  expect((await POST(incoming)).status).toBe(400)
  expect(fetch).not.toHaveBeenCalled()
})
