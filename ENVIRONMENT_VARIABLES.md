# Environment Variables

Names only. **No secret value was read, printed, stored or transmitted during
this audit.** Sources: GitHub Actions secrets API (names + timestamps only —
values are write-only), the `dealscan-vercel-handoff` annotation's
`present`/`missing` lists (names only), and the three committed `.env.example`
templates. Audit date 2026-09-19.

Classification: **PUBLIC** (browser-safe), **SERVER_ONLY**, **SECRET**,
**OPTIONAL**, **DEVELOPMENT_ONLY**, **PRODUCTION_REQUIRED**.

## Application runtime (Next.js in `landing/`)

| Variable | Class | Purpose | GitHub | Vercel |
|---|---|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | PUBLIC | Supabase project origin for browser + SSR clients | — | Required (present) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | PUBLIC | Anon JWT / `sb_publishable_` key; the only browser key | — | Required (present) |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | PUBLIC | Present in Vercel; **not read by app code** | — | Present (obsolete-but-harmless) |
| `SUPABASE_URL` | SERVER_ONLY | Server-side Supabase origin (admin + RPC) | Required (present) | Required (present) |
| `SUPABASE_SERVICE_ROLE_KEY` | **SECRET** | Server-only admin writes and RPC; never `NEXT_PUBLIC_` | **REQUIRED — MISSING** | Required (present) |
| `SUPABASE_SECRET_KEY` | **SECRET** | Present in Vercel only; not read by app code | — | Present (obsolete-but-harmless) |
| `SUPABASE_ANON_KEY` | SERVER_ONLY | CI RLS/public-boundary probe | Missing | Present |
| `SUPABASE_PUBLISHABLE_KEY` | SERVER_ONLY | CI public-key probe | Present | Present |
| `WAITLIST_CONTACT_EMAIL` | PUBLIC | Real operator contact rendered on `/privacy`; collection disabled when absent | Present | Via `landing/vercel.json` |

`landing/lib/supabase-config.ts` refuses any key whose JWT role is not `anon`,
and rejects localhost origins when `NODE_ENV=production`.
`landing/lib/supabase-private.ts` refuses any key whose role is not
`service_role` (or an `sb_secret_` key) — so a misconfigured value fails closed
rather than degrading to a lower privilege level.

## Pipeline and CI

| Variable | Class | Purpose | GitHub | Vercel |
|---|---|---|---|---|
| `DEALSCAN_ENV` | SERVER_ONLY | `production` enables production gates | Set in workflows | — |
| `DEALSCAN_DB_BACKEND` | SERVER_ONLY | `sqlite` (default) or `supabase` | Set in workflows | — |
| `DEALSCAN_REGISTRY_PATH` | SERVER_ONLY | County registry location | Set in workflows | — |
| `DEALSCAN_SQLITE_PATH` | DEVELOPMENT_ONLY | Isolated local DB path | local | — |
| `DEALSCAN_ACTIVE_AUDIT_RUN_ID` | SERVER_ONLY | Pins the current audit run | workflow | — |
| `DEALSCAN_MIGRATIONS_DIR` | SERVER_ONLY | Migrations materialized from `main` | workflow-derived | — |
| `DEALSCAN_REPAIR_INCONSISTENT` | SERVER_ONLY | Opt-in, idempotent repair of ledgered migrations | workflow | — |
| `DEALSCAN_SUPABASE_REGION` | SERVER_ONLY | `eu-west-1` pooler shard selection | workflow | — |
| `DEALSCAN_SUPABASE_POOLER_SHARD` | SERVER_ONLY | `aws-1` Supavisor shard | workflow | — |
| `PRODUCTION_APP_URL` | SERVER_ONLY | Live app origin for smoke tests | workflow | — |

## Management / deployment credentials

| Variable | Class | Purpose | GitHub | Vercel |
|---|---|---|---|---|
| `VERCEL_TOKEN` | **SECRET** | Vercel management API for handoff/promote/verify | Present | — |
| `SUPABASE_ACCESS_TOKEN` | **SECRET** | Supabase management API for schema inspection + migrations | Present | — |
| `SUPABASE_DB_URL` | **SECRET** | Postgres DSN for `pg_dump`/`psql` backups | Present | — |
| `SUPABASE_JWT_SECRET` | **SECRET** | Legacy JWT verification; not read by app code | — | Present |

## Caching / delivery (present but not on the production path)

| Variable | Class | Purpose | Status |
|---|---|---|---|
| `KV_REST_API_URL` | SERVER_ONLY | Upstash/KV REST endpoint | Present in GitHub, unused by `main` |
| `KV_REST_API_TOKEN` | **SECRET** | KV token | Present in GitHub, unused by `main` |
| `REDIS_URL` | **SECRET** | Redis/Upstash connection | Present in GitHub and Vercel, unused by `main` |
| `REDIS_TOKEN` | **SECRET** | Upstash REST token | Not set |
| `ENABLE_CACHE_EXPORT` | OPTIONAL | Cache export flag | Not set (defaults false) |
| `ENABLE_EMAIL_DELIVERY` | OPTIONAL | Email delivery flag | Not set (defaults false) |
| `EMAIL_PROVIDER` | OPTIONAL | `console`/`resend`/`sendgrid`/`disabled` | Defaults `disabled` |
| `EMAIL_API_KEY`, `EMAIL_FROM` | SECRET / PUBLIC | Email provider credentials | Not set |

## Research-only credentials (explicitly non-authorizing)

| Variable | Class | Purpose | Status |
|---|---|---|---|
| `OPENAI_API_KEY` | SECRET, OPTIONAL | OpenAI deal enrichment — **not implemented on `main`** (proposed in unmerged PR #1) | Not set |
| `EXA_API_KEY` | SECRET, OPTIONAL | Research search — not on the production path | Not set |
| `FIRECRAWL_API_KEY` | SECRET, OPTIONAL | Research scraping — not on the production path | Not set |

`main`'s `.env.example` states these "do not authorize ingestion", and no code
on `main` imports an OpenAI/Exa/Firecrawl client. Verified by inspection:
`openai-agents` appears in `requirements.lock.txt`, but no runtime module
imports it.

## Obsolete references still present

`pipeline/.env.example` still lists `RESEND_API_KEY`, `SENDGRID_API_KEY`,
`WHOP_API_KEY` and `DISCORD_WEBHOOK_URL`. No code on `main` reads them. They
were **left in place** rather than deleted: removing a template line is a
behaviour change with no upside, and the payment/community integrations remain
listed as future roadmap items in `README.md`.

## Priority list for completion

1. **`SUPABASE_SERVICE_ROLE_KEY` — add to GitHub under exactly this name.** It
   is the single credential blocking the entire production ingestion chain. The
   value already exists in Vercel under this exact name.
2. `SUPABASE_ANON_KEY` or `NEXT_PUBLIC_SUPABASE_ANON_KEY` — add to GitHub to
   enable the CI public-boundary/RLS probe (non-blocking for writes).
3. `ENABLE_PRODUCTION_INGESTION` — a repository **variable**, not a secret. Set
   to `true` only after a green bounded production smoke run.
4. Optional cleanup: delete the legacy `SUPABASE_SERVER_ROLE_KEY` alias once
   step 1 is done. The workflows keep a fail-closed fallback to it.
