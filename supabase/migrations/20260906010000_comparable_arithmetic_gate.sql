-- A materialized price-per-acre must agree with actual sale price and acreage.
-- Do not repair old source facts by inventing values; keep inconsistent deals
-- private until their persisted evidence has been reviewed again.
update public.deals d set verification_status='pending_review',verified_at=null,verification_expires_at=null
where d.verification_status='verified' and exists (
  select 1 from public.comps c where c.deal_id=d.id and (
    public.finite_number(c.price_per_acre) and c.price_per_acre>0
    and public.finite_number(c.sale_price) and c.sale_price>0
    and public.finite_number(c.lot_size_acres) and c.lot_size_acres>0
    and abs(c.price_per_acre-c.sale_price/nullif(c.lot_size_acres,0))<=0.011
  ) is not true
);

create or replace function public.require_comparable_arithmetic()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if new.verification_status='verified' and exists (
    select 1 from public.comps c where c.deal_id=new.id and (
      public.finite_number(c.price_per_acre) and c.price_per_acre>0
      and public.finite_number(c.sale_price) and c.sale_price>0
      and public.finite_number(c.lot_size_acres) and c.lot_size_acres>0
      and abs(c.price_per_acre-c.sale_price/nullif(c.lot_size_acres,0))<=0.011
    ) is not true
  ) then raise exception 'Publication requires reproducible comparable price-per-acre arithmetic'; end if;
  return new;
end;
$$;
create trigger deals_require_comparable_arithmetic before insert or update on public.deals
  for each row execute function public.require_comparable_arithmetic();
revoke all on function public.require_comparable_arithmetic() from public,anon,authenticated;
grant execute on function public.require_comparable_arithmetic() to service_role;
