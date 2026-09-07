# Continued engineering — 2026-09-06

Resumed directly from `c676f02` on `arena/01a072f4-dealscan`. Existing external
Supabase/Vercel blockers were deferred rather than used to stop repository work.
No project restart, production migration, authorization or ingestion was performed.

## Completed fix batches

| Commit | Verified changes |
|---|---|
| `86b719a` | Complete source-audit receipt accounting; unique property/audit identities; persisted property-field replay; API financial/provenance/deadline agreement, not just matching APNs |
| `6c2abe6` | Bounded streamed HTTP/JSON/query responses; strict JSON parsing; atomic format-specific private caches; actually ordered ArcGIS IDs, including precise 64-bit identifiers |
| `180c0a4` | Source-backed public financial/read contracts; wrong-parcel and duplicate-response rejection; comparable-set/arithmetic checks; additive database publication guard |
| `e30b13b` | Cancel superseded requests; same-APN county navigation without stale renders; deadline-driven expiry; safe saved-reference handling; currency-cent preservation |
| `ffd2840` | Detect privileged credentials even under innocuous public environment names; reject malformed keys and production loopback configuration; close parser/formatting edge cases |

## Verification

- **360 Python tests passed**, including the clean locked interpreter environment.
- Python compilation and dependency consistency passed.
- **168 web/database/UI tests passed**, including Postgres migration/RLS tests and
  React request-lifecycle regressions.
- `npm ci`, typecheck and the production build passed.
- npm audit reports **zero vulnerabilities**.
- Browser checks passed for the local auth boundary, configured contact, mobile
  overflow, same-APN county navigation, scoped browser-local saved references,
  distinct comparisons and zero runtime errors. Positive browser responses used
  explicit isolated transport fixtures; none reached a database or real ingestion.
- GitHub CI passed all five fix batches, including `ffd2840`:
  https://github.com/doriaphiri82-glitch/dealscan/actions/runs/33999701765.
  The existing PR is updated as each batch is pushed. A GitHub runner's real El Paso read-only probe still passed
  after the transport changes: five sampled records across three pages. This does
  not constitute ingestion or authorization.

## Contract notes

Missing optional address, zoning and freshness information remains null. A claimed
verified opportunity with missing core price/cost/valuation evidence or contradictory
calculations now fails visibly rather than becoming a partial or fabricated listing.

`20260906010000_comparable_arithmetic_gate.sql` is additive and tested offline. It
holds inconsistent materialized price-per-acre evidence privately instead of
rewriting source facts. Actual production application remains unverified.

The existing production-readiness failures remain separate from these successful
code checks. They are not marked fixed, and no production-ready claim is made.
See `production-handoff.md` for the historical access/deployment evidence.


## Subsequent audit pass

Local Git tracking was reconciled with the already-pushed `b23c780` tree without
resetting or discarding source files. Two local coverage edits were found to have
removed endpoint authorization and restored stale filesystem data. Existing tests
reproduced those regressions; the protected authoritative path was repaired.

- `1449023`: reject duplicate/malformed coverage snapshots; distinguish current
  stored inventory from historical batch counters; retain independent admin auth.
- `0f0b1f6`: require typed validation flags and bounded sample counts; reject
  credential-bearing review URLs; revoke publication on proof changes in SQLite
  and PostgreSQL. The additive migration remains unapplied to production here.
- `83db574`: bound signup body bytes and elapsed time, reject malformed UTF-8,
  enforce exact browser origins and preserve HTTPS preview-proxy compatibility.
- `837aef9`: reject conflicting source-audit identities before batch writes,
  preserve identical idempotent retries and enforce shared adapter input budgets.

Verification: **421 Python tests**, **208 web/database tests**, compilation,
typecheck, production build and npm audit (zero vulnerabilities). GitHub CI passed
all four fix batches, including
https://github.com/doriaphiri82-glitch/dealscan/actions/runs/34015782528.
A real local HTTP request that never finished its chunked body returned **408 in
about five seconds**; cross-scheme origins returned 403 and the admin endpoint
returned 401 without a session. No valid signup or production write was attempted.
Previously documented cloud-access limitations were deferred while code work
continued; no production-ready claim is made.


## Session continuation — `arena/01a0759b-dealscan`

