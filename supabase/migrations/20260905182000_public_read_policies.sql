-- Keep the production publication contract reproducible from migrations.
-- The browser-facing roles may read published data only; writes remain server-side.

alter table public.counties enable row level security;
alter table public.properties enable row level security;
alter table public.deals enable row level security;
alter table public.comps enable row level security;

-- Replace policies so this migration is safe when the same policy names already exist.
drop policy if exists "public read counties" on public.counties;
create policy "public read counties"
on public.counties
for select
to anon, authenticated
using (true);

drop policy if exists "public read published deals" on public.deals;
create policy "public read published deals"
on public.deals
for select
to anon, authenticated
using (
  status = 'discovered'
  and verification_status = 'verified'
);

drop policy if exists "public read deal properties" on public.properties;
create policy "public read deal properties"
on public.properties
for select
to anon, authenticated
using (
  exists (
    select 1
    from public.deals d
    where d.property_id = properties.id
      and d.status = 'discovered'
      and d.verification_status = 'verified'
  )
);

drop policy if exists "public read comps for published deals" on public.comps;
create policy "public read comps for published deals"
on public.comps
for select
to anon, authenticated
using (
  exists (
    select 1
    from public.deals d
    where d.id = comps.deal_id
      and d.status = 'discovered'
      and d.verification_status = 'verified'
  )
);

-- Least privilege for browser-facing roles: published tables are read-only.
revoke all on table public.counties, public.properties, public.deals, public.comps from anon, authenticated;
grant select on table public.counties, public.properties, public.deals, public.comps to anon, authenticated;

-- Subscriber, delivery and waitlist data is server-only.
revoke all on table public.subscribers, public.deliveries, public.waitlist from anon, authenticated;
