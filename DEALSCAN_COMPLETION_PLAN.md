# DealScan Completion Plan

Derived from `PROJECT_STATE_AUDIT.md`. Ordered by what actually blocks value,
not by what is most interesting to build. Nothing here is a rewrite: the codebase
is mature (489 Python tests, 208 web tests, 14 applied migrations, a complete
Vercel environment) and most of the work is **configuration and truth-telling**,
not new features.

## P0 — Critical (blocks startup, deployment, auth, data or security)

### P0-1 — `SUPABASE_SERVICE_ROLE_KEY` is now present in GitHub under the canonical name
- **Evidence:** GitHub Actions now has both `SUPABASE_SERVICE_ROLE_KEY` (canonical
  name, created 2026-11-10T10:18:27Z) and `SUPABASE_SERVER_ROLE_KEY` (legacy
  alias). Workflows read
  `secrets.SUPABASE_SERVICE_ROLE_KEY || secrets.SUPABASE_SERVER_ROLE_KEY`
  (fail-closed). Production `/api/health` returns `{"status":"ok","service":"dealscan-web","database":"ok","database_origin":"https://nyvvwwwqpbrkzyqbtvsx.supabase.co"}`.
- **Impact:** the entire production ingestion chain now has its canonical
  credential. The `started_at` timestamp fix in the ETL pipeline (persistence.py,
  database_supabase.py, database_sqlite.py) is re-verified by 99 local tests.

### P0-2 — Root `.gitignore` was replaced by an LLM chat reply, un-ignoring secrets and data
- **Evidence:** commit `f2d50db` (author `qwen.ai[bot]`, 2026-09-11) replaced the whole file with the sentence "Nothing needs to be added to .gitignore since the only modified file is a Python test file…". `git show 63ad770:.gitignore` shows the real patterns. Consequences: `.env`, `.env.*`, `*.db`, `*.sqlite`, `pipeline/data/*`, `landing/data/*`, `__pycache__/` all stopped being ignored, and **103 `.pyc` files became tracked**. `pipeline/data/dealscan.db` was previously covered by `*.db`.
- **Impact:** the next `git add -A` would have staged real waitlist emails, the SQLite database and any local `.env`. This is the single most dangerous finding.
- **Status:** **FIXED** — restored the pre-corruption patterns, added `.venv*/` and `.arena/`, and added `test_root_gitignore_still_protects_secrets_and_runtime_data`, which fails CI if any protection disappears or if prose appears in the file.

### P0-3 — 103 compiled Python artifacts tracked in git
- **Evidence:** `git ls-files | grep -c '\.pyc$'` → 103.
- **Impact:** noise, merge conflicts, stale bytecode shipped around, and the direct symptom of P0-2.
- **Status:** **FIXED** — removed from the index with `git update-index --force-remove`; the restored `.gitignore` keeps them out.

### P0-4 — Production serves main (fixed)
- **Evidence:** The GitHub product deployment (`7679597411`, environment `production`, commit `05c302a`) is the latest on `main`. Production `/api/health` returns `{"status":"ok","service":"dealscan-web","database":"ok","database_origin":"https://nyvvwwwqpbrkzyqbtvsx.supabase.co"}` (2026-11-10T10:24:35 GMT).
- **Impact:** all commits merged to `main` are now live. No stale-commit risk.

### P0-5 — Production health is verified (fixed)
- **Evidence:** `curl https://dealscan-omega.vercel.app/api/health` returns
  HTTP 200 with `{"status":"ok","service":"dealscan-web","database":"ok","database_origin":"https://nyvvwwwqpbrkzyqbtvsx.supabase.co"}` (2026-11-10T10:24:35 GMT). Supabase connectivity is confirmed.
- **Impact:** the production web tier is healthy; no surgery or manual effort
  required. The only remaining question is the product data (`deals = 0`), which
  is a source/product decision, not a code defect.

### P0-6 — A GitHub personal access token is embedded in the local git remote URL
- **Evidence:** `git remote -v` prints `https://x-access-token:<token>@github.com/…`. The value is **not** reproduced in any document, log or commit produced by this audit.
- **Impact:** anything able to read this machine, or the shell history, holds a token carrying `repo`, `admin:org`, `workflow`, `delete_repo` and `write:packages` (verified via the `x-oauth-scopes` response header). The token itself is not a git-committed secret, but it should be rotated and moved into a credential helper.
- **Status:** **OPEN — owner action: rotate the token**, then set the remote to the plain HTTPS URL and authenticate via a credential helper. The URL form must never be committed or pasted anywhere.

## P1 — Core product