Resumed after PR #10 merged as `afee487` (`main`). HEAD was verified to equal
`origin/main` exactly before any change; no rebuild or architecture replacement.

- Re-verified the merged baseline in this sandbox: **421 Python tests passed**
  (locked Python 3.11 venv), **208 web/database tests passed**, `compileall`,
  typecheck, production build and `npm audit` (**0 vulnerabilities**).
- Retargeted the read-only readiness push trigger in
  `.github/workflows/production-smoke.yml` from the closed session branch
  `arena/01a072f4-dealscan` to this session's branch so fresh pushes produce
  current read-only readiness evidence. The write step remains
  `workflow_dispatch + preflight_only=false`; the workflow permissions,
  concurrency lock and environment gating are unchanged. The pinning test in
  `pipeline/tests/test_cli_integrity.py` and the runbook paragraph were updated
  together.
- Recreated `docs/post-merge-status.md` (the prior local-only note was never
  pushed) with this session's sandbox-verified results, GitHub-observed
  readiness evidence, operator-reported production state and remaining
  operator actions.
- Re-confirmed blockers instead of stopping: secret/variable management and
  manual workflow dispatch return HTTP 403; sandbox TLS to Vercel/ArcGIS/GitHub
  blob hosts fails; no Supabase/Vercel credentials exist in this environment.
  Actual production migrations, persistence and the el_paso_tx 250-record smoke
  remain externally blocked, and scheduled ingestion stays disabled.
- The retargeted push trigger produced fresh read-only readiness evidence on
  commit `adff79f` (2026-09-06T07:38:56Z): production health now responds with
  an honest 503 (web app lacked public Supabase env) instead of the earlier
  middleware crash; the Production environment then supplied `SUPABASE_URL` and
  a public key, with only `SUPABASE_SERVICE_ROLE_KEY` still missing; the El
  Paso read-only source probe passed again unchanged; no writes or ingestion
  were attempted. CI passed on-branch and on PR #11.
- **Vercel handoff (operator task, completed via runner):** with `VERCEL_TOKEN`
  in GitHub secrets, `pipeline/validation/vercel_handoff.py` and the
  `dealscan-vercel-handoff` workflow verified from the runner (16:59Z,
  `handoff_verified`): root `landing`, Node aligned 24.x→**22.x** via one
  documented PATCH (verified on re-read), all four Supabase production env vars
  present plus the versioned `vercel.json` contact, production deployment READY
  at the exact `main` HEAD (`afee487`), and live `/`, `/privacy` (contact
  match) and `/api/health` (`database:ok`). The idempotent main-promotion path
  exists but was a no-op. Preflight deployment + source checks pass; full
  preflight stays blocked only on the GitHub-side `SUPABASE_SERVICE_ROLE_KEY`,
  and `preflight_only` remains true. 440 Python tests pass.

No production-ready claim is made or implied by these changes.
- **Supabase handoff (operator task, completed via runner):** with
  `SUPABASE_ACCESS_TOKEN` in GitHub secrets, `pipeline/validation/supabase_handoff.py`
  and the `dealscan-supabase-handoff` workflow went from first contact to
  `supabase_verified` in five observed runner iterations (each annotation was
  actable evidence; nothing was ever asserted without it):
  1. token valid; project ref resolved and `GET /v1/projects` healthy, but the
     query endpoint answered **HTTP 201** (not 200) — acceptance fixed;
  2. **HTTP 400** on the query endpoint — hardened error extraction (codes
     only, never free text that can echo SQL), an explicit `select 1` probe,
     per-query diagnostics;
  3. real evidence: project `ACTIVE_HEALTHY` in `eu-west-1`, pre-existing legacy
     schema with all 10 app tables (all row counts 0), migrations applied in
     order from `main`, Auth PATCH applied, but 5 files read as
     ledger-vs-marker inconsistent;
  4. statement-wise application with post-write marker verification + a
     read-only catalog cross-check delivered the decisive clue: **every
     trigger had persisted since run 1** — `information_schema.triggers` is
     privilege-filtered (0 rows vs 15 in `pg_trigger`), and the hardening flag
     check used a case-sensitive `LIKE` while `pg_get_functiondef` renders
     `SET search_path TO` (uppercase);
  5. probes corrected (pg_catalog reads, `ILIKE`): repair env re-applied the
     single statement of the hardening file, post-write verification passed,
     and the run went **`supabase_verified`** (run 34059778402, 21:02Z):
     reconciliation clean (no pending/inconsistent), schema contract passed,
     Auth config verified (`site_url` = production, `/auth/callback` allowed;
     no localhost entries — non-failing informational flag), all counts 0.
