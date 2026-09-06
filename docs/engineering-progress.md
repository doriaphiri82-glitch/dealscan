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
  an honest 503 (web app lacks public Supabase env) instead of the earlier
  middleware crash; the Production environment now supplies `SUPABASE_URL` and
  a public key, with only `SUPABASE_SERVICE_ROLE_KEY` still missing; the El
  Paso read-only source probe passed again unchanged; no writes or ingestion
  were attempted. CI passed on-branch and on PR #11.

No production-ready claim is made or implied by these changes.
