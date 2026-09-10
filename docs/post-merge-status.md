# Post-merge status — 2026-09-10 (session `arena/01a08d60-dealscan`)

This file is a fresh, session-scoped record. It replaces the previous session's
note. Nothing here claims production ingestion, migration, authorization or
deployment success.

## What was actually broken

`dealscan-production-smoke` had not executed a single job since PR #13. Its
`SUPABASE_SERVICE_ROLE_KEY` presence check used a double-quoted string literal:

```yaml
HAS_SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY != "" }}
```

GitHub Actions expressions accept only **single-quoted** literals, so the file
was unparseable and GitHub aborted every run at startup with zero jobs:

| Run | Branch | Event | Conclusion | Jobs |
|---|---|---|---|---|
| 34533437095 | `arena/01a0884c` | push | failure (0s) | 0 |
| 34533615403 | `main` | push | failure (0s) | 0 |
| 34534355797 | `arena/01a08d47` | push | failure (0s) | 0 |
| 34534668839 | `main` | push | failure (0s) | 0 |
| 34535256409 | `main` | workflow_dispatch | `startup_failure` | `total_count: 0` |

Corroborating evidence: the workflow was registered under its *filename*
(`.github/workflows/production-smoke.yml`) rather than its declared
`name: dealscan-production-smoke`, because GitHub could not parse the name out
of it. After the fix the same workflow ID `351029384` resolves by name.

`dealscan-ci` was green through PR #13 **and** PR #14 because no check ever
parsed a workflow expression. The fix landed as PR #15 (merge commit
`69898ec`) and adds `test_no_workflow_expression_uses_a_double_quoted_literal`,
which scans every workflow for a `"` inside `${{ }}` using only the stdlib —
`pipeline/requirements.lock.txt` has no PyYAML, so a `yaml` import would itself
have broken CI. The guard was verified in both directions: it fails on the
previous text and passes on the fixed one.

## Verified in this sandbox

- **487 tests passed** (`python -m pytest -q`, locked Python 3.11 venv) — the
  486 prior tests plus the new guard.
- `python -m compileall -q pipeline` passed.
- Expression scan across all 6 workflow files: clean after the fix, flags
  `production-smoke.yml:55` before it.
- Merge CI on `main` (`69898ec`) succeeded: run 34536862603.
- PR CI succeeded: run 34536685263; its `pipeline` job step 6 "Run pipeline
  tests" concluded `success`.

## GitHub-observed readiness evidence

Read-only run 34537161709 on `arena/01a08d60-dealscan`, commit `ffee83c`,
annotation stamped 2026-09-10T22:23:45Z. Steps 1–4 passed and step 5 ran, which
is itself proof the expression now parses. The `Read-only production readiness`
annotation reports `status: blocked`:

- **configuration: failed** — `missing: ["SUPABASE_SERVICE_ROLE_KEY"]`.
  Nothing else is missing: `SUPABASE_URL`, a public Supabase key, the explicit
  production Supabase mode and `WAITLIST_CONTACT_EMAIL` are all present.
- **platform_access** — `VERCEL_TOKEN: true`, `SUPABASE_ACCESS_TOKEN: true`,
  `SUPABASE_DB_URL: true`, `SUPABASE_SERVICE_ROLE_KEY: **false**`.
- **deployment: passed** — `https://dealscan-omega.vercel.app/api/health`
  returned HTTP 200 with `database: ok`, and `/privacy` carries
  `mailto:doriaphiri82@gmail.com`.
- **source: passed** (read-only technical probe) — El Paso CAD
  `ElPasoCADWebService/FeatureServer/0`, 138,736 matching records, 5 samples
  across 3 pages, object-ID field `ObjectID_1`, `ingestion_authorized: false`.
- **database / public_boundary: not checked** — `private_configuration_missing`.
- `production_writes_performed: false`, `ingestion_status: "not_attempted"`.

So exactly one thing blocks the bounded smoke: that one secret.

### The service-role key has never reached a runner

Two independent preflight runs, an hour apart, both report it missing:

- 2026-09-10T21:23:34Z, run 34531858733 (dispatch on `main` at `3ac6b48`, before
  PR #13 introduced the parse error) — `missing: ["SUPABASE_SERVICE_ROLE_KEY"]`.
- 2026-09-10T22:23:45Z, run 34537161709 — same, plus
  `platform_access.SUPABASE_SERVICE_ROLE_KEY: false`.

The owner believed the key was added roughly two hours before the 21:22 UTC
failure. Whatever was saved, it is not visible to Actions in this repository.

### Ruled out: an environment-name mismatch

The workflow declares `environment: production` (lowercase) while the repo's
settings contain `Production` (capital). That looked like the likely cause, and
it is **not**: `GET /environments/production` and `GET /environments/Production`
return the same entity (`id: 20783439090`), so GitHub resolves environment names
case-insensitively and the job does run in `Production`. The deployments API
merely records the casing as written. `Production` also has no protection rules,
and three sibling secrets resolve inside that same job — so the environment is
not hiding anything.

### What remains, and what could not be checked here

The agent token (`arena-ai-coding-agent[bot]`) lacks `actions:write`, so
`workflow_dispatch` returns HTTP 403 and only the owner can dispatch; it also
lacks secrets read, so the secret list could not be inspected to name the
fault. Because a push event can never reach the write step, the read-only pin
was retargeted to this session branch — the mechanism this trigger's own
comment prescribes — to obtain a real readiness annotation. Nothing was
bypassed and no gate was weakened.

Since the key is genuinely absent, the remaining causes are on the GitHub
settings side and need the owner:

1. Exact name `SUPABASE_SERVICE_ROLE_KEY` — no trailing space, no
   `NEXT_PUBLIC_` prefix, not `SUPABASE_SERVICE_ROLE`.
2. **Secrets** tab, not **Variables** — a variable is exposed as an env var and
   is invisible to `secrets.*`.
3. **Actions** sub-tab, not Codespaces or Dependabot.
4. Repository scope for `doriaphiri82-glitch/dealscan`, or the `Production`
   environment — not an org secret left unshared with this repo.
5. A non-empty `service_role` JWT. A saved-but-empty value reads as absent, and
   the `publishable`/`anon` key will not work: the smoke deliberately rejects
   service-or-unknown keys as an RLS proxy.

Once that is in place, a dispatch from `main` with `preflight_only=true` should
report `configuration.missing == []` and
`platform_access.SUPABASE_SERVICE_ROLE_KEY: true`, and only then is
`preflight_only=false` worth spending. A green bounded chain will still yield
`deals: 0`, because the El Paso CAD parcel layer publishes assessed and market
values but no asking price — see `docs/engineering-progress.md`. That is the
source, not a regression.
