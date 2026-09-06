-- Publication requires durable evidence, not a caller-provided status string.
-- Old unverifiable assessments are retained privately, not deleted or seeded.
update public.deals set verification_status='pending_review', verified_at=null, verification_expires_at=null
  where verification_status='verified';

create or replace function public.bump_deal_revision()
returns trigger language plpgsql set search_path=public as $$
begin
  new.revision=old.revision+1;
  return new;
end;
$$;
create trigger deals_bump_revision before update on public.deals
  for each row execute function public.bump_deal_revision();

create or replace function public.distance_miles(lat1 double precision, lon1 double precision, lat2 double precision, lon2 double precision)
returns double precision language sql immutable set search_path=public as $$
  select 7917.5226 * asin(least(1.0,sqrt(
    power(sin(radians(lat2-lat1)/2),2)+cos(radians(lat1))*cos(radians(lat2))*power(sin(radians(lon2-lon1)/2),2))));
$$;

create or replace function public.require_publication_evidence()
returns trigger language plpgsql security invoker set search_path=public as $$
declare
  prop public.properties%rowtype;
  evidence public.ingestion_records%rowtype;
  audit_run public.ingestion_runs%rowtype;
  county public.counties%rowtype;
  comparable_count integer;
  median_ppa numeric;
  expected_high numeric;
  validated_at timestamptz;
