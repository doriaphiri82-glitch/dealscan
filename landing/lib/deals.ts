export interface DealAIAnalysis {
  verdict: 'strong_buy' | 'buy' | 'watch' | 'avoid'
  summary: string
  why_it_stands_out: string[]
  risks: string[]
  next_steps: string[]
  risk_level: 'low' | 'medium' | 'high'
  confidence: number
}

export interface Deal {
  apn: string
  address: string
  county_id: string
  county_name?: string
  lot_size_acres: number | null
  asking_price: number | null
  deal_score: number
  estimated_arv_low: number | null
  estimated_arv_high: number | null
  estimated_profit_low: number | null
  estimated_profit_high: number | null
  recommended_offer_low?: number | null
  recommended_offer_high?: number | null
  motivation_signals?: string[]
  market_velocity?: number | null
  competition_level?: string
  owner_state?: string | null
  zoning?: string | null
  tax_delinquent_years?: number | null
  valuation_basis?: string | null
  valuation_confidence?: number | null
  source?: string
  source_url?: string | null
  source_vendor?: string | null
  source_quality?: string | null
  verification_status?: string | null
  data_freshness?: string | null
  ai_analysis?: DealAIAnalysis
}

export interface DealsResponse {
  count: number
  deals: Deal[]
  generated_at: string | null
  meta?: {
    status: string
    scraped_counties: string[]
    storage_source?: string
  }
}

const FALLBACK_DEALS: DealsResponse = {
  count: 0,
  deals: [],
  generated_at: null,
  meta: { status: 'no-data', scraped_counties: [] },
}

/** Fetch published pipeline deals. Never substitutes fabricated inventory. */
export async function fetchTopDeals(limit = 25): Promise<DealsResponse> {
  try {
    const res = await fetch(`/api/deals?limit=${limit}`, { headers: { Accept: 'application/json' } })
    if (!res.ok) return FALLBACK_DEALS
    const data = (await res.json()) as DealsResponse
    return { ...FALLBACK_DEALS, ...data }
  } catch {
    return FALLBACK_DEALS
  }
}

export async function fetchDealByApn(apn: string): Promise<{ deal: Deal } | null> {
  try {
    const res = await fetch(`/api/deals/${encodeURIComponent(apn)}`, { headers: { Accept: 'application/json' } })
    if (!res.ok) return null
    const data = (await res.json()) as { deal: Deal }
    return data.deal ? data : null
  } catch {
    return null
  }
}
