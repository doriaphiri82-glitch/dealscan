import { NextRequest, NextResponse } from 'next/server'
import SEED_BUNDLE from '../../../lib/seed-bundle'

const KEY_TOP = 'deals:top'
type DealsSource = 'redis' | 'redis-proto' | 'kv' | 'seed'
const REDIS_URL = process.env.REDIS_URL || ''
const REDIS_TOKEN = process.env.REDIS_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || ''
const KV_URL = process.env.KV_REST_API_URL || ''
const KV_TOKEN = process.env.KV_REST_API_TOKEN || ''
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

async function readBundle(): Promise<{ data: unknown; source: DealsSource }> {
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
      /* fall through to the committed seed */
    }
  }
  return { data: SEED_BUNDLE, source: 'seed' }
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
    count: deals.length,
    deals: deals.slice(0, limit),
    generated_at: bundle.generated_at ?? null,
    meta: {
      status: bundle.meta?.status ?? 'ok',
      scraped_counties: bundle.meta?.scraped_counties ?? [],
      storage_source: source,
    },
  }, { headers: { 'Cache-Control': 'no-store' } })
}
