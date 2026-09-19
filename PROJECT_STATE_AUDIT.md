# DealScan Project State Audit

Audit performed 2026-09-19 from a fresh clone at
`/home/nphiri098/BUSINESSES/WHOP/dealscan`. Every claim below carries the
evidence that produced it. Status vocabulary: **VERIFIED** (directly observed),
**LIKELY** (strong indirect evidence), **ASSUMPTION** (inferred, unconfirmed),
**UNKNOWN**, **BLOCKED** (external access/credential required),
**REQUIRES MANUAL VERIFICATION**.

Where this audit disagrees with earlier project docs, the disagreement is
recorded rather than smoothed over.

## Repository

- GitHub repository: `doriaphiri82-glitch/dealscan` — **VERIFIED** (GitHub API `/repos` returned 200; token resolves to `doriaphiri82-glitch`)
- Owner: `doriaphiri82-glitch` — **VERIFIED**
- Visibility: **public** — **VERIFIED** (`private: false`)
- Default branch: `main` — **VERIFIED**
- Current branch: `main` at `8ebbc59` — **VERIFIED**
- Latest commit on `main`: `8ebbc59 Merge pull request #17 from doriaphiri82-glitch/project-failure-analysis-52b04`, committed 2026-09-11 16:43 +0200 — **VERIFIED**
- Working tree at audit start: clean; 42 remote refs present — **VERIFIED**
- Branch protection on `main`: **absent** (`HTTP 404 "Branch not protected"`) — **VERIFIED**
- Local clone state at audit start: **stale by 395 commits** (local `main` was `220ca9b`, 2026-09-04). Fast-forwarded to `origin/main` non-destructively (`git merge --ff-only`; local `main` was a direct ancestor, so nothing was discarded) — **VERIFIED**

### Open pull requests (all mergeable state recorded as of audit)

| PR | Head branch | Head SHA | Mergeable state | Files | +/- |
|---|---|---|---|---|---|
| #18 | `manus/dealscan-production-repair` | `1f6d9abb` | `clean` | 8 | +54 / −20 |
| #9 | `fix/verified-etl-publication-gate` | `c1282750` | `dirty` | 7 | +105 / −17 |
| #5 | `feat/supabase-db-layer-3` | `3dfa7f45` | `dirty` | 3 | +237 / −31 |
| #1 | `feat/openai-deal-intelligence` | `b23bbabf` | `dirty` | 26 | +959 / −737 |

Open issues: the same four entries (PRs are counted as issues by the API). No
non-PR issues exist — **VERIFIED**.

PR #18 is the only cleanly mergeable one and is the newest commit in the
repository (2026-09-12). PRs #9/#5 were superseded by work already merged to
`main` (Supabase routing now lives in `scrape.yml` and `production-smoke.yml`).
PR #1 is 46 commits behind and describes an OpenAI enrichment feature that is
**not** referenced anywhere in `main`'s runtime code — **VERIFIED** by absence
of `openai` imports outside `requirements.lock.txt`.

### Repository branch sprawl (an operational risk, not a code defect)

42 remote refs, of which these are byte-identical duplicates pointing at the
same SHA `f77efb8`: `feat/supabase-db-layer`, `-2`, `-4`, `-final`, `-final2`,
`-final3`, `-final4`, `feat/supabase-production-database-layer` `-v2` … `-v7`,
`feat/supabase-production-db`, `tmp`. Likewise `fix/supabase-public-read-policy`
`-2`…`-5`, `-final`, `-final2`, `-final3` are all `9ceb2a3`. This is evidence of
an agent retrying the same change under new branch names — **VERIFIED**. None
are merged; they are inert but should be pruned. No branch deletion was
performed by this audit.

## Application

