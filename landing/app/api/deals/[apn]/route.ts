import { NextRequest, NextResponse } from 'next/server'
import { AmbiguousParcel, readPublishedDeal } from '@/lib/public-deals'

export const dynamic = 'force-dynamic'
const headers = { 'Cache-Control': 'no-store' }

export async function GET(request: NextRequest, { params }: { params: Promise<{ apn: string }> }) {
  // Next already decodes route parameters. Decoding again breaks literal % APNs.
  const { apn } = await params
  const countyId = request.nextUrl.searchParams.get('county_id') || undefined
  if (!apn.trim() || apn.length > 200 || /[\u0000-\u001f\u007f]/.test(apn) || (countyId && !/^[a-zA-Z0-9_-]{1,150}$/.test(countyId))) {
    return NextResponse.json({ error: 'Invalid parcel identity' }, { status: 400, headers })
  }
  try {
    const deal = await readPublishedDeal(apn, countyId)
    if (!deal) return NextResponse.json({ error: 'Deal not found', meta: { status: 'no-data', apn } }, { status: 404, headers })
    return NextResponse.json({ deal, meta: { apn } }, { headers })
  } catch (error) {
    if (error instanceof AmbiguousParcel) return NextResponse.json({ error: error.message }, { status: 409, headers })
    return NextResponse.json({ error: 'Verified deals are temporarily unavailable' }, { status: 503, headers })
  }
}
