# Post-merge status — 2026-09-06 (session `arena/01a0759b-dealscan`)

This file is a fresh, session-scoped record. It replaces the previous local-only
post-merge note (commit `5098f87` on the prior session branch, never pushed and
absent from this checkout). Nothing here claims production ingestion, migration,
authorization or deployment success.

## Verified in this sandbox (commit `afee487` = `origin/main`, PR #10 merge)

- Working tree clean; HEAD equals `origin/main` exactly.
- GitHub token works for code push, PRs, runs/checks and environment reads.
- **421 Python tests passed** (`python -m pytest -q`, locked Python 3.11 venv).
- **208 web/database/UI tests passed** (`npm test`, Node 22.22.3, `npm ci`).
- Typecheck (`next typegen && tsc --noEmit`) and production build passed;
  16 routes listed, middleware bundle built.
- `python -m compileall -q pipeline` passed.
- `npm audit`: **0 vulnerabilities**.
- Local source/API audit of the merged tree: middleware fail-closed auth,
  verified-only PostgREST public reads with RLS plus explicit allowlist
  projection, bounded/origin-checked waitlist RPC, admin coverage RPC with
  server-side role check, no mock/demo/substitute data in public paths.

## GitHub-observed evidence

- Merge CI on `main` (`afee487`) succeeded:
  https://github.com/doriaphiri82-glitch/dealscan/actions/runs/34016161996
- Fresh read-only readiness on this branch, commit `adff79f`,
  2026-09-06T07:38:56Z (run 34019687589, Check annotation retargeted push
  trigger working as intended):
  - **configuration: failed** — now missing **only** `SUPABASE_SERVICE_ROLE_KEY`.
    `SUPABASE_URL` and a public Supabase key are present in the Production
    environment, so secret configuration has begun since the previous run.
  - **deployment: failed, HTTP 503** `deployed_health_unavailable` — the
    runner now reaches the deployed application (the earlier HTTP 500 /
    middleware crash is gone); production health returns 503 because the web
    app still has no public Supabase configuration.
  - **source: passed** (read-only technical probe, unchanged): El Paso query
    `legal_acreage > 0 AND imprv_val = 0`, 138,863 matching records,
    5 samples across 3 pages, object-ID field `ObjectID_1`,
    `ingestion_authorized:false`.
  - **database / public_boundary: not checked** (service key missing);
    `production_writes_performed:false`; `ingestion_status:"not_attempted"`.
- CI on this branch and its PR passed:
  https://github.com/doriaphiri82-glitch/dealscan/actions/runs/34019687689 and
  https://github.com/doriaphiri82-glitch/dealscan/actions/runs/34019725407.
- Previous readiness annotation (prior branch, commit `837aef9`,
  2026-09-06T06:10:25Z) reported all three required secrets missing and the
  deployment at HTTP 500; that is superseded by the fresh run above.
- `Production` environment still has **no protection rules** and no branch
  policy restriction (read via API, 2 environments exist).
- Legacy `county-source-smoke` workflow references
  `.github/workflows/county-smoke.yml`, which does not exist on `main`; it is a
  leftover from an older branch. Harmless, but it cannot run from `main`.

## Operator-reported production observations (not agent-verified)

The sandbox cannot complete TLS handshakes to `*.vercel.app`, the ArcGIS source,
or GitHub blob/log hosts (`SSL_ERROR_SYSCALL` / EOF). TLS was not weakened. The
operator reported after the merge that:

- `/` and `/privacy` load (previous middleware crash resolved; privacy shows
  `doriaphiri82@gmail.com`).
- `/api/health` → `database: not-configured` (web app has no public Supabase env).
- `/api/deals` → unavailable, with **no substitute records** (correct contract).
- `/api/admin/coverage` → requires authentication (correct contract).

These must be re-confirmed by a GitHub readiness run before any write step;
a passing source probe is not deployment verification.

## Re-confirmed access blockers (unchanged)

- `403 Resource not accessible by integration` for repository/environment
  secrets and variables, and for manual `workflow_dispatch`.
- No Supabase, Vercel or DealScan credentials exist in this sandbox environment.
- Actual production Supabase schema, migration state and the real 250-record
  ingestion remain **unverified**. Scheduled ingestion stays disabled.

## Operator actions still required (no credentials in chat)

Per `docs/production-runbook.md` and `docs/production-handoff.md`:

1. Supply the still-missing matching `SUPABASE_SERVICE_ROLE_KEY` in the GitHub
   **Production** environment (`SUPABASE_URL` and a public key appear to be
   supplied already per the 07:38Z readiness run) and add environment
   protection rules before any write-enabled dispatch.
2. In Vercel: verify root `landing`, Node 22, and set the matching
   `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` (production
   health currently 503s for lack of them), plus separate server-only Supabase
   secrets, `WAITLIST_CONTACT_EMAIL=doriaphiri82@gmail.com` (already in
   versioned `vercel.json`), and Supabase Auth site/callback URLs for
   `https://dealscan-omega.vercel.app`.
3. Back up/inspect the real Supabase schema, then apply the unapplied ordered
   migrations in `supabase/migrations/` before any ingestion.
4. Run read-only readiness (a push to this session's branch triggers it now
   that the workflow pin was retargeted), review source authority, then
   dispatch `dealscan-production-smoke` with `preflight_only=false`,
   `county_id=el_paso_tx`, `max_records=250`,
   `app_url=https://dealscan-omega.vercel.app`.
5. Verify that exact run's persistence/audit/raw/normalized/hash/identity chain
   and deployed API agreement before any cron enabling
   (`ENABLE_PRODUCTION_INGESTION=true`).
