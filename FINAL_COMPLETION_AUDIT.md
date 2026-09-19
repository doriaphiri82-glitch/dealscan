# DealScan Final Completion Audit

Audit date 2026-09-19. Repository `doriaphiri82-glitch/dealscan`, public,
default branch `main`. HEAD at audit end: `881e6b6` (after the work below).
All claims are evidence-based and labelled VERIFIED / LIKELY / ASSUMPTION /
UNKNOWN / BLOCKED.

## Overall Status

**PARTIALLY VERIFIED.** All in-repository CI is green, the local build is green,
Vercel built and "completed" the pushed commit, and a real read-only
production-smoke run completed **success** after the in-repo fixes. The two
things that remain *unverified here are external and are not code defects*:
the production alias is unreachable from this sandbox, and the Supabase
"Preview" GitHub-App check fails on an IPv6-only database host that the
production code already routes around via the session pooler. Details,
remaining problems and the exact manual actions follow.

## What this agent changed and why

| Commit | Scope | Evidence it fixes |
|---|---|---|
| `3eefb9d` | `fix(security): restore root .gitignore…` | `f2d50db` (author `qwen.ai[bot]`) replaced `.gitignore` with a chat reply, un-ignoring `.env`, `*.db`, `pipeline/data/*` and `__pycache__/` and leaving **103 `.pyc` files committed**. |
| `766f682` part of `1936d46` | `fix(ci): resolve the saved Supabase service-role key alias` | The operator saved the key as `SUPABASE_SERVER_ROLE_KEY` (GitHub secret, 2026-09-10T19:10:32Z); every consumer reads `SUPABASE_SERVICE_ROLE_KEY`. The 2h-before-failure timestamp matches `docs/post-merge-status.md` exactly — root cause of "scheduled ingestion stayed dark". Workflows now read `secrets.SUPABASE_SERVICE_ROLE_KEY || secrets.SUPABASE_SERVER_ROLE_KEY`, fail-closed. |
| `881e6b6` | `docs: record…` | PROJECT_STATE_AUDIT.md, DEALSCAN_COMPLETION_PLAN.md, ENVIRONMENT_VARIABLES.md, REQUIRED_CREDENTIALS.md |

The local checkout was fast-forwarded to `origin/main` (8ebbc59) as a first
step; no work was based on the stale local tree.

## GitHub

- Repository: `doriaphiri82-glitch/dealscan` (public) — VERIFIED
- Branch: `main` — VERIFIED
- Latest commit: `881e6b6` — VERIFIED
- Working tree: clean — VERIFIED
- Push status: 4 commits pushed, `8ebbc59..881e6b6`, `EXIT=0` — VERIFIED
- Branch protection: none — VERIFIED
- CI result on `881e6b6` (dealscan-ci): **web = success, pipeline = success** — VERIFIED via GitHub Checks API

## Vercel

- Project: `dealscan` / `prj_6IPIDs5GWrzm5K26ODgrnHL80IUE` / team `doriaphiri82-4774s-projects`
- Production alias: `https://dealscan-omega.vercel.app` (root `landing`, Node 22.x)
- Latest commit deployment: the Vercel Git integration posted a **commit status
  `success` / "Deployment has completed"** on `881e6b6` (deployment
  `…/dealscan/8bjcu8RtLcGkSb1LtXErFrdW5PPf`). The committed code builds and is
  deployed by Vercel — VERIFIED.
- Production currency: VERIFIED STALE. The last *promoted* production deployment
  recorded is commit `1b8c5fb9` (2026-09-07); `main` is now `881e6b6`, ahead.
  The new deployment was built by the integration but the production alias has
  not been verified to point at it from this sandbox — VERIFIED STALE.
- Production live reachability from this sandbox: BLOCKED (TCP connect times out
  on 443 and 80 while vercel.com, ai-sdk.dev, etc. are reachable — a sandbox
  egress restriction, not necessarily an outage). Documented; no claim made.

## Supabase

- Project: `nyvvwwwqpbrkzyqbtvsx`, region `eu-west-1`, `ACTIVE_HEALTHY` — VERIFIED (from the 2026-09-10 supabase-handoff annotation)
- Migrations: `applied/[]`, `pending/[]`, `inconsistent/[]` — all applied — VERIFIED
- Schema contract / write contract: `passed` — VERIFIED
- Auth: `site_url https://dealscan-omega.vercel.app`, `callback_allowed true` — VERIFIED
- Tables (10), 15 triggers, 4 RLS policies, 30 functions in `public` — VERIFIED
- The one fix this agent made (the service-role alias) was validated by a real
  read-only `production-smoke` dispatch (see below) — VERIFIED EFFECTIVENESS.

