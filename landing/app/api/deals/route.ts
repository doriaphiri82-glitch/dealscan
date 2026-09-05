import { NextRequest, NextResponse } from 'next/server'
import { readPublishedDeals } from '@/lib/public-deals'

export const dynamic = 'force-dynamic'
const headers = { 'Cache-Control': 'no-store' }

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams
  const rawLimit = query.get('limit') ?? '25'
  const rawOffset = query.get('offset') ?? '0'
  if (!/^\d+$/.test(rawLimit) || !/^\d+$/.test(rawOffset) || Number(rawOffset) > 5000) {
    return NextResponse.json({ error: 'Invalid pagination' }, { status: 400, headers })
  }
  const limit = Math.max(1, Math.min(50, Number(rawLimit)))
  const offset = Number(rawOffset)
  const countyId = query.get('county_id') || undefined
  if (countyId && !/^[a-zA-Z0-9_-]{1,150}$/.test(countyId)) return NextResponse.json({ error: 'Invalid county_id' }, { status: 400, headers })
  try {
    const deals = await readPublishedDeals({ limit, offset, countyId })
    return NextResponse.json({
      count: deals.length, deals, generated_at: null,
      meta: { status: deals.length ? 'ok' : 'no-data', storage_source: 'supabase', scraped_counties: [], offset, limit },
    }, { headers })
  } catch {
    return NextResponse.json({
      error: 'Verified deals are temporarily unavailable', count: 0, deals: [], generated_at: null,
      meta: { status: 'unavailable', storage_source: 'supabase', scraped_counties: [] },
    }, { status: 503, headers })
  }
}
