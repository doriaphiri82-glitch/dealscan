import { NextRequest, NextResponse } from 'next/server'

const KEY_PREFIX = 'deal:'
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

async function readFromRedis(key: string): Promise<unknown | null> {
  if (isRedisRest) {
    try {
      const headers = REDIS_TOKEN ? { Authorization: `Bearer ${REDIS_TOKEN}` } : undefined
      const res = await fetch(`${REDIS_URL}/get/${encodeURIComponent(key)}`, { headers, cache: 'no-store' })
      if (!res.ok) return null
      const json = (await res.json()) as { result?: string | null }
      return json.result ? JSON.parse(json.result) : null
    } catch {
      return null
    }
  }
  if (isRedisProto) {
    const client = await getRedis()
    try {
      const raw = client ? await client.get(key) : null
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }
  return null
}

async function readFromSupabase(apn: string): Promise<unknown | null> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return null
  try {
    const params = new URLSearchParams({
      status: 'eq.discovered',
      verification_status: 'eq.verified',
      'properties.apn': `eq.${apn}`,
      select: 'id,deal_score,asking_price,estimated_arv_low,estimated_arv_high,estimated_profit_low,estimated_profit_high,recommended_offer_low,recommended_offer_high,motivation_signals,market_velocity,competition_level,status,source,source_url,source_vendor,source_quality,verification_status,data_freshness,valuation_basis,valuation_confidence,updated_at,properties!inner(apn,county_id,address,lot_size_acres,owner_name,owner_state,tax_delinquent_years,zoning)',
      limit: '1',
    })
    const res = await fetch(`${SUPABASE_URL.replace(/\/$/, '')}/rest/v1/deals?${params.toString()}`, {
      headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
      cache: 'no-store',
    })
    if (!res.ok) return null
    const rows = (await res.json()) as Array<Record<string, unknown>>
    const row = rows[0]
    if (!row) return null
    const property = (row.properties || {}) as Record<string, unknown>
    const { properties: _properties, ...deal } = row
    return { ...deal, ...property }
  } catch {
    return null
  }
}

export async function GET(
  _request: NextRequest,
  { params }: { params: { apn: string } }
) {
  const apn = decodeURIComponent(params.apn)
  let report: unknown | null = await readFromSupabase(apn)

  if (!report && (isRedisRest || isRedisProto)) {
    report = await readFromRedis(`${KEY_PREFIX}${apn}`)
  } else if (!report && KV_URL && KV_TOKEN) {
    try {
      const res = await fetch(`${KV_URL}/get/${encodeURIComponent(`${KEY_PREFIX}${apn}`)}`, {
        headers: { Authorization: `Bearer ${KV_TOKEN}` },
        cache: 'no-store',
      })
      if (res.ok) {
        const json = (await res.json()) as { result?: string | null }
        if (json.result) report = JSON.parse(json.result)
      }
    } catch {
      /* no published cache available */
    }
  }

  if (!report) {
    return NextResponse.json(
      { error: 'Deal not found', meta: { status: 'no-data', apn } },
      { status: 404, headers: { 'Cache-Control': 'no-store' } }
    )
  }
  return NextResponse.json({ deal: report, meta: { apn } }, { headers: { 'Cache-Control': 'no-store' } })
}