- Ordered operator steps now closed with live evidence: (5) Auth site URL +
  callback config, (8) project inspection + migration reconciliation, (9)
  logical pre/post schema backup (schema + row counts; physical `pg_dump` still
  needs `SUPABASE_DB_URL`), (10) reviewed, ordered, additive migrations only —
  never a blind recreate, with a `supabase_migrations` ledger and halting on
  first failure.
- Step (11) read-only production preflight re-ran inside the smoke workflow on
  the same commit: deployment + source probes pass; still blocked **only** by
  the missing GitHub-Production-environment `SUPABASE_SERVICE_ROLE_KEY`.
  Consequently (12) `preflight_only` stays true and (13) the 250-record
  el_paso_tx production smoke remains **not safe to run** until that secret is
  configured and an operator dispatches the gate (my dispatch returns 403).
- 461 Python tests pass (20 offline Supabase-management contracts, incl.
  statement-wise halting, untrusted-write detection, repair opt-in, Auth
  fallback casing, probe catalog checks).
- **Operator supplied both remaining server-side secrets** (2026-09-06 ~22:00Z;
  used only inside Actions runners, names only, never values):
  - Read-only production preflight is now fully green: **ready_for_bounded_smoke**
    (run on `a4f3d64`, 22:18Z) — configuration passed, SUPABASE_DB_URL access
    mapped, deployment 200 with operator-contact match, El Paso read-only source
    probe (138,863 matching, ObjectID_1) with ingestion_authorized=false, schema
    columns checked, public boundary verified. Step (11) closes.
  - Physical pg_dump backup was added to the handoff workflow (schema-only +
    counts, secret never echoed, credential-redacted, non-failing) but currently
    reports: **connection to db.<ref>.supabase.co (IPv6), port 5432 — Network is
    unreachable**. GitHub-hosted runners are IPv4-only. OPERATOR ACTION: replace
    the SUPABASE_DB_URL secret with the project's **Supavisor pooler** connection
    string (IPv4, port 6543 transaction or 5432 session mode) from the Supabase
    dashboard Connect panel. Until then the logical schema/count snapshot
    remains the verified surrogate (and is unaffected).
  - The Management token began answering **HTTP 401** at 22:22Z although it was
    valid at 21:02Z — consistent with SUPABASE_ACCESS_TOKEN being overwritten or
    rotated during the secrets update. OPERATOR ACTION: re-store the PAT
    (sbp_...) from supabase.com/dashboard/account/tokens. The module handles the
    denial cleanly (blocked report, no crash, no leakage).
- Step (12) remains as designed: `preflight_only=false` runs only via manual
  dispatch; the sandbox token is denied dispatch rights (HTTP 403), so the
  250-record el_paso_tx smoke stays a one-click operator action that is now
  technically safe to launch (bounded 250, read-only preflight green, service
  key server-side only, source authorization halting guard in main.py chain).
