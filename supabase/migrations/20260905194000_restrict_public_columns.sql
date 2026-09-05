-- RLS restricts rows, not columns. Prevent direct REST reads of owners, raw
-- ingestion details, private notes and database-only fields with the anon key.
revoke all on public.counties, public.properties, public.deals, public.comps from anon, authenticated;

grant select (county_id, county_name, state, state_fips, county_fips,
  coverage_status, verification_status, validation_status, data_freshness,
  last_successful_run, last_run_status, record_count, qualified_count,
  persisted_count, published_count)
on public.counties to anon, authenticated;

grant select (id, apn, county_id, address, lot_size_acres, zoning, land_use,
  latitude, longitude)
on public.properties to anon, authenticated;

grant select (id, property_id, deal_score, asking_price, estimated_arv_low,
  estimated_arv_high, estimated_costs, estimated_profit_low, estimated_profit_high,
  recommended_offer_low, recommended_offer_high, motivation_signals, status,
  source, source_url, source_vendor, source_quality, verification_status,
  data_freshness, valuation_basis, valuation_confidence, discovered_at, updated_at)
on public.deals to anon, authenticated;

grant select (id, deal_id, address, sale_price, sale_date, distance_miles,
  lot_size_acres, price_per_acre)
on public.comps to anon, authenticated;

create index if not exists idx_deals_verified_score
  on public.deals (deal_score desc, id)
  where status = 'discovered' and verification_status = 'verified';
