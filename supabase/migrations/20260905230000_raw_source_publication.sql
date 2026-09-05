-- Keep the exact JSON representation hashed by the producer as well as JSONB.
-- This allows PostgreSQL to independently check the entire payload hash without
-- relying on Python/PostgreSQL having identical JSON number/key serialization.
alter table public.ingestion_records add column if not exists raw_payload_canonical text;
update public.deals set verification_status='pending_review',verified_at=null,verification_expires_at=null
  where verification_status='verified';

create or replace function public.source_mapped_value(payload jsonb,mapping jsonb)
returns jsonb language plpgsql immutable set search_path=public as $$
declare part text; result jsonb=payload; matches integer; composite text; item jsonb; value_text text;
begin
  if jsonb_typeof(mapping)='array' then
    for item in select value from jsonb_array_elements(mapping) loop
      value_text=trim(public.source_mapped_value(payload,item)#>>'{}');
      if nullif(value_text,'') is not null then
        composite=case when composite is null then value_text else composite||', '||value_text end;
      end if;
    end loop;
    return to_jsonb(composite);
  end if;
  if jsonb_typeof(mapping) is distinct from 'string' then return null; end if;
  if jsonb_typeof(payload)='object' then
    select count(*) into matches from jsonb_each(payload) e where lower(e.key)=lower(mapping#>>'{}');
    if matches>1 then raise exception 'Ambiguous source field casing'; end if;
    if matches=1 then return (select e.value from jsonb_each(payload) e where lower(e.key)=lower(mapping#>>'{}')); end if;
  end if;
  foreach part in array string_to_array(mapping#>>'{}','.') loop
    if jsonb_typeof(result) is distinct from 'object' or part='' then return null; end if;
    select count(*) into matches from jsonb_each(result) e where lower(e.key)=lower(part);
    if matches>1 then raise exception 'Ambiguous source field casing'; end if;
    select e.value into result from jsonb_each(result) e where lower(e.key)=lower(part);
  end loop;
  return result;
end;
$$;

create or replace function public.source_number(value jsonb)
returns numeric language plpgsql immutable set search_path=public as $$
declare parsed numeric; content text;
begin
  if jsonb_typeof(value) not in ('number','string') then return null; end if;
  content=replace(trim(value#>>'{}'),',','');
  if left(content,1)='$' then content=substring(content from 2); end if;
  parsed=content::numeric;
  if not public.finite_number(parsed) then return null; end if;
  return parsed;
exception when invalid_text_representation or numeric_value_out_of_range then return null;
end;
$$;

create or replace function public.source_boolean(value jsonb)
returns boolean language sql immutable set search_path=public as $$
  select case when lower(trim(value#>>'{}')) in ('true','yes','y','1') then true
    when lower(trim(value#>>'{}')) in ('false','no','n','0') then false else null end;
$$;

create or replace function public.source_acres(payload jsonb,fields jsonb,cfg jsonb)
returns numeric language plpgsql immutable set search_path=public as $$
declare area numeric; units text;
begin
  area=public.source_number(public.source_mapped_value(payload,fields->'lot_size_acres'));
  units=lower(trim(coalesce(nullif(public.source_mapped_value(payload,fields->'lot_size_unit')#>>'{}',''),
    nullif(cfg->>'acreage_units',''),case when lower(fields->>'lot_size_acres') like '%acre%' then 'acres' end)));
  if area<=0 then return null; end if;
  if units in ('sf','sqft','sq ft','square feet') then return area/43560; end if;
  if units in ('ac','acre','acres','ac.') then return area; end if;
  return null;
end;
$$;

create or replace function public.source_sale_date(value jsonb)
returns timestamptz language plpgsql stable set search_path=public set timezone='UTC' set datestyle='ISO, MDY' as $$
declare content text=value#>>'{}'; millis numeric;
begin
  if jsonb_typeof(value)='number' or content ~ '^-?[0-9]{12,14}$' then
    millis=content::numeric;
    if abs(millis)<100000000000 then return null; end if;
    return to_timestamp((millis/1000)::double precision);
  end if;
  if length(content)<8 or content !~ '^[0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{2,4}' then return null; end if;
  return content::timestamptz;
exception when invalid_datetime_format or datetime_field_overflow or invalid_text_representation or numeric_value_out_of_range then return null;
end;
$$;

create or replace function public.source_mapping_identity(fields jsonb)
returns jsonb language sql immutable set search_path=public as $$
  select case when jsonb_typeof(fields)='object' then (
    select jsonb_object_agg(key,case when jsonb_typeof(value)='array' then
      (select coalesce(jsonb_agg(to_jsonb(lower(coalesce(item#>>'{}','none')))),'[]'::jsonb) from jsonb_array_elements(value) item)
      else to_jsonb(lower(coalesce(value#>>'{}','none'))) end) from jsonb_each(fields)
  ) else null end;
$$;

create or replace function public.source_vacancy_supported(payload jsonb,fields jsonb,cfg jsonb)
returns boolean language plpgsql immutable set search_path=public as $$
declare improvement numeric; flag boolean; land_use text; zoning text; code text;
begin
  improvement=public.source_number(public.source_mapped_value(payload,fields->'improvement_value'));
  flag=public.source_boolean(public.source_mapped_value(payload,fields->'has_improvements'));
  if flag is true or improvement>0 or improvement<0 then return false; end if;
  land_use=lower(trim(coalesce(public.source_mapped_value(payload,fields->'land_use')#>>'{}','')));
  if land_use ~ '\m(sfr|house|home|dwelling|building|apartment|condominium|warehouse|improved)\M'
    or land_use ~ '\m(not|non|formerly|previously)[ -]+(vacant|unimproved)\M' then return false; end if;
  if land_use ~ '\m(vacant|unimproved)\M' or improvement=0 then return true; end if;
  zoning=lower(trim(coalesce(public.source_mapped_value(payload,fields->'zoning')#>>'{}','')));
  if flag is false and (land_use ~ '\mresidential\M' or zoning ~ '\m(residential|res|r-?[0-9]+)\M') then return true; end if;
  code=upper(trim(coalesce(public.source_mapped_value(payload,fields->'use_code')#>>'{}',land_use)));
  if nullif(cfg->>'vacancy_codebook_url','') is not null and jsonb_typeof(cfg->'vacant_use_codes')='array'
    and exists(select 1 from jsonb_array_elements_text(cfg->'vacant_use_codes') c where upper(c)=code) then return true; end if;
  return false;
end;
$$;

create or replace function public.require_raw_source_evidence()
returns trigger language plpgsql security invoker set search_path=public as $$
declare r public.ingestion_records%rowtype; prop public.properties%rowtype; cfg jsonb; fields jsonb; comp record; canonical jsonb;
begin
  if new.verification_status is distinct from 'verified' then return new; end if;
  select * into r from public.ingestion_records where id=new.ingestion_record_id;
  select * into prop from public.properties where id=new.property_id;
  select metadata->'source_config' into cfg from public.ingestion_runs where id=r.run_id;
  fields=cfg->'fields';
  canonical=r.raw_payload_canonical::jsonb;
  if (jsonb_typeof(fields)='object' and fields<>'{}'::jsonb and public.source_mapping_identity(r.field_mapping)=public.source_mapping_identity(fields)
      and public.source_vacancy_supported(r.raw_payload,fields,cfg)
      and canonical=r.raw_payload and r.raw_payload_canonical is not null
      and encode(sha256(convert_to(r.raw_payload_canonical,'UTF8')),'hex')=prop.source_payload_hash
      and trim(public.source_mapped_value(r.raw_payload,fields->'apn')#>>'{}')=prop.apn
      and abs(public.source_acres(r.raw_payload,fields,cfg)-prop.lot_size_acres)<0.0000001
      and public.source_number(public.source_mapped_value(r.raw_payload,fields->'asking_price'))=new.asking_price
      and public.source_number(public.source_mapped_value(r.raw_payload,fields->'estimated_costs'))=new.estimated_costs
      and public.source_boolean(public.source_mapped_value(r.raw_payload,fields->'costs_complete'))
      and public.source_mapped_value(r.raw_payload,fields->'costs_source_url')#>>'{}' ~ '^https?://'
      and abs(public.source_number(public.source_mapped_value(r.raw_payload,fields->'latitude'))-prop.latitude)<0.0000001
      and abs(public.source_number(public.source_mapped_value(r.raw_payload,fields->'longitude'))-prop.longitude)<0.0000001
    ) is not true then raise exception 'Publication requires authorized mappings and matching raw source evidence'; end if;
  for comp in select c.*,a.raw_payload,a.raw_payload_canonical,a.field_mapping
      from public.comps c left join public.ingestion_records a on a.id=c.ingestion_record_id where c.deal_id=new.id loop
    if (public.source_mapping_identity(comp.field_mapping)=public.source_mapping_identity(fields) and comp.raw_payload_canonical::jsonb=comp.raw_payload
        and trim(public.source_mapped_value(comp.raw_payload,fields->'apn')#>>'{}')=comp.source_apn
        and public.source_number(public.source_mapped_value(comp.raw_payload,fields->'last_sale_price'))=comp.sale_price
        and public.source_sale_date(public.source_mapped_value(comp.raw_payload,fields->'last_sale_date'))=comp.sale_date
        and abs(public.source_acres(comp.raw_payload,fields,cfg)-comp.lot_size_acres)<0.0000001
        and public.source_boolean(public.source_mapped_value(comp.raw_payload,fields->'sale_qualified'))
        and public.source_boolean(public.source_mapped_value(comp.raw_payload,fields->'vacant_at_sale'))
        and abs(comp.distance_miles-public.distance_miles(prop.latitude,prop.longitude,
          public.source_number(public.source_mapped_value(comp.raw_payload,fields->'latitude'))::double precision,
          public.source_number(public.source_mapped_value(comp.raw_payload,fields->'longitude'))::double precision))<=0.02
      ) is not true then raise exception 'Publication requires raw source-backed comparable sales'; end if;
  end loop;
  return new;
end;
$$;
create trigger deals_require_raw_source_evidence before insert or update on public.deals
  for each row execute function public.require_raw_source_evidence();

revoke all on function public.source_mapped_value(jsonb,jsonb),public.source_number(jsonb),public.source_boolean(jsonb),
  public.source_acres(jsonb,jsonb,jsonb),public.source_sale_date(jsonb),public.source_mapping_identity(jsonb),public.source_vacancy_supported(jsonb,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.source_mapped_value(jsonb,jsonb),public.source_number(jsonb),public.source_boolean(jsonb),
  public.source_acres(jsonb,jsonb,jsonb),public.source_sale_date(jsonb),public.source_mapping_identity(jsonb),public.source_vacancy_supported(jsonb,jsonb,jsonb) to service_role;
