import 'server-only'
import { createHash } from 'node:crypto'

type Row = Record<string, unknown>
const object = (value: unknown): Row => value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {}
const numeric = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : 0
const text = (value: unknown) => typeof value === 'string' ? value : null
const url = (value: unknown) => (text(value) || '').replace(/\/+$/, '')

// Mirrors pipeline.validation.gates.source_fingerprint for the persisted source
// configuration. Stable ordering and ASCII JSON encoding match Python's contract.
const stable = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${stable(key)}:${stable((value as Row)[key])}`).join(',')}}`
  return JSON.stringify(value ?? null).replace(/[\u007f-\uffff]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4,'0')}`)
}
const fieldName = (value: unknown) => (value == null ? 'none' : String(value)).toLowerCase().replace(/ß/g,'ss').replace(/ς/g,'σ')
export function countyFingerprint(county: Row): string {
  const source = { ...object(county.extra), ...county }
  const identity: Row = {}
  for (const key of ['where','acreage_units','vacancy_codebook_url','vacant_use_codes','authority_reviewed','authority_evidence_url','authority_source_url','source_county_geoid']) identity[key] = source[key] ?? null
  identity.url = url(source.arcgis_layer_url || source.data_url || source.parcel_source_url)
  identity.where = source.where || '1=1'
  identity.fields = Object.fromEntries(Object.entries(object(source.field_mapping)).map(([key,value]) => [key,Array.isArray(value) ? value.map(fieldName) : fieldName(value)]))
  return createHash('sha256').update(stable(identity)).digest('hex')
}

export function countyHealth(snapshot: unknown, now = Date.now()) {
  const metrics = object(snapshot), stored = object(metrics.county)
  if (typeof stored.county_id !== 'string') throw new Error('Invalid county snapshot')
  const county = { ...object(stored.extra), ...stored }
  const sourceUrl = url(county.arcgis_layer_url || county.data_url || county.parcel_source_url)
  const validatedAt = Date.parse(String(county.last_validated_at ?? ''))
  const current = county.validation_status === 'valid' && Number.isFinite(validatedAt)
    && validatedAt >= now - 7*86400000 && validatedAt <= now + 300000
    && county.validation_source_fields_checked === true && county.validation_pagination_checked === true
    && numeric(county.validation_sample_checked) > 0 && county.validated_source_fingerprint === countyFingerprint(stored)
  let authority = false
  try {
    const evidence = new URL(String(county.authority_evidence_url))
    const source = new URL(sourceUrl)
    authority = county.authority_reviewed === true && evidence.protocol === 'https:' && source.protocol === 'https:'
      && !source.username && !source.password && url(county.authority_source_url) === sourceUrl
      && !!county.geoid && county.source_county_geoid === county.geoid
  } catch { /* unknown authority is not authorization */ }
  const ready = current && authority && county.ingestion_authorized === true
    && county.authorized_source_fingerprint === county.validated_source_fingerprint
  const unavailable = county.validation_status === 'invalid' || county.validation_status === 'unreachable'
  const stage = unavailable ? 'unavailable' : county.validation_status === 'validating' ? 'validating'
    : ready ? 'ingestion_ready' : current ? 'live_validated' : county.validation_status === 'valid' ? 'validation_expired'
    : sourceUrl ? 'discovered' : 'not_researched'
  const failed = ['error','failed'].includes(String(county.last_run_status))
  const partial = ['degraded','partial'].includes(String(county.last_run_status))
  const ingested = county.ingestion_status === 'ingested' && numeric(county.persisted_count) > 0
  const status = failed || unavailable ? 'failed' : partial || (!ready && numeric(metrics.stored_total)>0) ? 'degraded'
    : ready && ingested ? 'active' : county.last_run_status === 'skipped' ? 'skipped' : 'not_implemented'
  const published = numeric(metrics.verified_total), records = numeric(metrics.stored_total)
  const tier = published > 0 ? 'tier_6' : records > 0 ? 'tier_4' : ready ? 'tier_3' : current ? 'tier_2' : sourceUrl ? 'tier_1' : 'tier_0'
  const labels: Record<string,string> = { tier_0:'Not researched',tier_1:'Source discovered',tier_2:'Live validated',tier_3:'Authorized for ingestion',tier_4:'Source properties stored',tier_6:'Verified opportunities published' }
  return {
    county_id: county.county_id, county_name: text(county.county_name), state: text(county.state),
    source_stage: stage, live_validated: current, ingestion_ready: ready, ingested,
    status, tier, tier_name: labels[tier], records, published,
    last_batch_seen: numeric(county.record_count), last_batch_stored: numeric(county.persisted_count),
    last_batch_qualified: numeric(county.qualified_count),
    last_run: text(county.last_run_at), last_successful_run: text(county.last_successful_run),
    data_freshness: text(county.data_freshness), last_validated_at: text(county.last_validated_at),
    validation_status: text(county.validation_status), verification_status: text(county.verification_status),
    registry_coverage_status: text(county.coverage_status),
  }
}