- Framework: Next.js 15.5.25 (App Router) — **VERIFIED** (`landing/package.json`)
- Language: TypeScript 5.4 — **VERIFIED**
- Package manager: npm (`package-lock.json` present; `vercel.json` sets `installCommand: "npm ci"`) — **VERIFIED**
- Build system: `next build`; Node pinned to `22.x` in both `package.json#engines` and Vercel — **VERIFIED**
- Main application entry: `landing/app/layout.tsx` + `landing/app/page.tsx` — **VERIFIED**
- Vercel root directory: `landing` — **VERIFIED** two ways (workflow annotation `rootDirectory: "landing"`; `landing/vercel.json` + `landing/.vercel/project.json`)
- Middleware: `landing/middleware.ts` — verifies the Supabase session server-side, **fails closed** on error, 401s `/api/admin/*`, redirects pages to `/auth?next=…` — **VERIFIED** (read in full)
- Routes/pages present — **VERIFIED** (`git ls-tree` of `origin/main`):
  - `/` `landing/app/page.tsx`
  - `/privacy`
  - `/auth` (+ `/auth/callback`)
  - `/dashboard`
  - `/deals`, `/deals/[apn]`
  - `/compare`
  - `/my-dealscan`
  - `/admin/coverage`
- API routes/server actions — **VERIFIED**:
  - `landing/app/api/health/route.ts`
  - `landing/app/api/deals/route.ts`, `landing/app/api/deals/[apn]/route.ts`
  - `landing/app/api/waitlist/route.ts`
  - `landing/app/api/admin/coverage/route.ts`
- Components: `landing/components/*` plus route-local components (`InvestorDashboard.tsx`, `Workspace.tsx`, `SignOutButton.tsx`) — **VERIFIED**
- Styling system: Tailwind CSS 3.4 + `landing/app/globals.css` — **VERIFIED**
- State management: no store library; React hooks + server components. `landing/lib/use-parcel.ts` is the only custom hook — **VERIFIED**
- Existing libraries: `@supabase/ssr` 0.7, `@supabase/supabase-js` 2.57, `server-only`; dev: `vitest` 4.1.11, `@electric-sql/pglite` 0.5.8, `react-test-renderer` — **VERIFIED**
- Backend-adjacent runtime libs: `landing/lib/supabase-config.ts` (public key validation), `supabase-private.ts` (server-only service key + fixed RPC allowlist), `safe-redirect.ts`, `request-body.ts`, `verified-facts.ts`, `public-deals.ts`, `county-health.ts`, `parcels.ts` — **VERIFIED**

### Pipeline (Python)

- `pipeline/main.py` is the CLI orchestrator; `scheduler.py` delegates to it — **VERIFIED**
- Scrapers: ArcGIS REST and flat-file adapters behind `scrapers/adapter.py` — **VERIFIED**
- Persistence: two backends behind one interface — `database_sqlite.py` (default/CI) and `database_supabase.py` (selected only by `DEALSCAN_DB_BACKEND=supabase`) — **VERIFIED**
- `pipeline/validation/` is the production gate suite: `production_preflight.py`, `production_smoke.py`, `supabase_handoff.py`, `vercel_handoff.py`, `supabase_pooler_url.py`, `etl_validator.py`, `publication.py`, `gates.py`, `evidence.py`, `vacancy.py`, `live_validator.py`, `national_validator.py` — **VERIFIED**
- Test count expectation recorded in `docs/post-merge-status.md`: 487 passing — **REQUIRES MANUAL VERIFICATION** (re-run during this audit; see Final Audit)

## Database

Authoritative source: the `dealscan-supabase-handoff` Check annotation from run
`34533907928` (2026-09-10T21:47:07Z, commit `6e12e2a1`), which used
`SUPABASE_ACCESS_TOKEN` against the real project. Everything here is **VERIFIED**
by that report unless noted.

