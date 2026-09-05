import { currentVerification, supportedFinancialFacts, sourceReference } from './verified-facts'
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
  asking_price_basis?: string | null
  status?: string
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
  const row = value as Record<string,unknown>
  return currentVerification(row) && sourceReference(row) && supportedFinancialFacts(row)
}

interface RequestOptions { signal?: AbortSignal }

async function apiRead(url:string,signal?:AbortSignal):Promise<{status:number;body:unknown}> {
  const controller=new AbortController()
  const abort=()=>controller.abort(signal?.reason)
  if(signal?.aborted)abort()
  else signal?.addEventListener('abort',abort,{once:true})
  const timer=setTimeout(()=>controller.abort(new DOMException('Request timed out','TimeoutError')),12000)
  try {
    if(controller.signal.aborted)throw controller.signal.reason
    const response=await fetch(url,{headers:{Accept:'application/json'},cache:'no-store',signal:controller.signal,redirect:'error'})
    return {status:response.status,body:response.ok?await response.json():null}
  } finally {clearTimeout(timer);signal?.removeEventListener('abort',abort)}
}

/** Outages are errors, not a fabricated empty dataset or an old cached feed. */
export async function fetchTopDeals(limit = 25, offset = 0, options:RequestOptions = {}): Promise<DealsResponse> {
  try {
    if(!Number.isSafeInteger(limit)||limit<1||limit>50||!Number.isSafeInteger(offset)||offset<0||offset>5000)throw new Error()
    const response=await apiRead(`/api/deals?limit=${encodeURIComponent(limit)}&offset=${encodeURIComponent(offset)}`,options.signal)
    if(response.status!==200||!response.body||typeof response.body!=='object')throw new Error()
    const data=response.body as DealsResponse
    if (!Array.isArray(data.deals) || data.meta?.storage_source !== 'supabase' || !data.deals.every(currentDeal) || data.meta.status!==(data.deals.length?'ok':'no-data') || !Number.isSafeInteger(data.count) || data.count!==data.deals.length || data.deals.length>limit
      || new Set(data.deals.map(deal=>JSON.stringify([deal.county_id,deal.apn]))).size!==data.deals.length) throw new Error()
    return data
  } catch(error) { if(options.signal?.aborted)throw error; throw new FeedUnavailable('The verified feed is unavailable. Please try again.') }
}

export async function fetchDealByApn(apn: string, countyId?: string, options:RequestOptions = {}): Promise<{ deal: Deal } | null> {
  try {
    const query = countyId ? `?county_id=${encodeURIComponent(countyId)}` : ''
    const response=await apiRead(`/api/deals/${encodeURIComponent(apn)}${query}`,options.signal)
    if (response.status === 404) return null
    if (response.status === 409) throw new ParcelAmbiguous('This APN exists in more than one county. Select the county in Explorer.')
    if (response.status!==200||!response.body||typeof response.body!=='object') throw new Error()
    const data=response.body as {deal:Deal}
    if (!currentDeal(data.deal) || data.deal.apn!==apn || (countyId!==undefined&&data.deal.county_id!==countyId)) throw new Error()
    return data
  } catch (error) {
    if (options.signal?.aborted || error instanceof ParcelAmbiguous) throw error
    throw new FeedUnavailable('This parcel could not be checked against the current verified feed.')
  }
}
