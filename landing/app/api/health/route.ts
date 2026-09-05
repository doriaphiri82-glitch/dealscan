import { NextResponse } from 'next/server'
import { publicSupabaseConfig } from '@/lib/supabase-config'
import { supabaseRead } from '@/lib/public-deals'

export const dynamic = 'force-dynamic'
const headers = { 'Cache-Control': 'no-store, max-age=0' }

export async function GET() {
  const config=publicSupabaseConfig()
  if (!config) {
    return NextResponse.json({ status: 'degraded', service: 'dealscan-web', database: 'not-configured' }, { status: 503, headers })
  }
  try {
    // Probe the same RLS-protected read path as the application, not a static URL.
    await supabaseRead('deals', new URLSearchParams({ select: 'id', status: 'eq.discovered', verification_status: 'eq.verified', limit: '1' }))
    return NextResponse.json({ status: 'ok', service: 'dealscan-web', database: 'ok', database_origin:config.url }, { headers })
  } catch {
    return NextResponse.json({ status: 'degraded', service: 'dealscan-web', database: 'unavailable' }, { status: 503, headers })
  }
}
