import { NextRequest, NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

const DATA_FILE = path.join(process.cwd(), 'data', 'waitlist.json')

interface WaitlistEntry {
  email: string
  source: string
  timestamp: string
}

async function readWaitlist(): Promise<WaitlistEntry[]> {
  try {
    const data = await fs.readFile(DATA_FILE, 'utf-8')
    return JSON.parse(data)
  } catch {
    return []
  }
}

async function writeWaitlist(entries: WaitlistEntry[]): Promise<void> {
  const dir = path.dirname(DATA_FILE)
  await fs.mkdir(dir, { recursive: true })
  await fs.writeFile(DATA_FILE, JSON.stringify(entries, null, 2))
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { email, source } = body

    // Validate email
    if (!email || typeof email !== 'string') {
      return NextResponse.json({ error: 'Email is required' }, { status: 400 })
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email.trim())) {
      return NextResponse.json({ error: 'Invalid email address' }, { status: 400 })
    }

    const cleanEmail = email.trim().toLowerCase()

    // Read existing entries
    const entries = await readWaitlist()

    // Check for duplicates
    if (entries.some((e) => e.email === cleanEmail)) {
      return NextResponse.json(
        { message: 'Already on the waitlist!', position: entries.findIndex((e) => e.email === cleanEmail) + 1 },
        { status: 200 }
      )
    }

    // Add new entry
    const newEntry: WaitlistEntry = {
      email: cleanEmail,
      source: source || 'unknown',
      timestamp: new Date().toISOString(),
    }

    entries.push(newEntry)
    await writeWaitlist(entries)

    return NextResponse.json({
      message: 'Successfully joined the waitlist!',
      position: entries.length,
      total: entries.length,
    }, { status: 201 })
  } catch (error) {
    console.error('Waitlist error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function GET() {
  try {
    const entries = await readWaitlist()
    return NextResponse.json({ total: entries.length })
  } catch {
    return NextResponse.json({ total: 0 })
  }
}
