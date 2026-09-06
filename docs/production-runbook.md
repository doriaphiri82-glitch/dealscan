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
