-- Harden the shared trigger function against search_path manipulation.
-- Keep the function's dependency explicit and stable in production.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
