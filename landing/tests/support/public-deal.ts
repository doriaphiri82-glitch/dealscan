import type { Deal } from '../../lib/deals'

/** Offline browser transport fixture only; never used by application data paths. */
export function publishedDeal(patch: Partial<Deal> = {}): Deal {
  return {
    apn:'fixture-parcel',county_id:'fixture_county',source_record_id:'fixture-source-id',
    source_url:'https://county.example/parcel',status:'discovered',verification_status:'verified',
    verified_at:new Date().toISOString(),verification_expires_at:new Date(Date.now()+3600000).toISOString(),
    asking_price:20000,asking_price_basis:'source',estimated_costs:5000,
    estimated_arv_low:80000,estimated_arv_high:100000,estimated_profit_low:55000,estimated_profit_high:75000,
    recommended_offer_low:12000,recommended_offer_high:16000,deal_score:60,valuation_confidence:.75,
    valuation_basis:'comparable_sales',valuation_model:'vacant_land_comps_v1',
    lot_size_acres:1,latitude:35,longitude:-114,...patch,
  }
}
