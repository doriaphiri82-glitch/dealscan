import { NextRequest, NextResponse } from 'next/server'

import SEED_BUNDLE from '../../../../lib/seed-bundle'

const KEY_PREFIX = 'deal:'

const REDIS_URL = process.env.REDIS_URL || ''
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

async function readFromRedis(key: string): Promise<unknown | null> {
  if (isRedisRest) {
    try {
      const headers = KV_TOKEN ? { Authorization: `Bearer ${KV_TOKEN}` } : undefined
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

export async function GET(
  _request: NextRequest,
  { params }: { params: { apn: string } }
) {
  const apn = decodeURIComponent(params.apn)
  let report: unknown | null = null

  if (isRedisRest || isRedisProto) {
    report = await readFromRedis(`${KEY_PREFIX}${apn}`)
  } else if (KV_URL && KV_TOKEN) {
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
      /* fall through */
    }
  }

  if (!report) {
    report = SEED_BUNDLE.deals.find((d) => d.apn === apn) ?? null
  }

  if (!report) {
    return NextResponse.json(
      { error: 'Deal not found', meta: { status: 'no-data', apn } },
      { status: 404, headers: { 'Cache-Control': 'no-store' } }
    )
  }
  return NextResponse.json({ deal: report, meta: { apn } }, { headers: { 'Cache-Control': 'no-store' } })
}
