import { NextRequest, NextResponse } from 'next/server'

/*
 * GET /api/deals
 * Returns the top scored deals published by the pipeline.
 *
 * Storage resolution (same strategy as /api/waitlist):
 *   1. REDIS_URL (Upstash REST https:// or native redis://) — production
 *   2. KV_REST_API_URL + KV_REST_API_TOKEN — Vercel KV REST
 *   3. Repo artifact data/bundle.json (checked into the deployment)
 *
 * Returns a missing-data envelope (not an error) when no bundle exists yet,
 * so the site can fall back to its clearly-labeled demo section.
 */
const KEY_TOP = 'deals:top'

type DealsSource = 'redis' | 'redis-proto' | 'kv' | 'file' | null

const REDIS_URL = process.env.REDIS_URL || ''
const KV_URL = process.env.KV_REST_API_URL || ''
const KV_TOKEN = process.env.KV_REST_API_TOKEN || ''

const isRedisRest = /^https?:\/\//.test(REDIS_URL)
const isRedisProto = /^rediss?:\/\//.test(REDIS_URL)

// Cache across warm invocations.
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
  if (source === 'redis') {
    const res = await fetch(`${REDIS_URL}/get/${KEY_TOP}`)
    if (!res.ok) return null
    const json = (await res.json()) as { result?: string | null }
    return json.result ? JSON.parse(json.result) : null
  }
  if (source === 'redis-proto') {
    const client = await getRedis()
    const raw = client ? await client.get(KEY_TOP) : null
    return raw ? JSON.parse(raw) : null
  }
  return null
}

async function readBundle(): Promise<{ data: unknown; source: string }> {
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
      })
      if (res.ok) {
        const json = (await res.json()) as { result?: string | null }
        if (json.result) return { data: JSON.parse(json.result), source: 'kv' }
      }
    } catch {
      /* fall through */
    }
  }
  try {
    const fs = await import('fs')
    const path = await import('path')
    const raw = await fs.promises.readFile(
      path.join(process.cwd(), 'data', 'bundle.json'),
      'utf-8'
    )
    return { data: JSON.parse(raw), source: 'file' }
  } catch {
    return { data: null, source: 'none' }
  }
}

export async function GET(request: NextRequest) {
  const { data, source } = await readBundle()

  if (!data) {
    return NextResponse.json(
      { count: 0, deals: [], generated_at: null, meta: { status: 'no-data' } },
      { status: 200 }
    )
  }

  const bundle = data as {
    deals?: unknown[]
    generated_at?: string
    meta?: { status?: string; scraped_counties?: string[] }
  }

  const deals = Array.isArray(bundle.deals) ? bundle.deals : []
  const limitRaw = request.nextUrl.searchParams.get('limit')
  const limit = limitRaw ? Math.max(1, Math.min(50, parseInt(limitRaw, 10) || 25)) : 25

  return NextResponse.json({
    count: deals.length,
    deals: deals.slice(0, limit),
    generated_at: bundle.generated_at ?? null,
    meta: {
      status: bundle.meta?.status ?? 'ok',
      scraped_counties: bundle.meta?.scraped_counties ?? [],
      storage_source: source,
    },
  })
}