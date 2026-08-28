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
 *  1. Vercel KV (Upstash REST) — durable, production. Used when
 *     KV_REST_API_URL + KV_REST_API_TOKEN are present (set by linking a DB).
 *  2. Local file in `data/` — works in local `next dev` (writable FS).
 *  3. /tmp file — last resort for read-only serverless runtimes
 *     (Vercel without KV): writable, but ephemeral per instance.
 *
 * Never throws a bare 500: if every backend is unavailable we return a
 * clear, graceful 503 instead of an opaque "Internal server error".
 */
const KV_URL = process.env.KV_REST_API_URL || ''
const KV_TOKEN = process.env.KV_REST_API_TOKEN || ''
const KV_KEY = 'dealscan:waitlist'

const LOCAL_FILE = path.join(process.cwd(), 'data', 'waitlist.json')
const TMP_FILE = '/tmp/dealscan-waitlist.json'

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

async function readEntries(): Promise<{ entries: WaitlistEntry[]; source: string }> {
  if (KV_URL && KV_TOKEN) {
    const kv = await kvRead()
    if (kv) return { entries: kv, source: 'kv' }
  }
  const local = await fsRead(LOCAL_FILE)
  if (local) return { entries: local, source: 'local' }
  const tmp = await fsRead(TMP_FILE)
  if (tmp) return { entries: tmp, source: 'tmp' }
  return { entries: [], source: 'none' }
}

async function writeEntries(entries: WaitlistEntry[], source: string): Promise<boolean> {
  if (source === 'kv') {
    const ok = await kvWrite(entries)
    if (ok) return true
    // KV write failed — fall through to filesystem
  }
  if (source === 'local' || source === 'tmp' || source === 'none') {
    // Prefer local when writable (dev), else /tmp (serverless)
    const a = await fsWrite(LOCAL_FILE, entries)
    const b = await fsWrite(TMP_FILE, entries)
    return a || b
  }
  return false
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