import { NextRequest, NextResponse } from 'next/server'

const KEY_TOP = 'deals:top'
type DealsSource = 'supabase' | 'redis' | 'redis-proto' | 'kv' | 'none'
const REDIS_URL = process.env.REDIS_URL || ''
const REDIS_TOKEN = process.env.REDIS_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || ''
const KV_URL = process.env.KV_REST_API_URL || ''
const KV_TOKEN = process.env.KV_REST_API_TOKEN || ''
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
const isRedisRest = /^https?:\/\//.test(REDIS_URL)
const isRedisProto = /^rediss?:\/\//.test(REDIS_URL)

const globalForRedis = globalThis as unknown as {
  __dealsRedis?: { client: { get: (k: string) => Promise<string | null> } | null }
}

async function getRedis(): Promise<{ get: (k: string) => Promise<string | null> } | null> {
  if (!isRedisProto) return null
  if (globalForRedis.__dealsRedis?.client) return globalForRedis.__dealsRedis.client
  try {
    const mod = await import('redis')
    const client = mod.createClient({ url: REDIS_URL })
    await client.connect()
    globalForRedis.__dealsRedis = { client }
    return client
  } catch {
    return null
  }
}

async function readFromRedis(source: DealsSource): Promise<unknown | null> {
  try {
    if (source === 'redis') {
      const headers = REDIS_TOKEN ? { Authorization: `Bearer ${REDIS_TOKEN}` } : undefined
      const res = await fetch(`${REDIS_URL}/get/${KEY_TOP}`, { headers, cache: 'no-store' })
      if (!res.ok) return null
      const json = (await res.json()) as { result?: string | null }
      return json.result ? JSON.parse(json.result) : null
    }
    if (source === 'redis-proto') {
      const client = await getRedis()
      const raw = client ? await client.get(KEY_TOP) : null
      return raw ? JSON.parse(raw) : null
    }
  } catch {
    return null
  }
  return null
}

async function readFromSupabase(): Promise<unknown[] | null> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return null
  try {
    const params = new URLSearchParams({
      status: 'eq.discovered',
      verification_status: 'eq.verified',
      select: 'id,deal_score,asking_price,estimated_arv_low,estimated_arv_high,estimated_profit_low,estimated_profit_high,recommended_offer_low,recommended_offer_high,motivation_signals,market_velocity,competition_level,status,source,source_url,source_vendor,source_quality,verification_status,data_freshness,valuation_basis,valuation_confidence,updated_at,properties!inner(apn,county_id,address,lot_size_acres,owner_name,owner_state,tax_delinquent_years,zoning)',
      order: 'deal_score.desc',
      limit: '50',
    })
    const res = await fetch(`${SUPABASE_URL.replace(/\/$/, '')}/rest/v1/deals?${params.toString()}`, {
      headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
      cache: 'no-store',
    })
    if (!res.ok) return null
    const rows = (await res.json()) as Array<Record<string, unknown>>
    return rows.map((row) => {
      const property = (row.properties || {}) as Record<string, unknown>
      const { properties: _properties, ...deal } = row
      return { ...deal, ...property }
    })
  } catch {
    return null
  }
}

async function readBundle(): Promise<{ data: unknown; source: DealsSource }> {
  const supabaseDeals = await readFromSupabase()
  if (supabaseDeals) {
    return {
      data: { deals: supabaseDeals, generated_at: new Date().toISOString(), meta: { status: 'ok', scraped_counties: [] } },
      source: 'supabase',
    }
  }
  if (isRedisRest) {
    const d = await readFromRedis('redis')
    if (d) return { data: d, source: 'redis' }
  }
  if (isRedisProto) {
    const d = await readFromRedis('redis-proto')
    if (d) return { data: d, source: 'redis-proto' }
  }
  if (KV_URL && KV_TOKEN) {
    try {
      const res = await fetch(`${KV_URL}/get/${KEY_TOP}`, {
        headers: { Authorization: `Bearer ${KV_TOKEN}` },
        cache: 'no-store',
      })
      if (res.ok) {
        const json = (await res.json()) as { result?: string | null }
        if (json.result) return { data: JSON.parse(json.result), source: 'kv' }
      }
    } catch {
      /* no published cache available */
    }
  }
  return { data: { deals: [], generated_at: null, meta: { status: 'no-data', scraped_counties: [] } }, source: 'none' }
}

export async function GET(request: NextRequest) {
  const { data, source } = await readBundle()
  const bundle = (data || {}) as {
    deals?: unknown[]
    generated_at?: string
    meta?: { status?: string; scraped_counties?: string[] }
  }
  const deals = Array.isArray(bundle.deals) ? bundle.deals : []
  const raw = request.nextUrl.searchParams.get('limit')
  const parsed = raw ? parseInt(raw, 10) : 25
  const limit = Math.max(1, Math.min(50, Number.isFinite(parsed) ? parsed : 25))

  return NextResponse.json({
    count: Math.min(deals.length, limit),
    deals: deals.slice(0, limit),
    generated_at: bundle.generated_at ?? null,
    meta: {
      status: bundle.meta?.status ?? (deals.length ? 'ok' : 'no-data'),
      scraped_counties: bundle.meta?.scraped_counties ?? [],
      storage_source: source,
    },
  }, { headers: { 'Cache-Control': 'no-store' } })
}
