-- The audit status vocabulary the ETL writes, enforced by the database.
--
-- A legacy check on public.ingestion_records restricted status to
-- ('received','normalized','persisted','rejected','duplicate','error'), which
-- predates 'candidate', 'held', 'skipped' and 'failed'. Those four are written
-- by every real run, and one offending row rejects the whole batched insert
-- with SQLSTATE 23514. That is how a production run stored 248 authentic
-- properties and zero lineage records while every column and index checked out.
--
-- The replacement is the union: the vocabulary in pipeline/persistence.py plus
-- the legacy values, so rows written by earlier deployments stay valid. No data
-- is deleted or rewritten.
do $$ begin
  if exists (select 1 from pg_constraint con join pg_class c on c.oid=con.conrelid
             join pg_namespace n on n.oid=c.relnamespace
             where n.nspname='public' and c.relname='ingestion_records'
               and con.conname='ingestion_records_status_check') then
    alter table public.ingestion_records drop constraint ingestion_records_status_check;
  end if;
  if not exists (select 1 from pg_constraint con join pg_class c on c.oid=con.conrelid
                 join pg_namespace n on n.oid=c.relnamespace
                 where n.nspname='public' and c.relname='ingestion_records'
                   and con.conname='ingestion_records_status_v2') then
    alter table public.ingestion_records add constraint ingestion_records_status_v2
      check (status in ('received','normalized','persisted','candidate','held',
                        'rejected','skipped','duplicate','error','failed'));
  end if;
end $$;