begin
  if new.verification_status is distinct from 'verified' then
    new.verified_at=null;
    new.verification_expires_at=null;
    return new;
  end if;
  select * into prop from public.properties where id=new.property_id;
  select * into evidence from public.ingestion_records where id=new.ingestion_record_id;
  select * into audit_run from public.ingestion_runs where id=evidence.run_id;
  select * into county from public.counties where county_id=prop.county_id;
  validated_at=(audit_run.metadata->>'source_validated_at')::timestamptz;
  if (new.status='discovered' and prop.vacancy_status='qualified' and prop.has_improvements is not true
      and evidence.property_id=new.property_id and evidence.county_id=prop.county_id
      and evidence.status='candidate' and audit_run.status='completed'
      and coalesce((audit_run.metadata->>'audit_gap')::boolean,false)=false
      and evidence.source_url=new.source_url and evidence.source_url=prop.source_url
      and evidence.source_url=audit_run.source_url and evidence.source_record_id=prop.source_record_id
      and nullif(evidence.source_record_id,'') is not null and evidence.raw_payload<>'{}'::jsonb
      and jsonb_typeof(evidence.raw_payload)='object' and length(prop.source_payload_hash)=64
      and prop.source_fingerprint=audit_run.metadata->>'source_fingerprint'
      and prop.source_fingerprint=audit_run.metadata->>'authorized_source_fingerprint'
      and prop.source_fingerprint=county.extra->>'authorized_source_fingerprint'
      and county.validation_status='valid' and (county.extra->>'ingestion_authorized')::boolean
      and validated_at between now()-interval '7 days' and now()+interval '5 minutes'
      and evidence.normalized_payload->>'apn'=prop.apn
      and (evidence.normalized_payload->>'lot_size_acres')::numeric=prop.lot_size_acres
      and public.finite_number(prop.lot_size_acres) and prop.lot_size_acres>0
      and public.finite_number(prop.latitude::numeric) and prop.latitude between -90 and 90
      and public.finite_number(prop.longitude::numeric) and prop.longitude between -180 and 180
      and new.asking_price_basis='source' and public.finite_number(new.asking_price) and new.asking_price>0
      and public.finite_number(new.estimated_costs) and new.estimated_costs>=0
      and new.valuation_model='vacant_land_comps_v1' and new.valuation_basis='comparable_sales'
      and new.financial_evidence->>'model_version'=new.valuation_model
      and new.financial_evidence->>'asking_price_field'=evidence.field_mapping->>'asking_price'
      and nullif(evidence.field_mapping->>'asking_price','') is not null
      and (evidence.normalized_payload->>'asking_price')::numeric=new.asking_price
      and (evidence.normalized_payload->>'estimated_costs')::numeric=new.estimated_costs
      and (evidence.normalized_payload->>'costs_complete')::boolean
      and evidence.normalized_payload->>'costs_source_url' ~ '^https?://'
      and new.deal_score between 0 and 100) is not true then
    raise exception 'Publication requires completed, authorized, source-backed parcel and financial evidence';
  end if;
  select count(*), percentile_cont(0.5) within group(order by sale_price/lot_size_acres)
    into comparable_count,median_ppa from public.comps where deal_id=new.id;
  if comparable_count<3 or exists (
    select 1 from public.comps c left join public.ingestion_records r on r.id=c.ingestion_record_id
      where c.deal_id=new.id and (
        r.status in ('held','candidate','persisted') and r.hold_reason is distinct from 'duplicate_county_apn'
        and r.run_id=audit_run.id and r.county_id=prop.county_id and c.county_id=prop.county_id
        and r.id<>evidence.id and c.source_apn<>prop.apn and c.source_apn=r.normalized_payload->>'apn'
        and r.source_record_id=c.source_record_id and r.source_url=c.source_url and c.source_url=audit_run.source_url
        and jsonb_typeof(r.raw_payload)='object' and r.raw_payload<>'{}'::jsonb
        and c.sale_qualified and c.vacant_at_sale
        and (r.normalized_payload->>'sale_qualified')::boolean and (r.normalized_payload->>'vacant_at_sale')::boolean
        and public.finite_number(c.sale_price) and c.sale_price>0
        and public.finite_number(c.lot_size_acres) and c.lot_size_acres between prop.lot_size_acres*0.25 and prop.lot_size_acres*4
        and public.finite_number(c.distance_miles) and c.distance_miles between 0 and 10
        and c.sale_date between now()-interval '1095 days' and now()
        and (r.normalized_payload->>'last_sale_price')::numeric=c.sale_price
        and (r.normalized_payload->>'last_sale_date')::timestamptz=c.sale_date
        and (r.normalized_payload->>'lot_size_acres')::numeric=c.lot_size_acres
        and (r.normalized_payload->>'latitude')::double precision between -90 and 90
        and (r.normalized_payload->>'longitude')::double precision between -180 and 180
        and abs(c.distance_miles-public.distance_miles(prop.latitude,prop.longitude,
          (r.normalized_payload->>'latitude')::double precision,(r.normalized_payload->>'longitude')::double precision))<=0.02
      ) is not true
  ) then raise exception 'Publication requires at least three traceable, qualified, recent, nearby vacant-land sales'; end if;
  expected_high=round(median_ppa*prop.lot_size_acres,2);
  if (public.finite_number(new.estimated_arv_high) and abs(new.estimated_arv_high-expected_high)<=0.011
      and public.finite_number(new.estimated_arv_low) and abs(new.estimated_arv_low-round(expected_high*0.8,2))<=0.011
      and public.finite_number(new.estimated_profit_low) and new.estimated_profit_low>=1000
      and abs(new.estimated_profit_low-(new.estimated_arv_low-new.asking_price-new.estimated_costs))<=0.011
      and public.finite_number(new.estimated_profit_high)
      and abs(new.estimated_profit_high-(new.estimated_arv_high-new.asking_price-new.estimated_costs))<=0.011
      and public.finite_number(new.recommended_offer_low) and abs(new.recommended_offer_low-round(new.asking_price*0.6,2))<=0.011
      and public.finite_number(new.recommended_offer_high) and abs(new.recommended_offer_high-round(new.asking_price*0.8,2))<=0.011
      and public.finite_number(new.valuation_confidence) and abs(new.valuation_confidence-least(0.9,0.6+comparable_count*0.05))<0.001
      and (new.financial_evidence->>'comparable_count')::integer=comparable_count) is not true then
    raise exception 'Publication calculations do not match source-backed evidence';
  end if;
  new.verified_at=clock_timestamp();
  new.verification_expires_at=least(validated_at+interval '7 days',now()+interval '7 days');
  return new;
end;
$$;
create trigger deals_require_publication_evidence before insert or update on public.deals
  for each row execute function public.require_publication_evidence();

-- Changes to underlying evidence revoke publication in the SAME transaction.
-- Revision increments make an optimistic verification fail after any such change.
create or replace function public.revoke_changed_property_deals()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if (to_jsonb(new)-'updated_at'-'last_seen_at') is distinct from (to_jsonb(old)-'updated_at'-'last_seen_at') then
    update public.deals set verification_status='pending_review',verified_at=null where property_id=new.id;
  end if;
  return new;
end;
$$;
create trigger properties_revoke_changed_deals after update on public.properties
  for each row execute function public.revoke_changed_property_deals();

create or replace function public.revoke_changed_comp_deals()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if tg_op<>'INSERT' then
    update public.deals set verification_status='pending_review',verified_at=null where id=old.deal_id;
  end if;
  if tg_op<>'DELETE' then
    update public.deals set verification_status='pending_review',verified_at=null where id=new.deal_id;
  end if;
  return null;
