import { NextResponse } from 'next/server'
import { currentUser } from '@/lib/supabase-server'
import { privateRpc } from '@/lib/supabase-private'
import { countyHealth } from '@/lib/county-health'

export const dynamic = 'force-dynamic'
const headers = { 'Cache-Control': 'private, no-store' }

export async function GET() {
  const user = await currentUser()
  if (!user) return NextResponse.json({ error: 'Authentication required' }, { status: 401, headers })
  if (user.app_metadata?.role !== 'admin') return NextResponse.json({ error: 'Administrator access required' }, { status: 403, headers })
  try {
    const counties: ReturnType<typeof countyHealth>[] = []
    const identities=new Set<string>()
    const checkedAt=Date.now()
    for (let offset = 0; ; offset += 1000) {
      if (offset >= 6000) throw new Error('Registry exceeds bounded snapshot limit')
      const batch = await privateRpc('county_operational_snapshot', { p_limit: 1000, p_offset: offset })
      if (!Array.isArray(batch) || batch.length>1000) throw new Error('Invalid snapshot')
      for(const row of batch){
        const county=countyHealth(row,checkedAt)
        if(identities.has(county.county_id))throw new Error('Duplicate county snapshot')
        identities.add(county.county_id)
        counties.push(county)
      }
      if (batch.length < 1000) break
    }
    const summary = {
      total_counties: counties.length, total: counties.length,
      active: counties.filter(c => c.status === 'active').length,
      degraded: counties.filter(c => c.status === 'degraded').length,
      failed: counties.filter(c => c.status === 'failed').length,
      not_implemented: counties.filter(c => c.status === 'not_implemented').length,
      skipped: counties.filter(c => c.status === 'skipped').length,
      discovered: counties.filter(c => c.source_stage !== 'not_researched').length,
      live_validated: counties.filter(c => c.live_validated).length,
      ingestion_ready: counties.filter(c => c.ingestion_ready).length,
      ingested: counties.filter(c => c.ingested).length,
      verified_opportunities: counties.reduce((sum,c) => sum+c.published,0),
    }
    return NextResponse.json({ coverage_summary: summary, counties, generated_at: new Date().toISOString(),
      scope: 'persisted_counties', note: 'County geography is not national live parcel coverage. Source freshness is not ingestion time.' }, { headers })
  } catch {
    return NextResponse.json({ error: 'Coverage data is temporarily unavailable' }, { status: 503, headers })
  }
}
