import 'server-only'
import { publicSupabaseConfig } from './supabase-config'

export class DealsUnavailable extends Error {}
export class AmbiguousParcel extends Error {}

const NUMERIC_FIELDS = [
  'deal_score', 'asking_price', 'estimated_arv_low', 'estimated_arv_high',
  'estimated_profit_low', 'estimated_profit_high', 'recommended_offer_low',
  'recommended_offer_high', 'valuation_confidence',
] as const
const TEXT_FIELDS = [
  'status', 'verification_status', 'source', 'source_vendor', 'source_quality',
  'data_freshness', 'valuation_basis', 'updated_at',
] as const
const PROPERTY_FIELDS = ['apn', 'county_id', 'address', 'zoning'] as const
const PROPERTY_NUMBERS = ['lot_size_acres', 'latitude', 'longitude'] as const
const SIGNALS = new Set(['tax_delinquent', 'absentee_owner', 'long_ownership', 'no_improvements', 'vacant_land', 'probate', 'inherited'])
const SELECT = [...NUMERIC_FIELDS, ...TEXT_FIELDS, 'source_url', 'motivation_signals',
  `properties!inner(${[...PROPERTY_FIELDS, ...PROPERTY_NUMBERS].join(',')})`].join(',')

type Row = Record<string, unknown>
const object = (value: unknown): value is Row => !!value && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown) => typeof value === 'string' ? value : null
const number = (value: unknown) => {
  if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function sourceUrl(value: unknown): string | null {
  try {
    const url = new URL(String(value))
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null
  } catch { return null }
}

/** Explicit projection is a second boundary after RLS, never object-spread DB rows. */
export function publicDeal(row: unknown): Row | null {
  if (!object(row) || row.status !== 'discovered' || row.verification_status !== 'verified' || !object(row.properties)) return null
  const property = row.properties
  if (!text(property.apn) || !text(property.county_id)) return null
  const deal: Row = {}
  for (const field of NUMERIC_FIELDS) deal[field] = number(row[field])
  for (const field of TEXT_FIELDS) deal[field] = text(row[field])
  for (const field of PROPERTY_FIELDS) deal[field] = text(property[field])
  for (const field of PROPERTY_NUMBERS) deal[field] = number(property[field])
  deal.source_url = sourceUrl(row.source_url)
  const signals = typeof row.motivation_signals === 'string' ? row.motivation_signals.split(',') : row.motivation_signals
  deal.motivation_signals = Array.isArray(signals) ? [...new Set(signals.filter((s): s is string => typeof s === 'string' && SIGNALS.has(s)))] : []
  return deal
}

export async function supabaseRead(table: string, params: URLSearchParams): Promise<unknown[]> {
  const config = publicSupabaseConfig()
  if (!config) throw new DealsUnavailable('Database not configured')
  try {
    const response = await fetch(`${config.url}/rest/v1/${table}?${params}`, {
      headers: { apikey: config.key, Authorization: `Bearer ${config.key}` },
      cache: 'no-store', signal: AbortSignal.timeout(8000), redirect: 'error',
    })
    if (!response.ok) throw new DealsUnavailable('Database unavailable')
    const rows: unknown = await response.json()
    if (!Array.isArray(rows)) throw new DealsUnavailable('Invalid database response')
    return rows
  } catch {
    // Do not log response bodies, credentials, or source records.
    throw new DealsUnavailable('Database unavailable')
  }
}

export async function readPublishedDeals({ limit = 25, offset = 0, apn, countyId }: {
  limit?: number; offset?: number; apn?: string; countyId?: string
} = {}): Promise<Row[]> {
  const params = new URLSearchParams({
    status: 'eq.discovered', verification_status: 'eq.verified', select: SELECT,
    order: 'deal_score.desc,id.asc', limit: String(limit), offset: String(offset),
  })
  // Quote PostgREST filter values so punctuation in real APNs remains literal.
  const literal = (value: string) => `eq."${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
  if (apn) params.set('properties.apn', literal(apn))
  if (countyId) params.set('properties.county_id', literal(countyId))
  const rows = await supabaseRead('deals', params)
  return rows.map(publicDeal).filter((deal): deal is Row => deal !== null)
}

export async function readPublishedDeal(apn: string, countyId?: string): Promise<Row | null> {
  const rows = await readPublishedDeals({ apn, countyId, limit: 2 })
  if (rows.length > 1) throw new AmbiguousParcel('Specify county_id to identify this parcel')
  return rows[0] ?? null
}