end;
$$;
create trigger comps_revoke_changed_deals after insert or update or delete on public.comps
  for each row execute function public.revoke_changed_comp_deals();

create or replace function public.revoke_changed_audit_deals()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if (to_jsonb(new)-'updated_at'-'deal_id') is distinct from (to_jsonb(old)-'updated_at'-'deal_id') then
    update public.deals d set verification_status='pending_review',verified_at=null where d.ingestion_record_id=old.id
      or exists(select 1 from public.comps c where c.deal_id=d.id and c.ingestion_record_id=old.id);
  end if;
  return new;
end;
$$;
create trigger ingestion_records_revoke_changed_deals after update on public.ingestion_records
  for each row execute function public.revoke_changed_audit_deals();

create or replace function public.revoke_changed_run_deals()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if row(new.status,new.source_url,new.county_id,new.metadata) is distinct from row(old.status,old.source_url,old.county_id,old.metadata) then
    update public.deals d set verification_status='pending_review',verified_at=null
      from public.ingestion_records r where r.id=d.ingestion_record_id and r.run_id=old.id;
  end if;
  return new;
end;
$$;
create trigger ingestion_runs_revoke_changed_deals after update on public.ingestion_runs
  for each row execute function public.revoke_changed_run_deals();

create or replace function public.revoke_changed_county_deals()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if row(new.validation_status,new.arcgis_layer_url,new.field_mapping,new.extra->'ingestion_authorized',new.extra->'authorized_source_fingerprint')
    is distinct from row(old.validation_status,old.arcgis_layer_url,old.field_mapping,old.extra->'ingestion_authorized',old.extra->'authorized_source_fingerprint') then
    update public.deals d set verification_status='pending_review',verified_at=null
      from public.properties p where p.id=d.property_id and p.county_id=new.county_id;
  end if;
  return new;
end;
$$;
create trigger counties_revoke_changed_deals after update on public.counties
  for each row execute function public.revoke_changed_county_deals();

-- Remove inherited table AND column-level grants/policies from older deployments.
-- REVOKE ALL ON TABLE alone does not revoke explicit column grants. Unknown old
-- permissive SELECT policies otherwise OR together with the verified-only rules.
do $$ declare item record; columns text; begin
  for item in select c.oid,c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname in ('counties','properties','deals','comps','subscribers','deliveries','waitlist','ingestion_runs','ingestion_records') loop
    select string_agg(quote_ident(attname),',') into columns from pg_attribute
      where attrelid=item.oid and attnum>0 and not attisdropped;
    execute format('revoke all on table public.%I from public,anon,authenticated',item.relname);
    execute format('revoke select (%s),insert (%s),update (%s),references (%s) on table public.%I from public,anon,authenticated',columns,columns,columns,columns,item.relname);
  end loop;
  for item in select tablename,policyname from pg_policies where schemaname='public'
    and tablename in ('counties','properties','deals','comps','subscribers','deliveries','waitlist','ingestion_runs','ingestion_records') loop
    execute format('drop policy %I on public.%I',item.policyname,item.tablename);
  end loop;
end $$;

create policy "public read counties" on public.counties for select to anon,authenticated using (true);
-- Expiration is enforced even if scheduled revalidation does not run.
create policy "public read published deals" on public.deals for select to anon,authenticated
  using (status='discovered' and verification_status='verified' and verified_at is not null and verification_expires_at>now());
create policy "public read deal properties" on public.properties for select to anon,authenticated
  using (exists(select 1 from public.deals d where d.property_id=properties.id));
create policy "public read comps for published deals" on public.comps for select to anon,authenticated
  using (exists(select 1 from public.deals d where d.id=comps.deal_id));

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
  data_freshness, valuation_basis, valuation_confidence, discovered_at, updated_at, asking_price_basis, verified_at, verification_expires_at, valuation_model)
on public.deals to anon, authenticated;

grant select (id, deal_id, address, sale_price, sale_date, distance_miles,
  lot_size_acres, price_per_acre, source_url, source_record_id, source_apn, county_id, sale_qualified, vacant_at_sale)
on public.comps to anon, authenticated;

revoke all on function public.finite_number(numeric), public.distance_miles(double precision,double precision,double precision,double precision) from public,anon,authenticated;
grant execute on function public.finite_number(numeric), public.distance_miles(double precision,double precision,double precision,double precision) to service_role;
