/** Browser-facing verified opportunity contract. Unknown facts remain null. */
export interface Comp {
  address?: string | null
  source_apn: string
  county_id: string
  source_url: string
  source_record_id: string
  sale_price: number
  sale_date: string
  distance_miles: number
  lot_size_acres: number
  price_per_acre: number
}
export interface Deal {
  apn: string
  county_id: string
  address?: string | null
  lot_size_acres?: number | null
  asking_price?: number | null
  estimated_costs?: number | null
  deal_score?: number | null
  estimated_arv_low?: number | null
  estimated_arv_high?: number | null
  estimated_profit_low?: number | null
  estimated_profit_high?: number | null
  recommended_offer_low?: number | null
  recommended_offer_high?: number | null
  valuation_basis?: string | null
  valuation_model?: string | null
  valuation_confidence?: number | null
  source_url?: string | null
  source_quality?: string | null
  source_record_id?: string | null
  verification_status: 'verified'
  verified_at: string
  verification_expires_at: string
  data_freshness?: string | null
  motivation_signals?: string[]
  zoning?: string | null
  latitude?: number | null
  longitude?: number | null
  comps?: Comp[]
}
export interface DealsResponse {
  count: number
  deals: Deal[]
  generated_at: string | null
  meta: { status: string; storage_source: string; offset?: number; limit?: number; has_more?: boolean; scraped_counties?: string[] }
}
export class FeedUnavailable extends Error {}
export class ParcelAmbiguous extends Error {}

export function currentDeal(value: unknown): value is Deal {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const row = value as Deal
  return typeof row.apn === 'string' && !!row.apn && typeof row.county_id === 'string' && !!row.county_id
    && row.verification_status === 'verified' && Number.isFinite(Date.parse(row.verified_at))
    && Date.parse(row.verified_at) <= Date.now()+300000 && Date.parse(row.verification_expires_at)>Date.now()
}

/** Outages are errors, not a fabricated empty dataset or an old cached feed. */
export async function fetchTopDeals(limit = 25, offset = 0): Promise<DealsResponse> {
  try {
    const res = await fetch(`/api/deals?limit=${encodeURIComponent(limit)}&offset=${encodeURIComponent(offset)}`, {
      headers: { Accept: 'application/json' }, cache:'no-store', signal:AbortSignal.timeout(12000),
    })
    if (!res.ok) throw new Error()
    const data = await res.json() as DealsResponse
    if (!Array.isArray(data.deals) || data.meta?.storage_source !== 'supabase' || !data.deals.every(currentDeal)) throw new Error()
    return data
  } catch { throw new FeedUnavailable('The verified feed is unavailable. Please try again.') }
}

export async function fetchDealByApn(apn: string, countyId?: string): Promise<{ deal: Deal } | null> {
  try {
    const query = countyId ? `?county_id=${encodeURIComponent(countyId)}` : ''
    const res = await fetch(`/api/deals/${encodeURIComponent(apn)}${query}`, {
      headers:{ Accept:'application/json' },cache:'no-store',signal:AbortSignal.timeout(12000),
    })
    if (res.status === 404) return null
    if (res.status === 409) throw new ParcelAmbiguous('This APN exists in more than one county. Select the county in Explorer.')
    if (!res.ok) throw new Error()
    const data = await res.json() as { deal: Deal }
    if (!currentDeal(data.deal)) throw new Error()
    return data
  } catch (error) {
    if (error instanceof ParcelAmbiguous) throw error
    throw new FeedUnavailable('This parcel could not be checked against the current verified feed.')
  }
}
