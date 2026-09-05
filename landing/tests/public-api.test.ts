import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET as list } from '../app/api/deals/route'
import { GET as detail } from '../app/api/deals/[apn]/route'
import { GET as health } from '../app/api/health/route'

// Isolated transport fixtures, never published or persisted.
const row = (extra = {}) => ({
  status: 'discovered', verification_status: 'verified', deal_score: 45,
  verified_at: new Date().toISOString(), verification_expires_at: new Date(Date.now()+3600000).toISOString(),
  source_url: 'https://county.example/parcel', asking_price: null,
  properties: { apn: 'fixture', county_id: 'fixture_county', owner_name: 'PRIVATE', owner_address: 'PRIVATE' },
  comps: [1,2,3].map(i => ({ source_apn:`comp-${i}`,county_id:'fixture_county',source_record_id:String(i),
    source_url:'https://county.example/sale',sale_qualified:true,vacant_at_sale:true,sale_price:10000,lot_size_acres:1,
    price_per_acre:10000,distance_miles:i,sale_date:new Date(Date.now()-86400000).toISOString(),owner_name:'PRIVATE' })),
  notes: 'PRIVATE', raw_payload: { secret: 'PRIVATE' }, ...extra,
})
const request = (path: string) => new NextRequest(`https://dealscan.example${path}`)

beforeEach(() => {
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', 'https://example.supabase.co')
  vi.stubEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY', 'sb_publishable_unit_test')
  vi.stubEnv('KV_REST_API_URL', 'https://old-cache.example')
  vi.stubEnv('KV_REST_API_TOKEN', 'unused')
})

describe('public deal boundary', () => {
  it('treats an empty working Supabase as authoritative', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json([])); vi.stubGlobal('fetch', fetch)
    const res = await list(request('/api/deals'))
    expect(res.status).toBe(200)
    expect((await res.json()).deals).toEqual([])
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(String(fetch.mock.calls[0][0])).toContain('verification_status=eq.verified')
  })
  it('does not resurrect missing details from a stale cache', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json([])); vi.stubGlobal('fetch', fetch)
    const res = await detail(request('/api/deals/fixture'), { params: Promise.resolve({ apn: 'fixture' }) })
    expect(res.status).toBe(404); expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('does not hide database errors or fall back to cache', async () => {
    const fetch = vi.fn().mockRejectedValue(new Error('timeout')); vi.stubGlobal('fetch', fetch)
    const res = await list(request('/api/deals'))
    expect(res.status).toBe(503); expect(fetch).toHaveBeenCalledTimes(1)
    expect(res.headers.get('cache-control')).toBe('no-store')
  })
  it('projects only public fields and rejects unverified rows', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json([row(), row({ verification_status: 'source_verified' })])))
    const res = await list(request('/api/deals'))
    const body = await res.json()
    expect(body.count).toBe(1); expect(body.deals[0].asking_price).toBeNull()
    expect(JSON.stringify(body)).not.toContain('PRIVATE')
    expect(body.deals[0]).not.toHaveProperty('properties')
  })
  it('rejects expired or missing verification independently of database RLS', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json([
      row({ verification_expires_at: new Date(Date.now()-1000).toISOString() }),
      row({ verified_at: null }), row({ verification_expires_at: null }),
    ])))
    const res = await list(request('/api/deals'))
    expect((await res.json()).deals).toEqual([])
  })
  it('serves traceable allowlisted comparable rows on the exact parcel detail', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json([row()])); vi.stubGlobal('fetch',fetch)
    const res = await detail(request('/api/deals/fixture?county_id=fixture_county'),{ params:Promise.resolve({apn:'fixture'}) })
    const body = await res.json()
    expect(body.deal.comps).toHaveLength(3)
    expect(body.deal.comps[0].source_record_id).toBe('1')
    expect(JSON.stringify(body)).not.toContain('PRIVATE')
    expect(new URL(fetch.mock.calls[0][0]).searchParams.get('select')).toContain('comps(')
  })
  it('preserves literal percent APNs and scopes identical APNs by county', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json([row()])); vi.stubGlobal('fetch', fetch)
    const res = await detail(request('/api/deals/50%25?county_id=fixture_county'), { params: Promise.resolve({ apn: '50%' }) })
    expect(res.status).toBe(200)
    const params = new URL(fetch.mock.calls[0][0]).searchParams
    expect(params.get('properties.apn')).toBe('eq."50%"')
    expect(params.get('properties.county_id')).toBe('eq."fixture_county"')
  })
  it('rejects ambiguous parcel identifiers instead of choosing a county', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json([row(), row()])))
    expect((await detail(request('/api/deals/fixture'), { params: Promise.resolve({ apn: 'fixture' }) })).status).toBe(409)
  })
  it('bounds pagination before issuing a request', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    expect((await list(request('/api/deals?limit=12junk'))).status).toBe(400)
    expect((await list(request('/api/deals?offset=100000'))).status).toBe(400)
    expect(fetch).not.toHaveBeenCalled()
  })
  it('uses a timeout and blocks credential forwarding through redirects', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json([])); vi.stubGlobal('fetch', fetch)
    await list(request('/api/deals'))
    expect(fetch.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal)
    expect(fetch.mock.calls[0][1].redirect).toBe('error')
    expect(fetch.mock.calls[0][1].cache).toBe('no-store')
  })
})

describe('health', () => {
  it('is healthy with an accessible empty database', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json([])))
    expect((await health()).status).toBe(200)
  })
  it.each([Response.json({ error: 'bad' }, { status: 500 }), Response.json({ unexpected: true })])('fails closed on invalid responses', async response => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    const res = await health(); expect(res.status).toBe(503)
    expect(res.headers.get('cache-control')).toContain('no-store')
  })
  it('reports missing configuration without a network request', async () => {
    vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', '')
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    const res = await health(); expect(res.status).toBe(503)
    expect((await res.json()).database).toBe('not-configured'); expect(fetch).not.toHaveBeenCalled()
  })
})
