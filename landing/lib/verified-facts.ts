/** Read-boundary invariants; this never manufactures missing financial facts. */
type Row = Record<string, unknown>
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const present = (value: unknown): value is string => typeof value === 'string' && !!value.trim()

export function currentVerification(row: Row, now = Date.now()): boolean {
  if (row.status !== 'discovered' || row.verification_status !== 'verified' || typeof row.verified_at !== 'string' || typeof row.verification_expires_at !== 'string') return false
  const verified=Date.parse(row.verified_at), expires=Date.parse(row.verification_expires_at)
  return Number.isFinite(verified) && Number.isFinite(expires) && verified<=now+300000 && expires>now && expires<=verified+7*86400000
}

export function supportedFinancialFacts(row: Row): boolean {
  const {asking_price:ask, estimated_costs:costs, estimated_arv_low:low, estimated_arv_high:high,
    estimated_profit_low:profitLow, estimated_profit_high:profitHigh, deal_score:score,
    recommended_offer_low:offerLow,recommended_offer_high:offerHigh,valuation_confidence:confidence,
    lot_size_acres:area,latitude:lat,longitude:lon}=row
  if (!finite(ask) || ask<=0 || !finite(costs) || costs<0 || !finite(low) || low<=0 || !finite(high) || high<low) return false
  if (!finite(profitLow) || profitLow<1000 || !finite(profitHigh) || profitHigh<profitLow) return false
  if (Math.abs(low-Math.round(high*.8*100)/100)>.011) return false
  if (Math.abs(low-ask-costs-profitLow)>.011 || Math.abs(high-ask-costs-profitHigh)>.011) return false
  if (!finite(score) || !Number.isInteger(score) || score<0 || score>100 || !finite(confidence) || confidence<.75 || confidence>.9) return false
  if (!finite(offerLow) || !finite(offerHigh) || offerLow<0 || offerHigh<offerLow || offerHigh>ask) return false
  if (Math.abs(offerLow-Math.round(ask*.6*100)/100)>.011 || Math.abs(offerHigh-Math.round(ask*.8*100)/100)>.011) return false
  if (!finite(area) || area<=0 || !finite(lat) || !finite(lon) || Math.abs(lat)>90 || Math.abs(lon)>180 || (lat===0&&lon===0)) return false
  return row.asking_price_basis==='source' && row.valuation_basis==='comparable_sales' && row.valuation_model==='vacant_land_comps_v1'
}

export function sourceReference(row: Row): boolean {
  if (!present(row.apn) || !present(row.county_id) || !present(row.source_record_id) || !present(row.source_url)) return false
  if (!/^[a-zA-Z0-9_-]{1,150}$/.test(row.county_id) || row.apn.length>200 || /[\u0000-\u001f\u007f]/.test(row.apn)) return false
  try {
    const url=new URL(row.source_url)
    return ['https:','http:'].includes(url.protocol) && !url.username && !url.password
  } catch { return false }
}
