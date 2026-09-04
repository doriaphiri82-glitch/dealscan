/*
 * Empty committed fallback. Live inventory must come from the pipeline's
 * Redis/KV publication. Keeping this empty prevents fictional parcels,
 * prices, valuations, or AI outputs from being presented as real deals.
 */

export interface DealRecord {
  apn: string
  address: string
  county_id: string
  lot_size_acres: number | null
  asking_price: number | null
  deal_score: number
  estimated_arv_low?: number | null
  estimated_arv_high?: number | null
  estimated_profit_low?: number | null
  estimated_profit_high?: number | null
  motivation_signals?: string[]
  market_velocity?: number | null
  competition_level?: string
  owner_state?: string | null
  zoning?: string | null
  tax_delinquent_years?: number | null
  source?: string
  verification_status?: string
  data_freshness?: string | null
}

export interface DealsBundle {
  generated_at: string | null
  count: number
  deals: DealRecord[]
  error?: string
  meta: { status: string; scraped_counties: string[] }
}

export const SEED_BUNDLE: DealsBundle = {
  generated_at: null,
  count: 0,
  deals: [],
  error: '',
  meta: { scraped_counties: [], status: 'no-live-data' },
}

export const SEED_REGISTRY: { apn: string; county_id: string }[] = []

export default SEED_BUNDLE
