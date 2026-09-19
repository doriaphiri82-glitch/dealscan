# DealScan Completion Plan

Derived from `PROJECT_STATE_AUDIT.md`. Ordered by what actually blocks value,
not by what is most interesting to build. Nothing here is a rewrite: the codebase
is mature (489 Python tests, 208 web tests, 14 applied migrations, a complete
Vercel environment) and most of the work is **configuration and truth-telling**,
not new features.

## P0 — Critical (blocks startup, deployment, auth, data or security)

### P0-1 — `SUPABASE_SERVICE_ROLE_KEY` is absent from GitHub under the name every consumer reads
- **Evidence:** GitHub Actions has `SUPABASE_SERVER_ROLE_KEY` (updated 2026-09-10T19:10:32Z). Nothing in the codebase references that name. `scrape.yml:57` hard-fails without `SUPABASE_SERVICE_ROLE_KEY`; `production_preflight` reports `missing: ["SUPABASE_SERVICE_ROLE_KEY"]` in runs 34531858733 and 34537161709.
- **Impact:** the entire production ingestion chain cannot run. Supabase holds 250 properties and 0 deals; the scheduled pipeline is gated off and would fail its own credential check even if enabled.
- **Status:** **CODE FIXED** — both write workflows now resolve `secrets.SUPABASE_SERVICE_ROLE_KEY || secrets.SUPABASE_SERVER_ROLE_KEY` (fail-closed: `production_preflight` still rejects any value that is not a real `service_role`/`sb_secret_` key). Regression test added.
- **Remaining:** owner should add the canonical name in GitHub → Settings → Secrets → Actions. Blocked on human action: the token in this environment cannot write secrets (the API returns names only, and the project docs record HTTP 403 for the agent token on secret management).

### P0-2 — Root `.gitignore` was replaced by an LLM chat reply, un-ignoring secrets and data
- **Evidence:** commit `f2d50db` (author `qwen.ai[bot]`, 2026-09-11) replaced the whole file with the sentence "Nothing needs to be added to .gitignore since the only modified file is a Python test file…". `git show 63ad770:.gitignore` shows the real patterns. Consequences: `.env`, `.env.*`, `*.db`, `*.sqlite`, `pipeline/data/*`, `landing/data/*`, `__pycache__/` all stopped being ignored, and **103 `.pyc` files became tracked**. `pipeline/data/dealscan.db` was previously covered by `*.db`.
- **Impact:** the next `git add -A` would have staged real waitlist emails, the SQLite database and any local `.env`. This is the single most dangerous finding.
- **Status:** **FIXED** — restored the pre-corruption patterns, added `.venv*/` and `.arena/`, and added `test_root_gitignore_still_protects_secrets_and_runtime_data`, which fails CI if any protection disappears or if prose appears in the file.

### P0-3 — 103 compiled Python artifacts tracked in git
- **Evidence:** `git ls-files | grep -c '\.pyc$'` → 103.
- **Impact:** noise, merge conflicts, stale bytecode shipped around, and the direct symptom of P0-2.
- **Status:** **FIXED** — removed from the index with `git update-index --force-remove`; the restored `.gitignore` keeps them out.

### P0-4 — Production is serving a stale commit
- **Evidence:** the Vercel handoff annotation (2026-09-07) promoted `1b8c5fb9`; `main` is at `8ebbc59` (2026-09-11). No later production deployment was observed.
- **Impact:** everything merged to `main` since 2026-09-07 — including PRs #14–#17 — is not live.
- **Status:** **OPEN — BLOCKED on Vercel access.** `vercel whoami` reports "Logged out", and the sandbox cannot reach the production alias at TCP level, so promotion cannot be performed or verified. Owner action: promote the `main` deployment in Vercel (or merge PR #18, which restores promotion as an operator-dispatched workflow).

### P0-5 — Production health is unverifiable from this environment
- **Evidence:** `dealscan-omega.vercel.app` times out at TCP connect on 443 and 80, while `vercel.com`, `ai-sdk.dev`, `supabase.com` and `api.github.com` all return 200. The deployment-specific host returns 302 (Vercel SSO).
- **Impact:** cannot distinguish sandbox egress policy from a production outage.
- **Status:** **BLOCKED — REQUIRES MANUAL VERIFICATION.** Documented, not papered over. No claim of production health is made anywhere in this work.

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