import { NextResponse } from 'next/server'
import { currentUser } from '@/lib/supabase-server'
import { supabaseRead } from '@/lib/public-deals'

export const dynamic = 'force-dynamic'
const headers = { 'Cache-Control': 'private, no-store' }

export async function GET() {
  const user = await currentUser()
  if (!user) return NextResponse.json({ error: 'Authentication required' }, { status: 401, headers })
  // app_metadata is server-managed; never trust the user's editable metadata.
  if (user.app_metadata?.role !== 'admin') return NextResponse.json({ error: 'Administrator access required' }, { status: 403, headers })
  try {
    const rows: Record<string, unknown>[] = []
    for (let offset = 0; offset < 6000; offset += 1000) {
      const batch = await supabaseRead('counties', new URLSearchParams({
        select: 'county_id,county_name,state,coverage_status,verification_status,validation_status,record_count,persisted_count,published_count,last_successful_run,data_freshness,last_run_status',
        order: 'county_id.asc', limit: '1000', offset: String(offset),
      }))
      rows.push(...batch as Record<string, unknown>[])
      if (batch.length < 1000) break
    }
    const counties = rows.map(county => {
      const failed = county.validation_status === 'invalid' || county.validation_status === 'unreachable' || county.last_run_status === 'error'
      const persisted = Number(county.persisted_count) || 0
      const status = failed ? 'failed' : persisted > 0 && county.last_run_status === 'ok' ? 'active' : county.validation_status === 'valid' ? 'degraded' : 'not_implemented'
      return {
        county_id: county.county_id, county_name: county.county_name, state: county.state,
        tier: county.coverage_status, tier_name: county.coverage_status, status,
        records: persisted, published: Number(county.published_count) || 0,
        last_run: county.last_successful_run, data_freshness: county.data_freshness,
        validation_status: county.validation_status, verification_status: county.verification_status,
        registry_coverage_status: county.coverage_status,
      }
    })
    const summary = {
      total_counties: counties.length, total: counties.length,
      active: counties.filter(c => c.status === 'active').length,
      degraded: counties.filter(c => c.status === 'degraded').length,
      failed: counties.filter(c => c.status === 'failed').length,
      not_implemented: counties.filter(c => c.status === 'not_implemented').length, skipped: 0,
    }
    return NextResponse.json({ coverage_summary: summary, counties, generated_at: new Date().toISOString(), scope: 'persisted_counties' }, { headers })
  } catch {
    return NextResponse.json({ error: 'Coverage data is temporarily unavailable' }, { status: 503, headers })
  }
}
