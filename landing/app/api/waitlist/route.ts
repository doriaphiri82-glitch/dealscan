import { NextRequest, NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

interface WaitlistEntry {
  email: string
  source: string
  timestamp: string
}

/*
 * Storage strategy (env-order aware):
 *  1. Vercel KV REST (Upstash REST) — used when KV_REST_API_URL +
 *     KV_REST_API_TOKEN are present.
 *  2. REDIS_URL — supports both Upstash REST (`https://…`) and the native
 *     Redis protocol (`redis://` / `rediss://`, requires `redis` package).
 *  3. Local file in `data/` — works in local `next dev` (writable FS).
 *  4. /tmp file — last resort for read-only serverless runtimes.
 *
 * Never throws a bare 500: if every backend is unavailable we return a
 * clear, graceful 503 instead of an opaque "Internal server error".
 */
const KV_URL = process.env.KV_REST_API_URL || ''
const KV_TOKEN = process.env.KV_REST_API_TOKEN || ''
const REDIS_URL = process.env.REDIS_URL || ''
const KV_KEY = 'dealscan:waitlist'

const LOCAL_FILE = path.join(process.cwd(), 'data', 'waitlist.json')
const TMP_FILE = '/tmp/dealscan-waitlist.json'

const isRedisProtocol = /^rediss?:\/\//.test(REDIS_URL)
const isRedisRest = /^https:\/\//.test(REDIS_URL)

/* ---------- Redis protocol client (redis://, rediss://) ---------- */

// Cache the client across warm invocations to avoid reconnecting each time.
const globalForRedis = globalThis as unknown as {
  __dealscanRedis?: { client: { get: (k: string) => Promise<string | null>; set: (k: string, v: string) => Promise<unknown>; quit?: () => Promise<unknown> } | null; connecting?: Promise<unknown> | null }
}

type RedisLike = { get: (k: string) => Promise<string | null>; set: (k: string, v: string) => Promise<unknown>; quit?: () => Promise<unknown> }

async function getRedisClient(): Promise<RedisLike | null> {
  if (!isRedisProtocol) return null
  if (globalForRedis.__dealscanRedis?.client) return globalForRedis.__dealscanRedis.client
  try {
    const mod = await import('redis')
    const client = mod.createClient({ url: REDIS_URL })
    await client.connect()
    globalForRedis.__dealscanRedis = { client, connecting: null }
    return client
  } catch {
    return null
  }
}

async function redisProtoRead(): Promise<WaitlistEntry[] | null> {
  const client = await getRedisClient()
  if (!client) return null
  try {
    const raw = await client.get(KV_KEY)
    if (raw == null) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as WaitlistEntry[]) : []
  } catch {
    return null
  }
}

async function redisProtoWrite(entries: WaitlistEntry[]): Promise<boolean> {
  const client = await getRedisClient()
  if (!client) return false
  try {
    await client.set(KV_KEY, JSON.stringify(entries))
    return true
  } catch {
    return false
  }
}

/* ---------- Vercel KV (Upstash REST) ---------- */

async function kvRead(): Promise<WaitlistEntry[] | null> {
  if (!KV_URL || !KV_TOKEN) return null
  try {
    const res = await fetch(`${KV_URL}/get/${KV_KEY}`, {
      headers: { Authorization: `Bearer ${KV_TOKEN}` },
    })
    if (!res.ok) return null
    const json = (await res.json()) as { result?: string | null }
    if (json.result == null) return []
    const parsed = JSON.parse(json.result)
    return Array.isArray(parsed) ? (parsed as WaitlistEntry[]) : []
  } catch {
    return null
  }
}

async function kvWrite(entries: WaitlistEntry[]): Promise<boolean> {
  if (!KV_URL || !KV_TOKEN) return false
  try {
    const res = await fetch(`${KV_URL}/set/${KV_KEY}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${KV_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(entries),
    })
    return res.ok
  } catch {
    return false
  }
}

/* ---------- Upstash-style REST on REDIS_URL (https://…) ---------- */

async function redisRestRead(): Promise<WaitlistEntry[] | null> {
  if (!isRedisRest) return null
  try {
    const res = await fetch(`${REDIS_URL}/get/${KV_KEY}`)
    if (!res.ok) return null
    const json = (await res.json()) as { result?: string | null }
    if (json.result == null) return []
    const parsed = JSON.parse(json.result)
    return Array.isArray(parsed) ? (parsed as WaitlistEntry[]) : []
  } catch {
    return null
  }
}

async function redisRestWrite(entries: WaitlistEntry[]): Promise<boolean> {
  if (!isRedisRest) return false
  try {
    const res = await fetch(`${REDIS_URL}/set/${KV_KEY}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entries),
    })
    return res.ok
  } catch {
    return false
  }
}

