# Production handoff evidence — 2026-09-06 (Africa/Lusaka)

This records observed results, not a production-ready claim. No production
migration, authorization, parcel ingestion or opportunity publication was
performed during this handoff.

## Repository and delivery

- Working branch: `arena/01a072f4-dealscan`; the previous audited state was preserved.
- GitHub access is restored for code push and pull requests.
- Draft PR: https://github.com/doriaphiri82-glitch/dealscan/pull/10
- Current handoff code is pushed; CI and Vercel preview builds have succeeded.
- `WAITLIST_CONTACT_EMAIL=doriaphiri82@gmail.com` is set in the version-controlled
  Vercel build/runtime configuration and local preview. It is a public contact,
  not a subscription signup, sender identity or production credential.
- Node is pinned to the tested `22.x` runtime. Vercel project root remains `landing`.
  The dashboard's actual root/environment settings cannot be read without Vercel
  management access; build success is not a substitute for that inspection.

## Real external evidence

Read-only readiness ran in GitHub's **Production** environment on commit
`fe6b3789ef2f38e6f546511020cee3b912b32663`:

- Run: https://github.com/doriaphiri82-glitch/dealscan/actions/runs/33995992917
- Evidence timestamp: **2026-09-05 22:28:45 UTC** / **2026-09-06 00:28:45 Lusaka**.
- Its minimized JSON is available in the **Read-only production readiness** Check
  annotation and its seven-day artifact. The write step was skipped.

| Check | Observed result |
|---|---|
| Required production secrets in that job | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a public Supabase key were **not supplied** |
| Management credentials under expected secret names | `VERCEL_TOKEN`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_URL`: unavailable |
| Actual production `/api/health` | **HTTP 500** |
| Production site via independent HTTP retrieval | `/`, `/api/health`, `/privacy`: `MIDDLEWARE_INVOCATION_FAILED` |
| El Paso source connectivity/schema/sample pagination | **Passed a read-only technical probe** |
| Configured query count | **138,863 matching records**, not ingested records |
| Source sample | **5 real records across 3 pages**; object-ID field **`ObjectID_1`** |
| Database schema/counts/provenance | **Not checked**: private configuration missing |
| Deployed API/database agreement | **Not checked**: private configuration missing and production health failing |
| Production writes | **None** |
| Real 250-record ingestion | **Not attempted** |

The actual source query was `legal_acreage > 0 AND imprv_val = 0` against:

https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0

This is source-access evidence only. It did not change registry authorization or
establish financial evidence, full-county coverage, or successful ingestion. No
source record values or owner samples are exported in the report.

Successful current-branch code checks:

- https://github.com/doriaphiri82-glitch/dealscan/actions/runs/33995992905
- https://github.com/doriaphiri82-glitch/dealscan/actions/runs/33995995099

The Vercel GitHub status reports successful **Preview** builds. Preview URLs require
Vercel authentication, so their live database/contact behavior has not been checked
anonymously. The production alias is still the older, failing deployment:

https://dealscan-omega.vercel.app

## Access boundaries confirmed

The connector returns HTTP 403 for repository/environment secret and variable
management and manual workflow dispatch. Code push and PR creation work.
A trusted-branch push runs read-only readiness without bypassing environment
protection rules; actual ingestion requires `workflow_dispatch` and an intact
readiness pass. Both checks remain separate from normal offline CI.

The `Production` environment exists, but currently has **no configured reviewers
or deployment-branch restriction**. Lowercase `production` resolves to the same
environment ID; the missing keys are not a casing mismatch.

Sandbox-native HTTPS access to Vercel, ArcGIS and GitHub's blob-backed logs/artifacts
fails with TLS/EOF transport errors. TLS verification was not disabled. GitHub
runner source access works, and Check annotations retain readable readiness
metadata without relying on blob downloads.

## Exact remaining operator actions

1. In GitHub's **Production** environment or repository Actions secrets, supply the
   real matching `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and either
   `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY`. Configure appropriate environment
   protections before write-enabled runs. Do not paste credentials into chat.
2. Inspect/back up the actual Supabase project and apply all unapplied ordered
   migrations. The REST service key alone is not a database-migration credential.
   If the agent is to manage this directly, provide authorized database/management
   access through a secure environment, not chat.
3. In Vercel, verify project root `landing`, Node 22, matching public Supabase URL/key,
   separate private server-only Supabase URL/service key, and the supplied contact
   email. Verify Supabase Auth site/callback URLs. Fix production by promoting the
   reviewed, tested branch deployment (or merging the PR after the required review)
   rather than leaving the old crashing middleware live. Vercel management access
   is required for the agent to inspect/change those settings directly.
4. Follow `docs/production-runbook.md`: run read-only readiness first. Once it passes,
   review the exact source authority and dispatch `dealscan-production-smoke` on
   this branch with **`county_id=el_paso_tx`**, **`max_records=250`**,
   **`app_url=https://dealscan-omega.vercel.app`**, **`preflight_only=false`**.
   The owner's GitHub UI can dispatch while the connector lacks that permission.
5. Verify that run's complete persistence/audit/raw/normalized/hash/identity chain
   and deployed API agreement. Keep any financially incomplete parcels private.
   Zero published opportunities is valid; never insert fixtures to force a pass.
6. Only after real proof, enable cron with `ENABLE_PRODUCTION_INGESTION=true`.
   No such enabling was performed here.

**Release status: blocked by external configuration/access and production
promotion.** The code/CI/preview-build results above do not satisfy the missing
production gates.