- Supabase project: `nyvvwwwqpbrkzyqbtvsx`, region `eu-west-1`, status `ACTIVE_HEALTHY`
- Auth probe: `session_5432=ok transaction_6543=ok` (read-only `select 1`)
- Migrations: `applied_this_run: []`, `pending: []`, `inconsistent: []` → **all reviewed migrations are already applied**
- Schema contract: `status: passed`, `missing: []`; write contract: `passed`
- Tables present (10): `comps`, `counties`, `deals`, `deliveries`, `ingestion_records`, `ingestion_runs`, `properties`, `subscribers`, `waitlist`, `waitlist_request_limits`
- RLS: `pg_policies_public = 4`; `pg_triggers_public = 15`; `pg_functions_public = 30`
- Triggers include real publication gates, e.g. `deals_require_a_typed_validation`, `deals_require_comparable_arithmetic`, `deals_require_publication_evidence`, `deals_require_raw_source_evidence`, `deals_bump_revision`, and `*_revoke_changed_deals` invalidation triggers on `comps`, `counties`, `ingestion_records`, `ingestion_runs`, `properties`
- Migration ledger exists (`ledger_present: true`)

### Live row counts (2026-09-10T21:47Z) — the most important single finding

| Table | Rows |
|---|---|
| `counties` | 3 |
| `properties` | 250 |
| `ingestion_records` | 500 |
| `ingestion_runs` | 4 |
| **`deals`** | **0** |
| `comps` | 0 |
| `subscribers` / `deliveries` / `waitlist` | 0 / 0 / 0 |

Interpretation, evidenced by `docs/engineering-progress.md` and
`docs/post-merge-status.md`: the El Paso CAD parcel layer publishes assessed and
market values but **no asking price**, so no parcel can satisfy the comparable-
arithmetic gate that `deals` enforces. `deals: 0` is therefore a **source-data
property, not a regression**. It is nonetheless the central product risk: the
core promise ("find profitable land deals") cannot be fulfilled from the one
source currently wired up.

The 2026-09-10 run was a bounded 250-record validation, not a backlog. There is
no evidence any scheduled ingestion has ever run — see Workflows below.

### Migrations on disk

14 ordered files under `supabase/migrations/` (2026-09-05 → 2026-09-07) covering
production schema, public read policies, `updated_at` search-path hardening,
column restriction, ingestion integrity, publication-evidence gate, operational
contracts, raw-source publication, subscriber consent, comparable arithmetic,
typed validation evidence and audit-status vocabulary — **VERIFIED**
(`git ls-files supabase/migrations`).

## Vercel

Authoritative source: the `dealscan-vercel-handoff` Check annotation from run
`34168223163` (2026-09-07T22:54:29Z). **VERIFIED** unless noted.

- Project: `dealscan`, id `prj_6IPIDs5GWrzm5K26ODgrnHL80IUE`
- Team: `doriaphiri82-4774s-projects` (`team_p1f0pRmv2Pm0cbvo02banPIE` in the checked-out `.vercel/project.json`)
- Framework: `nextjs`; root directory `landing` (matches); Node `22.x` (matches)
- Git integration: `github`, repo `dealscan`, production branch `main`
- Production environment variables: `missing: []` — complete (see Environment below)
- Production deployment then live: `dpl_DmMLzf3v3aTVQhp2YjNgj6B5k8RE`, state `READY`, commit `1b8c5fb9`
- Promotion action: `none`, reason `already_current`
- Live checks then: `/` → 200, `/privacy` → 200 (operator contact matches), `/api/health` → 200 with `database: ok`
- Production alias: `https://dealscan-omega.vercel.app`

### Currency of that evidence

The annotation is dated 2026-09-07 and the promoted commit is `1b8c5fb9`; `main`
has since moved to `8ebbc59` (2026-09-11). Production therefore runs a
**stale-but-reviewed** commit — **VERIFIED** by SHA comparison. Whether
`/api/health` still returns 200 today is **UNKNOWN** from this sandbox (see
Production reachability). No Vercel management credential exists in this
environment, so the project could not be re-inspected live.

### Supabase Auth configuration

