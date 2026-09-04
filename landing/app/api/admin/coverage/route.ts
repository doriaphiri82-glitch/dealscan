import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

type RegistryCounty = Record<string, any>
type RegistryDocument = { counties?: Record<string, RegistryCounty> }

function statusForCounty(county: RegistryCounty) {
  const verification = String(county.verification_status || '').toLowerCase()
  const validation = String(county.validation_status || '').toLowerCase()
  const stored = Number(county.last_record_count || 0)

  if (verification === 'verified' && stored > 0) return 'active'
  if (validation === 'invalid' || validation === 'unreachable') return 'failed'
  if (verification === 'source_verified' && stored > 0) return 'degraded'
  return 'not_implemented'
}

function readRegistry(): RegistryDocument {
  const candidates = [
    path.join(process.cwd(), 'data', 'registry.json'),
    path.join(process.cwd(), '..', 'pipeline', 'config', 'counties', 'registry.json'),
  ]
  for (const registryPath of candidates) {
    try {
      const raw = fs.readFileSync(registryPath, 'utf-8')
      const parsed = JSON.parse(raw) as RegistryDocument
      if (parsed && parsed.counties && typeof parsed.counties === 'object') return parsed
    } catch {
      // Try the next deployment-safe registry location.
    }
  }
  throw new Error('No county coverage registry is available')
}

export async function GET() {
  try {
    const registry = readRegistry()
    const source: Record<string, RegistryCounty> = registry.counties || {}

    const counties = Object.entries(source).map(([id, county]) => {
      const records = Number(county.last_record_count || 0)
      const published = Number(county.last_published_count || 0)
      return {
        county_id: id,
        county_name: county.county_name || id,
        state: county.state || '',
        tier: county.coverage_status || null,
        tier_name: county.coverage_status || null,
        status: statusForCounty(county),
        records,
        published,
        last_run: county.last_successful_run || null,
        data_freshness: county.data_freshness || null,
        validation_status: county.validation_status || null,
        verification_status: county.verification_status || null,
        registry_coverage_status: county.coverage_status || null,
        rejection_reasons: county.rejection_reasons || {},
      }
    })

    const summary = {
      total_counties: counties.length,
      total: counties.length,
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