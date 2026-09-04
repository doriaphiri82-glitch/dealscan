import { NextRequest, NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

interface WaitlistEntry { email: string; source: string; timestamp: string }

const KV_URL = process.env.KV_REST_API_URL || ''
const KV_TOKEN = process.env.KV_REST_API_TOKEN || ''
const REDIS_URL = process.env.REDIS_URL || ''
const KV_KEY = 'dealscan:waitlist'
const LOCAL_FILE = path.join(process.cwd(), 'data', 'waitlist.json')
const TMP_FILE = '/tmp/dealscan-waitlist.json'
const isRedisProtocol = /^rediss?:\/\//.test(REDIS_URL)
const isRedisRest = /^https:\/\//.test(REDIS_URL)

const globalForRedis = globalThis as unknown as { __dealscanRedis?: { client: RedisLike | null } }
type RedisLike = { get: (k: string) => Promise<string | null>; set: (k: string, v: string) => Promise<unknown> }

async function getRedisClient(): Promise<RedisLike | null> {
  if (!isRedisProtocol) return null
  if (globalForRedis.__dealscanRedis?.client) return globalForRedis.__dealscanRedis.client
  try {
    const mod = await import('redis')
    const client = mod.createClient({ url: REDIS_URL })
    await client.connect()
    globalForRedis.__dealscanRedis = { client }
    return client
  } catch { return null }
}

async function redisProtoRead(): Promise<WaitlistEntry[] | null> {
  const client = await getRedisClient(); if (!client) return null
  try { const raw = await client.get(KV_KEY); if (raw == null) return []; const parsed = JSON.parse(raw); return Array.isArray(parsed) ? parsed : [] } catch { return null }
}
async function redisProtoWrite(entries: WaitlistEntry[]) { const client = await getRedisClient(); if (!client) return false; try { await client.set(KV_KEY, JSON.stringify(entries)); return true } catch { return false } }
async function kvRead(): Promise<WaitlistEntry[] | null> { if (!KV_URL || !KV_TOKEN) return null; try { const res = await fetch(`${KV_URL}/get/${KV_KEY}`, { headers: { Authorization: `Bearer ${KV_TOKEN}` } }); if (!res.ok) return null; const json = await res.json() as { result?: string | null }; if (json.result == null) return []; const parsed = JSON.parse(json.result); return Array.isArray(parsed) ? parsed : [] } catch { return null } }
async function kvWrite(entries: WaitlistEntry[]) { if (!KV_URL || !KV_TOKEN) return false; try { const res = await fetch(`${KV_URL}/set/${KV_KEY}`, { method: 'POST', headers: { Authorization: `Bearer ${KV_TOKEN}`, 'Content-Type': 'application/json' }, body: JSON.stringify(entries) }); return res.ok } catch { return false } }
async function redisRestRead(): Promise<WaitlistEntry[] | null> { if (!isRedisRest) return null; try { const res = await fetch(`${REDIS_URL}/get/${KV_KEY}`); if (!res.ok) return null; const json = await res.json() as { result?: string | null }; if (json.result == null) return []; const parsed = JSON.parse(json.result); return Array.isArray(parsed) ? parsed : [] } catch { return null } }
async function redisRestWrite(entries: WaitlistEntry[]) { if (!isRedisRest) return false; try { const res = await fetch(`${REDIS_URL}/set/${KV_KEY}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(entries) }); return res.ok } catch { return false } }
async function fsRead(file: string): Promise<WaitlistEntry[] | null> { try { const parsed = JSON.parse(await fs.readFile(file, 'utf-8')); return Array.isArray(parsed) ? parsed : [] } catch { return null } }
async function fsWrite(file: string, entries: WaitlistEntry[]) { try { const dir = path.dirname(file); if (dir !== path.dirname(TMP_FILE)) await fs.mkdir(dir, { recursive: true }); await fs.writeFile(file, JSON.stringify(entries, null, 2)); return true } catch { return false } }

type StorageSource = 'kv-rest' | 'redis-rest' | 'redis-proto' | 'local' | 'tmp' | 'none'
async function readEntries(): Promise<{ entries: WaitlistEntry[]; source: StorageSource }> {
  if (KV_URL && KV_TOKEN) { const value = await kvRead(); if (value) return { entries: value, source: 'kv-rest' } }
  if (isRedisRest) { const value = await redisRestRead(); if (value) return { entries: value, source: 'redis-rest' } }
  if (isRedisProtocol) { const value = await redisProtoRead(); if (value) return { entries: value, source: 'redis-proto' } }
  const local = await fsRead(LOCAL_FILE); if (local) return { entries: local, source: 'local' }
  const tmp = await fsRead(TMP_FILE); if (tmp) return { entries: tmp, source: 'tmp' }
  return { entries: [], source: 'none' }
}
async function writeEntries(entries: WaitlistEntry[], source: StorageSource) {
  if (source === 'kv-rest' && await kvWrite(entries)) return true
  if (source === 'redis-rest' && await redisRestWrite(entries)) return true
  if (source === 'redis-proto' && await redisProtoWrite(entries)) return true
  if (source === 'none') {
    if (KV_URL && KV_TOKEN && await kvWrite(entries)) return true
    if (isRedisRest && await redisRestWrite(entries)) return true
    if (isRedisProtocol && await redisProtoWrite(entries)) return true
  }
  return (await fsWrite(LOCAL_FILE, entries)) || (await fsWrite(TMP_FILE, entries))
}

export async function POST(request: NextRequest) {
  let body: { email?: unknown; source?: unknown }
  try { body = await request.json() } catch { return NextResponse.json({ message: 'Invalid request body.' }, { status: 400 }) }
  const { email, source } = body
  if (!email || typeof email !== 'string') return NextResponse.json({ message: 'Email is required.' }, { status: 400 })
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return NextResponse.json({ message: 'Please enter a valid email address.' }, { status: 400 })
  const cleanEmail = email.trim().toLowerCase()
  const { entries, source: storageSource } = await readEntries()
  if (entries.some((entry) => entry.email === cleanEmail)) return NextResponse.json({ message: 'You’re already signed up for DealScan updates.', alreadyJoined: true }, { status: 200 })
  entries.push({ email: cleanEmail, source: typeof source === 'string' ? source : 'unknown', timestamp: new Date().toISOString() })
  if (!(await writeEntries(entries, storageSource))) return NextResponse.json({ message: 'Updates sign-up is not available right now. Please try again later.' }, { status: 503 })
  return NextResponse.json({ message: 'You’re signed up for DealScan updates.', position: entries.length, total: entries.length }, { status: 201 })
}

export async function GET() { const { entries } = await readEntries(); return NextResponse.json({ total: entries.length }) }
