# Controlled production rollout

This is an execution checklist, not a claim that production ingestion or deployment
has succeeded. Never insert fixtures to make the checks pass. Empty public results
are expected when real financial evidence is unavailable.

See [production handoff evidence](production-handoff.md) for observed remote
checks, the current production failure, access limits and exact operator actions.

## 1. Review and apply the database contract

Back up the Supabase project and inspect its existing schema. Apply all unapplied
files in `supabase/migrations/` in timestamp order. The ingestion/publication
migrations retain unverifiable history privately, enforce county-scoped lineage,
and replace browser grants/policies. Incompatible legacy IDs, duplicates or
references require operator reconciliation; do not drop tables to bypass a failure.

Then, with credentials provided through a secure environment, run:

```bash
cd pipeline
python -m pip install -r requirements.lock.txt
export DEALSCAN_ENV=production
export DEALSCAN_DB_BACKEND=supabase
export DEALSCAN_REGISTRY_PATH=data/counties.json
export WAITLIST_CONTACT_EMAIL=doriaphiri82@gmail.com
python main.py --setup-db
```

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` must already be configured; the
command does not create credentials or migrate tables automatically.

## 2. Configure and verify the actual web deployment

- Vercel project root: **`landing`**; Node **22**; install with `npm ci`.
- Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` to the matching
  project's URL and **anon/publishable** key. Never put a privileged key in a
  `NEXT_PUBLIC_*` variable.
- Configure Supabase Auth's site URL and allowed `/auth/callback` URLs for the
  actual deployment. Do not use a sandbox localhost URL in browser configuration.
- Server-side features requiring private writes need separately configured
  `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. A server-only Vercel secret is
  not a public frontend variable.
- Set a real `WAITLIST_CONTACT_EMAIL`, review `/privacy` and the retention/contact
  process before collecting signups. The operator-provided contact is
  **`doriaphiri82@gmail.com`**, set in `landing/vercel.json` for builds/runtime.
  Requests require explicit consent and a durable
  private database write. They are not automated email-alert subscriptions.
- Confirm `/api/health` returns 200 with `database=ok`. A configured but empty
  database is healthy; an unavailable/misconfigured one must return 503.

## 3. Configure GitHub without sharing secrets in chat

Create/review the **production** GitHub environment and its protection rules.
Configure these environment or repository secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- Either `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY` for independent public
  RLS checks (this is not the service key).

The GitHub connector may not have permission to manage secrets. Use GitHub's
settings UI if necessary. Never paste private keys into issues, logs, chat or Git.

## 4. Execute one bounded real smoke run

Review the exact county source and its authority evidence. Dispatch
**dealscan-production-smoke** with:

- exact reviewed county ID (initial default: `el_paso_tx`);
- `max_records=250`;
- the actual deployed HTTPS application origin;
- initially leave **`preflight_only=true`** (the safe default). It only reads source,
  schema/counts and deployed API state, reports missing secret names without values,
  and never authorizes, ingests, creates fixtures or applies migrations.

After read-only readiness passes and source authority/migrations have been reviewed,
repeat with **`preflight_only=false`** to execute the real 250-record ingestion.
Pushes to the current trusted handoff branch `arena/01a0759b-dealscan` (the
branch pinned in the workflow's `push` trigger) also run only read-only
readiness (to obtain evidence when the connector cannot manually
dispatch Actions). A superseded session branch is retargeted explicitly in the
workflow pin. The write step additionally requires `workflow_dispatch`, so
a push never authorizes or ingests. Environment protection rules remain enforced.
The workflow refuses to continue when readiness fails. The same minimized
readiness report appears in a GitHub Check annotation, so it remains inspectable
when the artifact/log storage endpoint is unreachable. No source rows or secret
values are included. A preflight pass alone is
not a completed production smoke, migration proof or authenticated-login test.

Read-only readiness is also available locally (it can report missing credentials
without selecting a fallback database):

```bash
python -m validation.production_preflight --county el_paso_tx --max-records 250 \
  --app-url "$PRODUCTION_APP_URL" --report-file data/readiness-summary.json
```

The full smoke command is available from a securely configured operator environment:

```bash
python main.py --production-smoke el_paso_tx --max-records 250 \
  --app-url "$PRODUCTION_APP_URL" --report-file data/smoke-summary.json
```

The sequence is live validation → explicit authorization → bounded Supabase ETL →
**that run's** property/raw/normalized/mapping/identity checks → public RLS and
web API checks. Missing credentials, failed validation, an unattempted/partial
run, stale audit evidence or a failed public API check produce nonzero exit codes.
The smoke test never requires or invents a profitable deal to create activity.

Private source rows stay in the database. CI artifacts contain minimized counters,
run IDs and structural diagnostics, not owner/raw payload exports. They expire
after seven days. Do not publish screenshots or dumps containing owner information.

To recheck an existing run without ingesting again:

```bash
python main.py --verify-ingestion-run RUN_ID --county el_paso_tx --max-records 250 \
  --app-url "$PRODUCTION_APP_URL" --require-web-api
