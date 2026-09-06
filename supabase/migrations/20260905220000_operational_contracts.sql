-- Real consented signups only. Legacy emails do not acquire invented consent.
-- The expression index fails explicitly on legacy case-duplicates rather than
-- deleting subscriber history. Reconcile such rows before applying the migration.
alter table public.waitlist add column if not exists consented_at timestamptz;
create unique index if not exists waitlist_email_normalized on public.waitlist (lower(email));

create table if not exists public.waitlist_request_limits (
  request_key text primary key check (request_key ~ '^[0-9a-f]{64}$'),
  window_started_at timestamptz not null default now(),
  attempts integer not null check (attempts > 0)
);
create index if not exists waitlist_limits_window on public.waitlist_request_limits(window_started_at);
alter table public.waitlist_request_limits enable row level security;
revoke all on table public.waitlist_request_limits from public,anon,authenticated;
grant select,insert,update,delete on public.waitlist_request_limits to service_role;

-- Counter increments and email upsert share a transaction and row locks.
-- Duplicate requests receive the same response without exposing membership.
create or replace function public.join_waitlist(p_email text,p_source text,p_request_key text)
returns boolean language plpgsql security invoker set search_path=public as $$
declare attempt_count integer;
begin
  if p_email is null or length(p_email)>254 or p_email<>lower(trim(p_email))
    or p_email !~ '^[^[:space:]@<>]+@[^[:space:]@<>]+\.[^[:space:]@<>]+$'
    or p_request_key is null or p_request_key !~ '^[0-9a-f]{64}$'
    or p_source is null or p_source not in ('final_cta','website') then
    raise exception 'Invalid signup request';
  end if;
  delete from public.waitlist_request_limits where request_key in (
    select request_key from public.waitlist_request_limits
      where window_started_at < now()-interval '24 hours' limit 500
  );
  insert into public.waitlist_request_limits as current(request_key,window_started_at,attempts)
    values(p_request_key,now(),1)
    on conflict (request_key) do update set
      window_started_at=case when current.window_started_at < now()-interval '1 hour' then now() else current.window_started_at end,
      attempts=case when current.window_started_at < now()-interval '1 hour' then 1 else least(current.attempts+1,1000) end
    returning attempts into attempt_count;
  if attempt_count>20 then return false; end if;
  insert into public.waitlist(email,source,consented_at) values(p_email,p_source,now())
    on conflict (lower(email)) do update set consented_at=coalesce(waitlist.consented_at,excluded.consented_at);
  return true;
end;
$$;
revoke all on function public.join_waitlist(text,text,text) from public,anon,authenticated;
grant execute on function public.join_waitlist(text,text,text) to service_role;

-- Server-only operational snapshots; counters are computed from current rows,
-- not the last ETL batch's denormalized "published" count. No owner rows returned.
create or replace function public.county_operational_snapshot(p_limit integer default 1000,p_offset integer default 0)
returns table(county jsonb,stored_total bigint,verified_total bigint)
language plpgsql security invoker set search_path=public as $$
begin
  if p_limit not between 1 and 1000 or p_offset not between 0 and 6000 then
    raise exception 'Invalid snapshot bounds';
  end if;
  return query select to_jsonb(c),
    (select count(*) from public.properties p where p.county_id=c.county_id),
    (select count(*) from public.deals d join public.properties p on p.id=d.property_id
      where p.county_id=c.county_id and d.status='discovered' and d.verification_status='verified'
        and d.verified_at is not null and d.verification_expires_at>now())
    from public.counties c order by c.county_id limit p_limit offset p_offset;
end;
$$;
revoke all on function public.county_operational_snapshot(integer,integer) from public,anon,authenticated;
grant execute on function public.county_operational_snapshot(integer,integer) to service_role;
