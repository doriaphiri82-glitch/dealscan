import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, '')
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!url || !key) {
    return NextResponse.json({ status: 'degraded', service: 'dealscan-web', database: 'not-configured' }, { status: 503 })
  }

  try {
    const response = await fetch(`${url}/rest/v1/counties?select=county_id&limit=1`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
      cache: 'no-store',
    })
    if (!response.ok) {
      return NextResponse.json({ status: 'degraded', service: 'dealscan-web', database: 'unavailable' }, { status: 503 })
    }
    return NextResponse.json({ status: 'ok', service: 'dealscan-web', database: 'ok' }, { status: 200 })
  } catch {
    return NextResponse.json({ status: 'degraded', service: 'dealscan-web', database: 'unavailable' }, { status: 503 })
  }
}