### P1-1 — The core promise has no queryable data: `deals = 0`
- **Evidence:** 2026-09-10 live counts: `counties: 3`, `properties: 250`, `ingestion_records: 500`, **`deals: 0`**, `comps: 0`. Explanation recorded in `docs/engineering-progress.md`: the El Paso CAD layer exposes assessed/market values but **no asking price**, and `deals` is protected by `comparable_arithmetic` and publication-evidence triggers, so nothing can be published.
- **Impact:** DealScan's headline claim is "AI finds profitable land deals". With one source that has no asking price, the product cannot produce a single deal — the gates are working correctly and correctly refusing to invent data.
- **Status:** **OPEN — a product/data problem, not a code defect.** Deliberately **not** worked around: inserting fixtures or relaxing the arithmetic gate would fabricate financial evidence on a public site. The real next step is a second source that publishes asking price, or an explicitly-labelled "assessed-value-only" mode.

### P1-2 — Scheduled ingestion has never run and is deliberately disabled
- **Evidence:** `ENABLE_PRODUCTION_INGESTION` is unset (repository variables: `total_count: 0`); run `35352711792` shows `ingest: skipped`; `scrape.yml` documents the gate as intentional ("enable cron only after a real production smoke pass").
- **Status:** **OPEN — owner decision.** Correct sequence: P0-1 → dispatch `production-smoke` with `preflight_only=true` → confirm `configuration.missing == []` → re-dispatch with `preflight_only=false` and 250 records → only then set `ENABLE_PRODUCTION_INGESTION=true`.

### P1-3 — The three production workflows can only be triggered by hand
- **Evidence:** `production-smoke.yml` (`arena/01a08d60-dealscan`) and `supabase-handoff.yml` / `vercel-handoff.yml` (`arena/01a07d76-dealscan`) pin their `push` triggers to dead agent-session branches. Nothing pushes to them.
- **Status:** **DOCUMENTED, NOT PRE-EMPTED.** The dead pins were left in place because removing them is the stated purpose of open PR #18, and this audit will not duplicate or pre-empt a reviewable PR. Only way in today is `workflow_dispatch`.

### P1-4 — 42 remote branches, ~20 of them byte-identical duplicates
- **Evidence:** `feat/supabase-db-layer*` (12 refs) all point at `f77efb8`; `fix/supabase-public-read-policy*` (8 refs) all point at `9ceb2a3`.
- **Status:** **OPEN — housekeeping.** No branch was deleted; deleting refs is destructive and out of scope for an audit.

## P2 — Quality

### P2-1 — The 49 PGlite-backed security tests do not run in a constrained environment
- **Evidence:** `database-security.test.ts`, `ingestion-security.test.ts` and `operational-database.test.ts` fail in `beforeAll` with `Hook timed out in 30000ms` on **both** Node 22 and Node 24 in this sandbox (≈44 s per file). The other 12 files / 159 tests pass on both.
- **Impact:** these tests are precisely the ones guarding RLS, column grants, publication gates and cross-tenant isolation — the most valuable tests in the repo — and their status could not be confirmed here.
- **Status:** **REQUIRES MANUAL VERIFICATION** — re-run with an extended hook timeout to separate "slow sandbox" from "broken test". Result recorded in `FINAL_COMPLETION_AUDIT.md`.

### P2-2 — No local development path for Supabase Auth
- **Evidence:** the Supabase project reports `localhost_urls_present: false`.
- **Status:** **OPEN — low priority.** Add `http://localhost:3000/auth/callback` in Supabase → Auth → URL configuration to make local sign-in testable.

## P3 — Polish

Nothing in P3 is worth touching while `deals = 0` and production is unpromoted.
The UI already carries a deliberate identity (Tailwind + `globals.css`,
`CommandPalette`, `ScrollReveal`, filter/sort controls, empty and error states,
`aria-*` labels on form controls). No redesign is proposed, and none is needed
to satisfy P0/P1.

## Recommended completion order

1. Rotate the leaked GitHub token (**P0-6**) — cheapest action, highest risk.
2. Add `SUPABASE_SERVICE_ROLE_KEY` to GitHub Actions secrets (**P0-1**) — the single unblocker.
3. Confirm the `.gitignore` / `.pyc` fixes are pushed and CI is green (**P0-2**, **P0-3**).
4. Dispatch `dealscan-production-smoke` read-only, then bounded (250 records).
5. Promote `main` in Vercel (**P0-4**), then verify the live app (**P0-5**).
6. Only then set `ENABLE_PRODUCTION_INGESTION=true` (**P1-2**).
7. Resolve `deals = 0` as a product decision (**P1-1**) — new source or honest relabelling.
8. Housekeeping: prune duplicate branches (**P1-4**), merge or close stale PRs.