```

`RUN_ID` is the real numeric ID returned by the ingestion summary, not a sample ID.
When executed inside Actions the check also requires the current workflow ID and attempt, not evidence from an older retry. The health response must identify the same Supabase project even when both public feeds are empty.

## 5. Review opportunities separately; opt into automation last

Ingestion persists source-faithful held candidates and pending-review assessments.
It does **not** automatically publish opportunities. An operator may invoke
`python main.py --verify-deal DEAL_ID` only for a real persisted assessment after
reviewing its source evidence. Verification recomputes the financial model,
checks durable comparables and sets an expiry bounded by both source validation
and the oldest comparable's allowed age. It fails if evidence is
missing or changed.

Only after the real smoke/deployment checks pass, set repository variable
`ENABLE_PRODUCTION_INGESTION=true` to enable the 15-minute cron. Initial automated
runs remain bounded to one pilot and 250 records. The ingestion and smoke workflows
share a concurrency lock; neither pushes generated data to Git or to `main`.

## National research is separate

`python main.py --refresh-universe` loads official Census county geography and
fails if that refresh cannot be completed. It creates no parcels or financial
claims. Source research can then use the separate read-only discovery workflow.
New discoveries require live validation and reviewed authority evidence before
explicit authorization. Production registry state is synchronized with Supabase
so fresh workflow checkouts do not silently reuse stale local permissions.

A count of counties in Census/the registry is **not** national live parcel coverage.
Report discovered, current live-validated, authorized, actually ingested and
publicly verified opportunities as separate measurements.

## Deliberately inactive features

Paid checkout and automated deal alerts are not enabled. The email CLI fails
explicitly; provider helpers require consent, a real unsubscribe URL and explicit
enabling, and report acceptance rather than inbox delivery. Legacy subscriber
rows do not acquire manufactured consent during migration. Browser saved parcels
are local to the browser profile, not synchronized private account data.

No production datasource is replaced with an illustrative property or an invented
map point. Optional diagnostic cache exports are disabled unless explicitly
requested, reread current verified rows and are never read by the web API.

## Supabase management handoff

The `dealscan-supabase-handoff` workflow (push to the session branch or manual
dispatch, `environment: production`) runs `pipeline/validation/supabase_handoff.py`
with `SUPABASE_ACCESS_TOKEN` and `SUPABASE_URL` from GitHub secrets. It is
inspection-first and evidence-only:

1. Probe `select 1`, then take a logical schema snapshot (tables/columns,
   functions, triggers, policies, indexes, RLS flags, migration ledger, row
   counts). No row content, no credentials, no secret-shaped values.
2. Reconcile the 11 reviewed `supabase/migrations` files (materialized from
   `main` on the runner, never the unmerged branch) against a
   `supabase_migrations.schema_migrations` ledger plus marker objects
   (table/function/trigger/policy/index/column/body-flag names).
3. Apply any pending files **one SQL statement per call** (dollar-quote aware
   splitting), re-verify each file's markers after application and only then
   write its ledger row; any failure reports the exact statement index or the
   missing markers and stops. `applied=ledger` with missing markers is an
   `inconsistent` state that blocks by design; idempotent re-application is
   opt-in via `DEALSCAN_REPAIR_INCONSISTENT=1` and still re-verifies.
4. Require the schema contract (required non-credential columns), sanitize the
   Auth config (only site URL, redirect list, core email toggles; secrets are
   dropped), and ensure `SITE_URL` plus the production `/auth/callback`
   redirect. PATCH fixes are re-read before being claimed, with a lowercase
   payload fallback if the API accepts an uppercase payload without persisting.

Operational caveat learned on the live project (eu-west-1): for the Management
query role, `information_schema.triggers` is privilege-filtered and returned
**zero** while `pg_trigger` held all 15 public triggers — probes now read the
`pg_catalog` views directly. `pg_get_functiondef` renders
`SET search_path TO ...` (uppercase), which a case-sensitive `LIKE` cannot
match. The Check annotation carries a minimized summary (<4 KB); the full JSON
report is a 7-day artifact. The endpoint answers HTTP 201 (not 200) with the
row array. Physical `pg_dump` still needs `SUPABASE_DB_URL` (not available);
the schema/count snapshot is the verified surrogate.

## PostgreSQL connectivity: IPv4 Session Pooler

GitHub-hosted runners are **IPv4-only**, and the direct database host
`db.<ref>.supabase.co` publishes an **IPv6-only** address unless the project
buys the IPv4 add-on. A `SUPABASE_DB_URL` that works from a laptop therefore
failed on the runner with `connection to server ... Network is unreachable`.
Supabase's Supavisor pooler is dual-stack, so `pipeline/validation/supabase_pooler_url.py`
adapts the stored secret per run instead of asking for a manual secret swap.

| element    | direct                 | required for the runner                                  |
|------------|------------------------|----------------------------------------------------------|
| host       | `db.<ref>.supabase.co` | `aws-<shard>-<region>.pooler.supabase.com` (dual-stack)   |
| port       | 5432                   | **5432 — session mode**                                   |
| user       | `postgres`             | **`postgres.<ref>`** — Supavisor routes on the tenant suffix |
| password   | percent-encoded        | copied verbatim, never decoded, never logged              |
| path/query | —                      | preserved byte for byte                                   |

Two rewrites, both learned from live runs:

1. A direct `db.<ref>.supabase.co` host is moved onto the session pooler.
2. A host that is **already** a pooler endpoint keeps its host (this project
   answers on the **`aws-1`** shard, not `aws-0`) but has its username
   tenant-qualified and its port forced to 5432. Supavisor routes on the tenant
   suffix, so a plain `postgres` user against a pooler host cannot authenticate.
   The project ref comes from `DEALSCAN_SUPABASE_PROJECT_REF` or the
   `SUPABASE_URL` secret; when it is unknown the DSN is passed through rather
   than guessed.

Note on reading the error: `FATAL: password authentication failed for user
"postgres"` from a pooler host names the *downstream* role, so it means the
tenant was routed and the **password** was rejected — it is not evidence of a
username problem. `FATAL: Tenant or user not found` is the username symptom.

Port **6543** is transaction mode: it multiplexes statements and cannot serve
`pg_dump`, so the derivation never emits it. Region and shard are pinned in the
workflow (`DEALSCAN_SUPABASE_REGION=eu-west-1`, `DEALSCAN_SUPABASE_POOLER_SHARD=aws-1`)
and validated (`^[a-z]+-[a-z]+-[0-9]+$`, `^aws-[0-9]+$`). Any host that is
neither form raises rather than hiding a misconfigured secret.

Parsing is done by hand, libpq-style (authority ends at the first `/`, `?` or
`#`; userinfo ends at the first `@`), because `urlsplit()` raises
`Invalid IPv6 URL` on an unencoded `[`/`]` in the password — which is exactly
what an unreplaced `[YOUR-PASSWORD]` placeholder looks like, and aborting there
would hide the real problem.

