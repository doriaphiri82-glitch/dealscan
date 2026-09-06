-- Legacy activity flags do not establish permission to send new email alerts.
-- Keep existing records/preferences; do not manufacture consent or erase history.
alter table public.subscribers add column if not exists consented_at timestamptz;
alter table public.subscribers add column if not exists unsubscribe_url text;
alter table public.subscribers alter column is_active set default false;
alter table public.subscribers alter column budget_min drop default;
alter table public.subscribers alter column budget_max drop default;
alter table public.subscribers alter column min_profit drop default;
