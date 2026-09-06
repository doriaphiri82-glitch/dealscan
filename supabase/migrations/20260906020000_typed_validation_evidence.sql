-- Validation evidence is typed proof, not truthy strings or fabricated counts.
-- Existing assessments remain private if either the current county permission
-- or the run's recorded permission cannot satisfy this contract.
create or replace function public.current_validation_proof(status text, proof jsonb, fingerprint text)
returns boolean language plpgsql stable set search_path=public set timezone='UTC' as $$
declare validated_at timestamptz;
begin
  if (status='valid' and jsonb_typeof(proof)='object'
      and proof->'validation_source_fields_checked'='true'::jsonb
      and proof->'validation_pagination_checked'='true'::jsonb
      and proof->'ingestion_authorized'='true'::jsonb
      and jsonb_typeof(proof->'validation_sample_checked')='number'
      and proof->>'validation_sample_checked' ~ '^[1-5]$'
      and fingerprint ~ '^[0-9a-f]{64}$'
      and proof->>'validated_source_fingerprint'=fingerprint
      and proof->>'authorized_source_fingerprint'=fingerprint
      and jsonb_typeof(proof->'last_validated_at')='string'
      and proof->>'last_validated_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[T ]') is not true then
    return false;
  end if;
  validated_at=(proof->>'last_validated_at')::timestamptz;
  return validated_at between now()-interval '7 days' and now()+interval '5 minutes';
exception when invalid_datetime_format or datetime_field_overflow then return false;
end;
$$;

update public.deals d set verification_status='pending_review',verified_at=null,verification_expires_at=null
where d.verification_status='verified' and not exists (
  select 1 from public.properties p join public.counties c on c.county_id=p.county_id
    join public.ingestion_records r on r.id=d.ingestion_record_id
    join public.ingestion_runs u on u.id=r.run_id
    where p.id=d.property_id
      and public.current_validation_proof(c.validation_status,c.extra,p.source_fingerprint)
      and public.current_validation_proof(u.metadata->'source_authorization'->>'validation_status',
          u.metadata->'source_authorization',p.source_fingerprint)
);

create or replace function public.require_typed_source_validation()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if new.verification_status='verified' and not exists (
    select 1 from public.properties p join public.counties c on c.county_id=p.county_id
      join public.ingestion_records r on r.id=new.ingestion_record_id
      join public.ingestion_runs u on u.id=r.run_id
      where p.id=new.property_id
        and public.current_validation_proof(c.validation_status,c.extra,p.source_fingerprint)
        and public.current_validation_proof(u.metadata->'source_authorization'->>'validation_status',
            u.metadata->'source_authorization',p.source_fingerprint)
  ) then raise exception 'Publication requires current typed source validation and authorization evidence'; end if;
  return new;
end;
$$;
create trigger deals_require_a_typed_validation before insert or update on public.deals
  for each row execute function public.require_typed_source_validation();
revoke all on function public.current_validation_proof(text,jsonb,text),public.require_typed_source_validation() from public,anon,authenticated;
grant execute on function public.current_validation_proof(text,jsonb,text),public.require_typed_source_validation() to service_role;


-- Changes to any part of permission evidence revoke already-public rows in the
-- same transaction, not merely when a future verification is attempted.
create or replace function public.revoke_changed_validation_proof()
returns trigger language plpgsql security invoker set search_path=public as $$
begin
  if new.validation_status is distinct from old.validation_status or
    jsonb_build_array(new.extra->'validation_source_fields_checked',new.extra->'validation_pagination_checked',
      new.extra->'validation_sample_checked',new.extra->'last_validated_at',
      new.extra->'validated_source_fingerprint',new.extra->'authorized_source_fingerprint',new.extra->'ingestion_authorized')
    is distinct from
    jsonb_build_array(old.extra->'validation_source_fields_checked',old.extra->'validation_pagination_checked',
      old.extra->'validation_sample_checked',old.extra->'last_validated_at',
      old.extra->'validated_source_fingerprint',old.extra->'authorized_source_fingerprint',old.extra->'ingestion_authorized')
  then
    update public.deals set verification_status='pending_review',verified_at=null,verification_expires_at=null
      where verification_status='verified' and property_id in (
        select id from public.properties where county_id=new.county_id);
  end if;
  return new;
end;
$$;
create trigger counties_revoke_validation_proof after update on public.counties
  for each row execute function public.revoke_changed_validation_proof();
revoke all on function public.revoke_changed_validation_proof() from public,anon,authenticated;
grant execute on function public.revoke_changed_validation_proof() to service_role;
