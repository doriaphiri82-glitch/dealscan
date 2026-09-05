import 'server-only'
import { publicSupabaseConfig } from './supabase-config'
import { currentVerification, supportedFinancialFacts, sourceReference } from './verified-facts'

export class DealsUnavailable extends Error {}
export class AmbiguousParcel extends Error {}

const NUMERIC_FIELDS = [
  'deal_score', 'asking_price', 'estimated_costs', 'estimated_arv_low', 'estimated_arv_high',
  'estimated_profit_low', 'estimated_profit_high', 'recommended_offer_low',
  'recommended_offer_high', 'valuation_confidence',
] as const
const TEXT_FIELDS = [
  'status', 'verification_status', 'asking_price_basis', 'source', 'source_vendor', 'source_quality',
  'data_freshness', 'valuation_basis', 'valuation_model', 'updated_at', 'verified_at', 'verification_expires_at',
] as const
const PROPERTY_FIELDS = ['apn', 'county_id', 'address', 'zoning', 'source_record_id'] as const
const PROPERTY_NUMBERS = ['lot_size_acres', 'latitude', 'longitude'] as const
const SIGNALS = new Set(['tax_delinquent', 'absentee_owner', 'long_ownership', 'no_improvements', 'vacant_land', 'probate', 'inherited'])
const SELECT = [...NUMERIC_FIELDS, ...TEXT_FIELDS, 'source_url', 'motivation_signals',
  `properties!inner(${[...PROPERTY_FIELDS, ...PROPERTY_NUMBERS].join(',')})`].join(',')

const COMP_NUMBERS = ['sale_price','lot_size_acres','price_per_acre','distance_miles'] as const
const COMP_TEXT = ['address','source_apn','county_id','source_record_id','sale_date'] as const
const COMP_SELECT = [...COMP_NUMBERS,...COMP_TEXT,'source_url','sale_qualified','vacant_at_sale'].join(',')

type Row = Record<string, unknown>
const object = (value: unknown): value is Row => !!value && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown) => typeof value === 'string' ? value : null
const number = (value: unknown) => {
  if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return null
  if (typeof value==='string' && !/^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:e[+-]?[0-9]+)?$/i.test(value.trim())) return null
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
export function publicDeal(row: unknown, withComps = false): Row | null {
  if (!object(row) || row.status !== 'discovered' || row.verification_status !== 'verified' || !object(row.properties)) return null
  if (!currentVerification(row)) return null
  const property = row.properties
  if (!text(property.apn) || !text(property.county_id)) return null
  const deal: Row = {}
  for (const field of NUMERIC_FIELDS) deal[field] = number(row[field])
  for (const field of TEXT_FIELDS) deal[field] = text(row[field])
  for (const field of PROPERTY_FIELDS) deal[field] = text(property[field])
  for (const field of PROPERTY_NUMBERS) deal[field] = number(property[field])
  deal.source_url = sourceUrl(row.source_url)
  if (!sourceReference(deal) || !supportedFinancialFacts(deal)) throw new DealsUnavailable('Verified record lacks source-backed financial facts')
  if (withComps) {
    if (!Array.isArray(row.comps)) throw new DealsUnavailable('Comparable evidence unavailable')
    const comps = row.comps.map(publicComp).filter((comp): comp is Row => comp !== null)
    const identities = new Set(comps.map(comp=>JSON.stringify([comp.source_url,comp.source_record_id])))
    const parcels = new Set(comps.map(comp=>JSON.stringify([comp.county_id,comp.source_apn])))
    if (comps.length < 3 || comps.length>100 || comps.length !== row.comps.length || identities.size!==comps.length || parcels.size!==comps.length
      || comps.some(comp=>comp.county_id!==deal.county_id || comp.source_apn===deal.apn || Number(comp.lot_size_acres)<Number(deal.lot_size_acres)*.25 || Number(comp.lot_size_acres)>Number(deal.lot_size_acres)*4)) throw new DealsUnavailable('Comparable evidence unavailable')
    const perAcre=comps.map(comp=>Number(comp.sale_price)/Number(comp.lot_size_acres)).sort((a,b)=>a-b)
    const midpoint=Math.floor(perAcre.length/2)
    const median=perAcre.length%2 ? perAcre[midpoint] : (perAcre[midpoint-1]+perAcre[midpoint])/2
    if (Math.abs(Math.round(median*Number(deal.lot_size_acres)*100)/100-Number(deal.estimated_arv_high))>.011
      || Math.abs(Number(deal.valuation_confidence)-Math.min(.9,.6+comps.length*.05))>.001) throw new DealsUnavailable('Comparable calculations do not match the assessment')
    deal.comps = comps
  }
  const signals = typeof row.motivation_signals === 'string' ? row.motivation_signals.split(',') : row.motivation_signals
  deal.motivation_signals = Array.isArray(signals) ? [...new Set(signals.filter((s): s is string => typeof s === 'string' && SIGNALS.has(s)))] : []
  return deal
}