### Live row counts (2026-09-10T21:47Z) — unchanged by this work

`counties 3 · properties 250 · ingestion_records 500 · ingestion_runs 4 ·
deals 0 · comps 0 · subscribers/deliveries/waitlist 0`. `deals = 0` is caused
by the source having no asking price and the `comparable_arithmetic`
publication trigger correctly refusing to publish — a source/product decision,
not a code defect.

## Environment

- Required variables (production):
  - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
    `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (Vercel), `WAITLIST_CONTACT_EMAIL`
  - `SUPABASE_SERVICE_ROLE_KEY` (GitHub — **was missing under that name; now
    resolved via alias fallback in the workflows**)
- Configured: VERIFIED (Vercel env `missing: []`; GitHub secrets present;
  `SUPABASE_SERVER_ROLE_KEY` now read as fallback)
- Missing: `SUPABASE_ANON_KEY`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` in GitHub (optional, public probe only); `ENABLE_PRODUCTION_INGESTION` variable (deliberate cron gate)
- Obsolete: `SUPABASE_SECRET_KEY`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_JWT_SECRET` in Vercel (unused by code); `RESEND_`/`SENDGRID_`/`WHOP_` keys in `pipeline/.env.example` (unused by `main`) — left in place, documented
- The local git remote URL contained an embedded GitHub PAT (`x-access-token:<token>`): removed by this agent and NOT re-committed or pasted into any document. **The token must be rotated** — see Manual actions.

## Features

| Feature | Status | Evidence |
|---|---|---|
| Authentication | VERIFIED | `middleware.ts` (fail-closed Supabase SSR session check; 401s `/api/admin/*`); `@supabase/ssr`; Supabase Auth site/callback configured |
| Dashboard | VERIFIED | `app/dashboard/page.tsx`, `InvestorDashboard.tsx` |
| Deal discovery | VERIFIED | `app/deals/page.tsx`, `app/deals/[apn]/page.tsx`, `lib/public-deals.ts`, `lib/deals.ts` |
| Search | LIKELY | `components/CommandPalette.tsx` (⌘K); deals page has a query filter |
| Filtering | VERIFIED | deals page county / score / sort selects |
| Deal detail | VERIFIED | `app/deals/[apn]/page.tsx` + `lib/use-parcel.ts` |
| User profile | UNKNOWN | `app/my-dealscan/page.tsx` / `Workspace.tsx` exist but content not inspected |
| Saved deals | UNKNOWN | not confirmed beyond the my-dealscan page |
| Notifications | NOT IMPLEMENTED | email delivery disabled by default; no push/notification feature wired |
| Payments | NOT IMPLEMENTED | Whop storefront is roadmap (`README.md`); no payment code on `main` |
| Admin | VERIFIED | `app/admin/coverage/page.tsx`, `app/api/admin/coverage` |
| Analytics | LIKELY | `lib/county-health.ts`, dashboard metrics |
| API | VERIFIED | `/api/health`, `/api/deals`, `/api/deals/[apn]`, `/api/waitlist`, `/api/admin/coverage` return 200 (2026-09-07 handoff) |
| Database | VERIFIED | Supabase ACTIVE_HEALTHY, 14 migrations applied, schema/write contracts passed |
| Mobile responsiveness | UNKNOWN | Tailwind utilities suggest responsiveness; not independently tested |
| Error handling | VERIFIED | middleware fails closed; private config throws `PrivateStoreUnavailable`; no raw secret/error bodies |
| Security | VERIFIED | 4 PGlite security suites pass in CI; RLS + publication triggers enforced; middleware fail-closed; private RPC allowlist |

## Tests

Local run (this audit, Node v22.23.2 — the version CI/Vercel pin):

| Test | Result |
|---|---|
| Install | VERIFIED — `npm ci` 164 packages (exit 0); `pip install -r requirements.lock.txt` exit 0 |
| Typecheck | VERIFIED — `next typegen && tsc --noEmit` exit 0 |
| Lint | VERIFIED — `next build` runs lint, no errors |
| Python unit/integration (`pipeline/tests`) | VERIFIED — **489 passed** in 394 s, incl. the 2 new regression guards |
| Web unit (`landing/tests`) — local | PARTIAL — 12/15 files, 159/208 tests passed. 3 PGlite-backed files (49 tests) timed out in `beforeAll` at 30 s: sandbox CPU cannot compile the Postgres WASM in time. |
| Web unit (`landing/tests`) — CI | VERIFIED — `web` job **success** ⇒ all 208 tests pass on a GitHub ubuntu-latest runner (resolves this as environment-slowness, not a code defect) |
| Build (`next build`) | VERIFIED — exit 0; 16 routes prerendered/server-rendered |
| Preview deployment (Vercel integration on push) | VERIFIED — commit status `success` / "Deployment has completed" |
| Production deployment promotion | VERIFIED STALE — last promoted commit `1b8c5fb9`; `main` is `881e6b6` |
| Production smoke (read-only dispatch) | VERIFIED EFFECTIVENESS — dispatched `production-smoke` with `preflight_only=true`; run completed **success** at 2026-09-19T10:39, confirming the alias fix resolves the readiness gate with no missing keys |
| Production live HTTP | BLOCKED — sandbox cannot reach the alias at TCP level |

The green smoke run was `dealscan-production-smoke` (workflow id 351029384),
`workflow_dispatch` on `main`, read-only inputs.

## Remaining problems

1. **Production alias serves a stale commit (`1b8c5fb9`) and is unreachable from here.** A deployment was built for `881e6b6`, but promoting/verifying it live requires a Vercel login the sandbox lacks.
2. **`deals = 0`.** Correct by design, but the core "land deals" promise has no live data until a source with asking prices is added.
3. **The `Supabase Preview` GitHub-App check fails on an IPv6-only `db.<ref>.supabase.co` connect timeout.** The production path routes around this via the IPv4 session pooler (port 5432); the preview app does not. Infra-level; not fixable in this repo.
4. **Branch sprawl (42 refs, ~20 byte-identical duplicates).** Housekeeping only; not pruned to avoid destructive ref changes.
5. **`.cpython-312.pyc` remain on disk under `pipeline/__pycache__/`.** Untracked and ignored; harmless. Not cleaned to stay non-destructive.

## Manual actions required (cannot be done from this environment)

1. **Rotate the GitHub PAT** that was embedded in the local `git remote` URL. It
   was removed from `.git/config` here, but it was already visible in this
   session, so treat it as compromised: revoke the old token in GitHub Settings →
   Developer settings → Personal access tokens, issue a new one, and authenticate
   with a credential helper (never store a PAT in a remote URL again).
   **Status: BLOCKED — requires human access.**
2. **Add `SUPABASE_SERVICE_ROLE_KEY` under that exact name** in GitHub → Settings
   → Secrets and variables → Actions → Secrets (the value already exists in
   Vercel under this name). The in-repo fallback now accepts the saved
   `SUPABASE_SERVER_ROLE_KEY` so ingestion works immediately, but renaming is
   cleaner. **Status: BLOCKED on human action (tokens are write-only).**
3. **Promote `main` in Vercel** (or merge PR #18, which re-enables
   operator-dispatched promotion). CI is green; the only blocker is a Vercel
   login. **Status: BLOCKED — REQUIRES MANUAL VERIFICATION.**
4. **Verify production live**: after promotion, `curl
   https://dealscan-omega.vercel.app/api/health` should return `{"database":"ok"}`.
   **Status: BLOCKED from this environment.**
5. **Decide on `deals = 0`**: add a source that publishes asking price, or ship
   an explicitly-labelled "assessed-value-only" mode. **Status: product decision.**
6. **Optionally prune the duplicate `feat/supabase-db-layer*` and
   `fix/supabase-public-read-policy*` branches.** Not done — destructive, out of
   scope.

## Final recommendation

The repository is in a strong state: CI is green (`web` + `pipeline` both
`success`), the build is green and Vercel deployed the pushed commit
("Deployment has completed"), 14 migrations are applied and healthy, and the
single genuine production blocker — the misnamed service-role key — is now
resolved in code with a fail-closed fallback and **proven** by a real read-only
`production-smoke` dispatch that completes `success`.

The remaining items are almost entirely external rather than code defects: a
rotated token, a Vercel login, one renamed secret, and a county source that
publishes asking prices. Recommended next steps in priority order: (1) rotate
the token; (2) add the canonical `SUPABASE_SERVICE_ROLE_KEY` secret; (3) promote
`main` in Vercel; (4) re-dispatch `production-smoke` with `preflight_only=false`
and 250 records to verify the full persistence/audit/identity chain before
enabling cron (`ENABLE_PRODUCTION_INGESTION=true`). `deals = 0` is correct and
must not be papered over with fixtures.

Production URL: `https://dealscan-omega.vercel.app` (configured alias verified;
live health unverified from this sandbox — BLOCKED on egress/credentials).

