# DealScan — Real Data Pipeline Scope

**Goal:** serve real, verified vacant-land opportunities through the web application without fabricating records, valuations, seller signals, or accessibility evidence.

**Status:** production hardening in progress.

## Current architecture

```text
GitHub Actions (15-minute production schedule)
        |
        v
National county registry
        |
        v
Source discovery -> live validation -> county ETL
        |
        +--> normalize / vacancy validation / financial evidence
        |
        +--> Supabase Postgres
        |      |- counties
        |      |- properties
        |      |- deals
        |      |- comps
        |      |- ingestion_runs
        |      `- ingestion_records
        |
        `--> bundle.json fallback artifact

Next.js / Vercel
        |
        `--> /api/deals -> Supabase verified deals first
              /api/deals/[apn] -> Supabase verified deal detail
```

## Implemented

| Area | Status |
|---|---|
| National county registry | Implemented |
| Source discovery | Implemented |
| Live source validation | Implemented |
| ArcGIS/public parcel adapters | Implemented |
| Normalization + field coverage diagnostics | Implemented |
| Vacant-land validation | Implemented |
| Deal scoring + valuation evidence | Implemented |
| Supabase production persistence | Implemented |
| Comparables persistence | Implemented |
| Ingestion run audit | Implemented |
| Per-record ingestion provenance | Implemented |
| Verified-deal public API | Implemented |
| Auth + protected dashboard | Implemented |
| CI Python tests | Passing |
| CI Next.js build | Passing |
| Scheduled production workflow | Implemented |
| Production smoke workflow | Implemented, manual by design |

## Data-quality rules

1. A county without an authoritative usable source is not treated as successful ingestion.
2. Source fields are normalized without inventing missing values.
3. Vacant-land classification requires an actual supported source signal.
4. Valuation requires source-derived evidence; missing evidence causes rejection.
5. Public APIs expose only deals with `status=discovered` and `verification_status=verified`.
6. Every persisted property can retain source-record provenance in `ingestion_records`.
7. Demo records are not used by the public deals API.

## Production workflow

`.github/workflows/scrape.yml`:

1. verifies Supabase credentials;
2. runs the pipeline test suite;
3. initializes the database;
4. validates the county registry;
5. discovers national sources;
6. live-validates a bounded number of sources;
7. runs bounded national ETL;
8. optionally publishes Redis/KV cache data;
9. writes the committed web fallback bundle; and
10. reports coverage.

The workflow is deliberately fail-closed when production Supabase credentials are missing.

## Production smoke test

`.github/workflows/production-smoke.yml` is manually dispatched because it requires the real production secrets. It validates:

- Supabase credentials;
- pipeline tests;
- database initialization;
- county configuration;
- live pilot sources;
- one bounded production ingestion;
- persisted production data; and
- `ingestion_runs` / `ingestion_records` provenance.

## Remaining release gates

1. Add the real `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` GitHub Actions secrets.
2. Run the production smoke workflow successfully.
3. Confirm at least one authoritative county completes ETL against Supabase.
4. Confirm verified deals appear through the production `/api/deals` endpoint.
5. Configure the Vercel project with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` and verify the deployed health endpoint.
6. Complete any commercial integrations such as payments/email only when those credentials are intentionally enabled.

Until the production smoke test passes, DealScan should be considered **release candidate**, not falsely labeled fully live.