function publicComp(value: unknown): Row | null {
  if (!object(value) || value.sale_qualified !== true || value.vacant_at_sale !== true || !sourceUrl(value.source_url)) return null
  const sale = Date.parse(String(value.sale_date ?? ''))
  if (!Number.isFinite(sale) || sale > Date.now() || sale < Date.now()-1095*86400000) return null
  if (!text(value.source_apn) || !text(value.county_id) || !text(value.source_record_id)) return null
  const row: Row = { source_url:sourceUrl(value.source_url) }
  for (const key of COMP_TEXT) row[key] = text(value[key])
  for (const key of COMP_NUMBERS) row[key] = number(value[key])
  if (!(Number(row.sale_price)>0) || !(Number(row.lot_size_acres)>0) || row.distance_miles == null || Number(row.distance_miles)<0 || Number(row.distance_miles)>10) return null
  if (row.price_per_acre==null || Math.abs(Number(row.price_per_acre)-Number(row.sale_price)/Number(row.lot_size_acres))>.011) return null
  return row
}

export async function supabaseRead(table: string, params: URLSearchParams): Promise<unknown[]> {
  const config = publicSupabaseConfig()
  if (!config) throw new DealsUnavailable('Database not configured')
  try {
    const response = await fetch(`${config.url}/rest/v1/${table}?${params}`, {
      headers: config.key.startsWith('sb_publishable_') ? { apikey: config.key } : { apikey: config.key, Authorization: `Bearer ${config.key}` },
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

export async function readPublishedDeals({ limit = 25, offset = 0, apn, countyId, withComps = false }: {
  limit?: number; offset?: number; apn?: string; countyId?: string; withComps?: boolean
} = {}): Promise<Row[]> {
  const params = new URLSearchParams({
    status: 'eq.discovered', verification_status: 'eq.verified', verification_expires_at: `gt.${new Date().toISOString()}`, select: withComps ? `${SELECT},comps(${COMP_SELECT})` : SELECT,
    order: 'deal_score.desc,id.asc', limit: String(limit), offset: String(offset),
  })
  // Quote PostgREST filter values so punctuation in real APNs remains literal.
  const literal = (value: string) => `eq."${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
  if (apn) params.set('properties.apn', literal(apn))
  if (countyId) params.set('properties.county_id', literal(countyId))
  const rows = await supabaseRead('deals', params)
  const deals=rows.map(row => publicDeal(row,withComps)).filter((deal): deal is Row => deal !== null)
  if (deals.some(deal=>(apn!==undefined&&deal.apn!==apn)||(countyId!==undefined&&deal.county_id!==countyId))
    || new Set(deals.map(deal=>JSON.stringify([deal.county_id,deal.apn]))).size!==deals.length) throw new DealsUnavailable('Unexpected parcel response')
  return deals
}

export async function readPublishedDeal(apn: string, countyId?: string): Promise<Row | null> {
  const rows = await readPublishedDeals({ apn, countyId, limit: 2, withComps:true })
  if (rows.length > 1) throw new AmbiguousParcel('Specify county_id to identify this parcel')
  return rows[0] ?? null
}
