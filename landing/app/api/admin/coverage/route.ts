import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export async function GET() {
  try {
    const registryPath = path.join(process.cwd(), 'data', 'registry.json')
    const raw = fs.readFileSync(registryPath, 'utf-8')
    const registry = JSON.parse(raw)

    const counties = Object.entries(registry.counties || {}).map(
      ([id, county]: [string, any]) => ({
        county_id: id,
        county_name: county.county_name || id,
        state: county.state || '',
        tier: county.tier ?? null,
        tier_name: county.tier_name || null,
        status: county.status || 'unknown',
        records: county.records ?? 0,
        published: county.published ?? 0,
        last_run: county.last_run || null,
        rejection_reasons: county.rejection_reasons || {},
      })
    )

    const summary = {
      total_counties: counties.length,
      active: counties.filter((c) => c.status === 'active').length,
      degraded: counties.filter((c) => c.status === 'degraded').length,
      failed: counties.filter((c) => c.status === 'failed').length,
      not_implemented: counties.filter((c) => c.status === 'not_implemented').length,
      skipped: counties.filter((c) => c.status === 'skipped').length,
    }

    return NextResponse.json({
      coverage_summary: summary,
      counties,
      generated_at: new Date().toISOString(),
    })
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to load coverage data', details: String(error) },
      { status: 500 }
    )
  }
}