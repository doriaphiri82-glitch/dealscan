/*
 * Committed demo/seed bundle. Statically imported by API routes so it ships
 * inside the serverless function bundle — no runtime fs reads (which Vercel
 * serverless functions don't expose for committed data files).
 *
 * The pipeline (pipeline/publish.py) overwrites the live source (Redis/KV)
 * with real data when it runs. Until then, this seed data keeps /api/deals
 * and /api/deals/[apn] populated with a labeled demo so the site is never
 * empty.
 */

export interface DealRecord {
  apn: string
  address: string
  county_id: string
  lot_size_acres: number
  asking_price: number
  deal_score: number
  estimated_arv_low: number
  estimated_arv_high: number
  estimated_profit_low: number
  estimated_profit_high: number
  motivation_signals: string[]
  market_velocity: number
  competition_level: string
  owner_state: string
  zoning: string
  tax_delinquent_years: number
  source: string
}

export interface DealsBundle {
  generated_at: string | null
  count: number
  deals: DealRecord[]
  error?: string
  meta: {
    status: string
    scraped_counties: string[]
  }
}

export const SEED_BUNDLE: DealsBundle = {
  generated_at: '2026-08-31T10:18:27.894612+00:00',
  count: 3,
  deals: [
    {
      apn: '123-45-678A',
      address: 'Lot 12, Sierra Vista Estates',
      county_id: 'cochise_az',
      lot_size_acres: 2.31,
      asking_price: 2100.0,
      deal_score: 88,
      estimated_arv_low: 8279.0,
      estimated_arv_high: 10349.0,
      estimated_profit_low: 5517.0,
      estimated_profit_high: 7586.0,
      motivation_signals: [
        'tax_delinquent',
        'absentee_owner',
        'long_ownership',
        'no_improvements',
        'vacant_land',
      ],
      market_velocity: 0.7,
      competition_level: 'low',
      owner_state: 'CA',
      zoning: 'Rural Residential',
      tax_delinquent_years: 3,
      source: 'demo',
    },
    {
      apn: '456-78-901B',
      address: 'Parcel 7, Golden Valley Ranchos',
      county_id: 'mohave_az',
      lot_size_acres: 5.02,
      asking_price: 4500.0,
      deal_score: 74,
      estimated_arv_low: 12132.0,
      estimated_arv_high: 15165.0,
      estimated_profit_low: 6661.0,
      estimated_profit_high: 9694.0,
      motivation_signals: [
        'absentee_owner',
        'long_ownership',
        'no_improvements',
        'vacant_land',
        'probate',
      ],
      market_velocity: 0.6,
      competition_level: 'low',
      owner_state: 'AZ',
      zoning: 'Rural Residential',
      tax_delinquent_years: 1,
      source: 'demo',
    },
    {
      apn: '789-01-234C',
      address: 'Tract 3, Rio Grande Estates',
      county_id: 'socorro_nm',
      lot_size_acres: 10.5,
      asking_price: 3200.0,
      deal_score: 73,
      estimated_arv_low: 6262.0,
      estimated_arv_high: 7827.0,
      estimated_profit_low: 2561.0,
      estimated_profit_high: 4126.0,
      motivation_signals: [
        'tax_delinquent',
        'absentee_owner',
        'long_ownership',
        'no_improvements',
        'vacant_land',
        'probate',
      ],
      market_velocity: 0.55,
      competition_level: 'low',
      owner_state: 'TX',
      zoning: 'Agricultural Residential',
      tax_delinquent_years: 4,
      source: 'demo',
    },
  ],
  error: '',
  meta: {
    scraped_counties: ['demo'],
    status: 'demo',
  },
}

export const SEED_REGISTRY = [
  { apn: '123-45-678A', county_id: 'cochise_az' },
  { apn: '456-78-901B', county_id: 'mohave_az' },
  { apn: '789-01-234C', county_id: 'socorro_nm' },
]

export default SEED_BUNDLE