`site_url: https://dealscan-omega.vercel.app`, `callback_allowed: true`,
`localhost_urls_present: false`, `fix_applied: true` — **VERIFIED**. Auth
redirects will not work from `localhost` until a local URL is allow-listed;
correct for production, inconvenient for local development only.

## Workflows and automation

Seven workflows are registered and `active` — **VERIFIED** (`/actions/workflows`).

| Workflow | ID | Trigger | Last observed state |
|---|---|---|---|
| `dealscan-ci` | 349791784 | push/PR on `pipeline/**`, `landing/**`, `supabase/**`, workflows | re-dispatched by this audit |
| `dealscan-pipeline` | 346517393 | cron every 15 min + dispatch | **`completed / skipped` on every scheduled run since at least 2026-09-16** |
| `dealscan-production-smoke` | 351029384 | push to a pinned arena branch + dispatch | last runs `failure` (2026-09-11) |
| `dealscan-supabase-handoff` | 351786419 | push to a pinned arena branch + dispatch | last run `success` (2026-09-10) |
| `dealscan-vercel-handoff` | 351681740 | push to a pinned arena branch + dispatch | last run `success` (2026-09-07) |
| `dealscan-source-discovery` | 350966551 | `workflow_dispatch` only | **no runs ever recorded** |
| `county-source-smoke` | 350108033 | — | last runs `failure` (2026-09-04); file no longer exists on `main` |

### Why scheduled ingestion never runs — VERIFIED root cause

`scrape.yml` gates its only job:

```yaml
if: github.event_name == 'workflow_dispatch' || vars.ENABLE_PRODUCTION_INGESTION == 'true'
```

`ENABLE_PRODUCTION_INGESTION` does not exist (repository variables: `total_count: 0`),
so every cron run resolves to `skipped`. Confirmed against run `35352711792`
(2026-09-18T13:51:45Z): one job `ingest`, `conclusion: skipped`, created and
updated one second apart. This is a **deliberate, documented rollout gate**
("enable cron only after a real production smoke pass"), not a defect — but it
means scheduled ingestion has never produced production data. **VERIFIED**.

### The production-smoke workflow is currently unrunnable by schedule

Its only non-dispatch trigger is `push: branches: ['arena/01a08d60-dealscan']`,
a branch pinned by a previous agent session. Nothing pushes to that branch now,
so the workflow can only be run by manual dispatch. The same pattern applies to
`supabase-handoff` (`arena/01a07d76-dealscan`) and `vercel-handoff`
(`arena/01a07d76-dealscan`). These are inert, session-scoped pins — **VERIFIED**
by reading each workflow's `on:` block.

### Parseability

`dealscan-pipeline` resolves by its declared `name` and records real job
structure rather than `startup_failure`, so the earlier double-quoted-literal
parse bug documented in `docs/post-merge-status.md` is fixed on `main` —
**VERIFIED**.

## Production reachability — BLOCKED from this sandbox

| Check | Result |
|---|---|
| `https://dealscan-omega.vercel.app/api/health` (443) | TCP connect timeout; `HTTP 000` after 12 s |
| same host over port 80 | timeout |
| DNS resolution | resolves to `216.198.79.67`, `64.29.17.67` (Vercel anycast) |
| `https://vercel.com` | HTTP 200 |
| `https://ai-sdk.dev` (Vercel-hosted) | HTTP 200 |
| `https://supabase.com`, `https://nextjs.org`, `https://api.github.com` | HTTP 200 |
| `dealscan-ehcdv5nwl-….vercel.app` (deployment host) | HTTP 302 (Vercel deployment SSO) |

General internet egress works; only the `dealscan-omega` alias fails, and it
fails at TCP connect rather than at HTTP. This matches the transport-restriction
note already recorded in `docs/production-handoff.md`. **Conclusion: this
sandbox cannot distinguish "egress policy" from "production outage". Reported as
BLOCKED / REQUIRES MANUAL VERIFICATION.** No claim is made about current
production health.