/* ---------- Filesystem backends ---------- */

async function fsRead(file: string): Promise<WaitlistEntry[] | null> {
  try {
    const data = await fs.readFile(file, 'utf-8')
    const parsed = JSON.parse(data)
    return Array.isArray(parsed) ? (parsed as WaitlistEntry[]) : []
  } catch {
    return null
  }
}

async function fsWrite(file: string, entries: WaitlistEntry[]): Promise<boolean> {
  try {
    const dir = path.dirname(file)
    if (dir !== path.dirname(TMP_FILE)) {
      await fs.mkdir(dir, { recursive: true })
    }
    await fs.writeFile(file, JSON.stringify(entries, null, 2))
    return true
  } catch {
    return false
  }
}

/* ---------- Orchestration ---------- */

type StorageSource = 'kv-rest' | 'redis-rest' | 'redis-proto' | 'local' | 'tmp' | 'none'

async function readEntries(): Promise<{ entries: WaitlistEntry[]; source: StorageSource }> {
  if (KV_URL && KV_TOKEN) {
    const kv = await kvRead()
    if (kv) return { entries: kv, source: 'kv-rest' }
  }
  if (isRedisRest) {
    const rest = await redisRestRead()
    if (rest) return { entries: rest, source: 'redis-rest' }
  }
  if (isRedisProtocol) {
    const proto = await redisProtoRead()
    if (proto) return { entries: proto, source: 'redis-proto' }
  }
  const local = await fsRead(LOCAL_FILE)
  if (local) return { entries: local, source: 'local' }
  const tmp = await fsRead(TMP_FILE)
  if (tmp) return { entries: tmp, source: 'tmp' }
  return { entries: [], source: 'none' }
}

async function writeEntries(entries: WaitlistEntry[], source: StorageSource): Promise<boolean> {
  // Preferred backend first (the one that served the read)
  if (source === 'kv-rest' && (await kvWrite(entries))) return true
  if (source === 'redis-rest' && (await redisRestWrite(entries))) return true
  if (source === 'redis-proto' && (await redisProtoWrite(entries))) return true

  // If nothing was readable (first ever entry), try durable backends in order
  if (source === 'none') {
    if (KV_URL && KV_TOKEN && (await kvWrite(entries))) return true
    if (isRedisRest && (await redisRestWrite(entries))) return true
    if (isRedisProtocol && (await redisProtoWrite(entries))) return true
  }

  // Fallback: filesystem (local dev) then /tmp (serverless, ephemeral)
  const a = await fsWrite(LOCAL_FILE, entries)
  const b = await fsWrite(TMP_FILE, entries)
  return a || b
}

/* ---------- Route handlers ---------- */

export async function POST(request: NextRequest) {
  let body: { email?: unknown; source?: unknown }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ message: 'Invalid request body.' }, { status: 400 })
  }

  const { email, source } = body
  if (!email || typeof email !== 'string') {
    return NextResponse.json({ message: 'Email is required.' }, { status: 400 })
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(email.trim())) {
    return NextResponse.json({ message: 'Please enter a valid email address.' }, { status: 400 })
  }

  const cleanEmail = email.trim().toLowerCase()
  const { entries, source: storageSource } = await readEntries()

  if (entries.some((e) => e.email === cleanEmail)) {
    return NextResponse.json(
      {
        message: 'You\u2019re already on the waitlist \u2014 we\u2019ll be in touch.',
        alreadyJoined: true,
      },
      { status: 200 }
    )
  }

  entries.push({
    email: cleanEmail,
    source: typeof source === 'string' ? source : 'unknown',
    timestamp: new Date().toISOString(),
  })

  const persisted = await writeEntries(entries, storageSource)
  if (!persisted) {
    return NextResponse.json(
      { message: 'Waitlist storage is not available right now. Please try again later.' },
      { status: 503 }
    )
  }

  return NextResponse.json(
    {
      message: 'You\u2019re on the list. We\u2019ll be in touch when early access opens.',
      position: entries.length,
      total: entries.length,
    },
    { status: 201 }
  )
}

export async function GET() {
  const { entries } = await readEntries()
  return NextResponse.json({ total: entries.length })
}