- Full local sweep re-verified: 461 Python tests, 208 web tests, typecheck,
  production build; final diff scanned — no secrets, no credentials, no debug
  code (the four print()s are the handoff CLIs' sanitized report emitters).
- **IPv4 Session Pooler derivation (2026-09-07).** The earlier OPERATOR ACTION
  "replace the SUPABASE_DB_URL secret with the Supavisor pooler connection
  string" is **obsolete** — no host swap is needed. `pipeline/validation/supabase_pooler_url.py`
  adapts the stored secret per run: a direct `db.<ref>.supabase.co` host moves to
  `aws-<shard>-<region>.pooler.supabase.com:5432` with user `postgres.<ref>`, and
  an already-pooled host keeps its host but gets a tenant-qualified username and
  session-mode port. The password is spliced verbatim (never decoded/re-encoded,
  never logged), parsing is libpq-style by hand so an unencoded `[`/`]` cannot
  abort it, and the workflow masks the DSN with `::add-mask::` before capturing
  it into `GITHUB_ENV`. Transaction mode (6543) is never emitted: it cannot serve
  `pg_dump`.
- **Live evidence, run 34158289491 (2026-09-07 20:09:53Z, commit c3b57a2).**
  `dealscan-supabase-handoff` returned **supabase_verified** again with the
  restored token: query endpoint passed, pending/inconsistent both empty, schema
  contract passed, Auth passed (site URL + callback, no localhost), all 10 app
  tables present with counts 0, catalog cross-check 15 triggers / 4 policies /
  30 functions, project ACTIVE_HEALTHY in eu-west-1. `dealscan-vercel-handoff`
  stayed **handoff_verified** (production deployment on main 1b8c5fb, `/`,
  `/privacy`, `/api/health` all 200). `dealscan-production-smoke` reported
  **ready_for_bounded_smoke** (El Paso probe 138,863 records, counts all 0,
  `ingestion_authorized=false`, no production writes).
- **The physical pg_dump backup is still blocked — root cause now proven, not
  inferred.** Run 34158763056 (20:17:05Z, commit 3337628) emitted the
  credential-free shape diagnosis:
  `{"blockers":["password_is_the_dashboard_placeholder"],"host_class":"session_pooler",
  "parsed":true,"password_present":true,"password_uri_safe":false,
  "placeholder_suspect":true,"port":"5432","project_ref_available":true,
  "username_tenant_qualified":true}`. So the stored `SUPABASE_DB_URL` is already
  a correct **session pooler** endpoint (`aws-1-eu-west-1.pooler.supabase.com:5432`,
  IPv4-reachable — the runner connected to 54.229.189.117) with an already
  tenant-qualified username; the password field still holds the dashboard
  placeholder `[YOUR-PASSWORD]`, which is why `pg_dump` gets
  `FATAL: password authentication failed for user "postgres"` (Supavisor names
  the downstream role, having routed the tenant successfully) and why the very
  first derivation attempt died in `urlsplit()` with `Invalid IPv6 URL` on the
  unencoded `[`.
  **OPERATOR ACTION (the only remaining blocker for the physical backup):** in
  GitHub → Settings → Secrets → Actions, re-store `SUPABASE_DB_URL` with the
  real database password substituted for `[YOUR-PASSWORD]`, percent-encoded
  (`@`→`%40`, `:`→`%3A`, `%`→`%25`). No host change is needed; the workflow
  adapts host, port and username by itself. Until then the logical schema/count
  snapshot remains the verified surrogate and the handoff still reports
  `supabase_verified` (the backup step is non-failing by design).
- **Bounded-smoke dispatch gate repaired (2026-09-07 21:06Z, run 34161918861).**
  The operator dispatched `dealscan-production-smoke` on
  `arena/01a07d76-dealscan` with `preflight_only=false`, and the run finished
  **success** — but the step "Validate, authorize, ingest, and verify the
  complete current-run chain" was **skipped**. Evidence: the job step list shows
  step 6 `skipped`, and the artifact (`production-smoke-34161918861`, 860 B)
  contains only `readiness-summary.json` — no `smoke-summary.json`. The
  read-only preflight in that same run passed at 21:07:36Z
  (`ready_for_bounded_smoke`, El Paso 138,863 records, counts all 0,
  `ingestion_authorized=false`), so **nothing was ingested and nothing was
  written**; a green run was reported for a chain that never executed.
  The gate was `if: github.event_name == 'workflow_dispatch' && !inputs.preflight_only`,
  which depends on how a boolean input is delivered to the `inputs` context and
  treats an empty value as authorization. It is now, strictly tighter, an
  explicit literal comparison in both the typed input context and the raw event
  payload, so only `false` opens the write path and any other value stays
  read-only. Two supporting changes make a silent skip impossible to miss:
  a "Resolve and record the dispatch intent" step prints and annotates the
  resolved decision (event, county, cap, both representations of
  `preflight_only`, `authorized_write_path`) on every run, and a new guard step
  fails the run when an authorized dispatch produced no `smoke-summary.json`.
  Contracts in `test_cli_integrity.py` pin the new gate and the guard.
  **The bounded 250-record el_paso_tx chain therefore has NOT run yet** and must
  be re-dispatched by the operator (sandbox tokens still get HTTP 403 on
  `workflow dispatch`).
- **Database password reset verified end to end at the shape level, still
  failing at authentication (run 34162606071, 21:18:15Z, commit 132c3f8).**
  After the operator reset the database password and re-stored
  `SUPABASE_DB_URL`, the credential-free diagnosis is now completely clean:
  `{"blockers":[],"host_class":"session_pooler","parsed":true,
  "password_present":true,"password_uri_safe":true,"placeholder_suspect":false,
  "port":"5432","project_ref_available":true,"username_tenant_qualified":true}`.
  The placeholder is gone and the URI is well formed. `pg_dump` nevertheless
  still reports `FATAL: password authentication failed for user "postgres"` at
  `aws-1-eu-west-1.pooler.supabase.com` (18.202.64.2). A read-only `select 1`
  probe against both pooler ports was added to tell the remaining cases apart
  (stale/mismatched password vs session-mode-only failure vs wrong tenant
  suffix); its classification lands in the annotation and in
  `data/supabase-auth-probe.txt`. Everything else in the handoff stays
  `supabase_verified`; the physical dump remains the only red item.
- **Pooler authentication now succeeds (run 34162816449, 21:21:52Z, commit
  4fe4e15).** The read-only probe reports `session_5432=ok transaction_6543=ok`,
  so the reset database password, the tenant-qualified username and the IPv4
  session pooler all work — the earlier 28P01 was the stale password (Supavisor
  had not yet picked up the reset). The physical dump then failed on a purely
  technical incompatibility: `pg_dump: error: aborting because of server version
  mismatch` — ubuntu-latest ships an older `postgresql-client` than the managed
  server. A step now reads the server major version over the same read-only
  connection, installs the matching `postgresql-client-<major>` from the
  official PostgreSQL apt repository and points the backup at it, falling back
  to the system client with a warning if that is not possible.
- **The bounded 250-record chain RAN and FAILED, leaving real un-audited rows
  (dispatch 34164109995, 21:42:41Z → 21:44:49Z, commit 7859fc8).** The repaired
  gate worked — the intent notice recorded
  `event=workflow_dispatch preflight_only=false authorized_write_path=true` and
  the chain step executed instead of being skipped — but it exited 1, and the
  new guard step confirmed a `smoke-summary.json` was produced (so this was a
  real chain failure, not a skip). The next read-only preflight (run
  34164524974) measured production: **counties 0→3, properties 0→248,
  ingestion_runs 0→1, ingestion_records 0→0, deals 0**. Nothing is published
  (`available_verified: 0`, public boundary still verified), and every property
  is genuine El Paso source data — but the ingestion audit table is **empty**,
  so 248 rows have no lineage. That is precisely the `audit_gap` condition the
  design refuses to call success: `save_property()` upserts the property and
  then writes its `ingestion_records` row, and only the second write failed, 248
  times.
- **Why it could not be diagnosed, and what now fixes that.** Three blind spots
  were closed: (1) `main.py` wrote its report only to a log and an artifact —
  blob downloads are frequently unreachable, so it now emits a minimized Check
  annotation (`compact_report()` collapses lists to counts and statuses, so no
  parcel or owner payload can ride along); (2) `_request()` raised
  `HTTP <status>` with no cause — it now appends the PostgREST/SQLSTATE **code**
  only, strictly validated as `[A-Za-z0-9_]{3,12}` (42P10 = no unique index for
  an ON CONFLICT target, PGRST204 = unknown column, 23503/23514 = constraint,
  P0001 = trigger), never the message, details or hint; `warn_audit()` keeps that
  structural text only when it matches this module's own pattern, and
  `runners.run()` now surfaces the distinct reasons in the run error; (3) the
  Supabase handoff gained a **write contract**: every column the ETL can emit
  (taken from the real payload builders) must exist, and every PostgREST
  `on_conflict` target must have a non-partial unique index — a missing one is
  invisible until write time and would produce exactly this empty-audit
  outcome. A failing write contract now blocks the handoff.
- **The 248 rows were left in place deliberately.** They are real source
  records, not synthetic ones, nothing about them is published, and the upserts
  are idempotent on `(apn, county_id)`: a corrected re-run re-writes them with
  their audit rows rather than duplicating them. Deleting production rows is an
  operator decision, not an autonomous one.