Secret handling: the workflow calls `--emit-mask` first so the derived DSN is
registered with `::add-mask::` before the `--dsn` capture into `GITHUB_ENV`;
failures print a credential-free `::warning::` to stderr and exit 1 with empty
stdout, so the capture cannot pick up junk. The backup step uses
`DB_DSN="${SUPABASE_DB_POOLER_DSN:-$SUPABASE_DB_URL}"` and stays non-failing by
design: if the physical dump cannot run, the logical schema/count snapshot
remains the verified surrogate.

### Diagnosing an authentication failure without seeing the secret

`--diagnose` writes `data/supabase-dsn-diagnosis.json` into the 7-day artifact
and echoes it as a `::notice::`. It reports **shape only** — `host_class`
(`session_pooler` / `transaction_pooler` / `direct_ipv6_only` / `unknown`),
`port`, `username_tenant_qualified`, `password_present`, `password_uri_safe`,
`placeholder_suspect`, `project_ref_available` — plus a `blockers` list. No
credential value, and never which character is wrong.

| blocker | operator fix |
|---------|--------------|
| `password_is_the_dashboard_placeholder` | The literal `[YOUR-PASSWORD]` was never replaced. Re-copy the Session Pooler URI from Supabase → Connect and substitute the real database password. |
| `password_not_percent_encoded` | Percent-encode special characters (`@`→`%40`, `:`→`%3A`, `%`→`%25`, `[`→`%5B`). |
| `pooler_username_not_tenant_qualified_and_ref_unknown` | Store `SUPABASE_URL` (or `DEALSCAN_SUPABASE_PROJECT_REF`) so `postgres` can become `postgres.<ref>`. |
| `unrecognised_host` | The secret is neither the direct host nor a pooler host. |

Operator note: no rotation is required for the *host*; the workflow adapts it.
Only the database **password** itself must be correct and percent-encoded in
`SUPABASE_DB_URL`.

### Read-only auth probe

A `select 1` probe runs after the backup step against **both** pooler ports and
writes `data/supabase-auth-probe.txt` (also a `::notice::`). It classifies each
outcome as `ok`, `invalid_password_28P01`, `tenant_or_user_not_found`,
`ipv6_unreachable`, `dns_failure`, `timeout`, `tls_error` or `other` — never a
value. Port 6543 is contacted **for diagnosis only**; `pg_dump` always uses 5432.

| session 5432 | transaction 6543 | meaning |
|---|---|---|
| `ok` | any | credentials fine; a dump failure is something else |
| `invalid_password_28P01` | `invalid_password_28P01` | the password in the secret does not match the database password, or Supavisor has not yet picked up a very recent reset |
| `invalid_password_28P01` | `ok` | credentials are right; session mode is the problem, not the secret |
| any | `tenant_or_user_not_found` | the username's tenant suffix is wrong |
