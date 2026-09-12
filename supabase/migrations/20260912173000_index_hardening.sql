-- Index hardening for live foreign-key query and write paths.
-- Additive FK coverage is safe for existing data. The dropped indexes are
-- redundant non-unique duplicates; their retained equivalents cover the same
-- keys and no constraint depends on them.

create index if not exists comps_county_id_idx
  on public.comps (county_id);
create index if not exists comps_ingestion_record_id_idx
  on public.comps (ingestion_record_id);
create index if not exists deals_ingestion_record_id_idx
  on public.deals (ingestion_record_id);
create index if not exists ingestion_records_deal_id_idx
  on public.ingestion_records (deal_id);
create index if not exists ingestion_records_property_county_idx
  on public.ingestion_records (property_id, county_id);
create index if not exists ingestion_records_run_county_idx
  on public.ingestion_records (run_id, county_id);

drop index if exists public.idx_comps_deal_id;
drop index if exists public.idx_deals_property_id;
drop index if exists public.ingestion_records_property_idx;
drop index if exists public.idx_properties_county_id;
