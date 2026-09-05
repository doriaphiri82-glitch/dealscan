# DealScan Pipeline

Land-deal screening pipeline: discovers authoritative county parcel sources, validates them, ingests real records, scores opportunities, persists production data to Supabase, and publishes a web bundle.

## Architecture

- **Production database:** Supabase/Postgres (`DEALSCAN_DB_BACKEND=supabase`)
- **Local development:** SQLite fallback
- **Source discovery:** county registry + ArcGIS/public parcel sources
- **Audit trail:** `ingestion_runs` + `ingestion_records`
- **Web app:** Next.js under `landing/`
- **Production schedule:** GitHub Actions `.github/workflows/scrape.yml` every 15 minutes
- **Optional cache:** Redis/Vercel KV; not required for primary Supabase reads

## Layout

```
pipeline/
├── config/            # national county registry + settings
├── scrapers/          # ArcGIS, flat-file and county adapters
├── scoring/           # deal scoring, valuation and comparables
├── delivery/          # optional email delivery
├── runners.py         # one-county ETL orchestration
├── runregistry.py     # local run history + Supabase audit finalization
├── database.py        # backend selector
├── database_supabase.py # production PostgREST persistence + provenance
├── main.py            # CLI
└── tests/             # offline unit tests
```

## Commands

```bash
python main.py --setup-db
python main.py --validate
python main.py --discover-national 50
python main.py --validate-live 50
python main.py --run-national 20 --max-records 5000
python main.py --coverage
```

For local SQLite development, omit `DEALSCAN_DB_BACKEND=supabase`. Production ingestion must have both `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` configured.

## Production workflow

`.github/workflows/scrape.yml` runs the production pipeline in this order:

1. Verify Supabase credentials.
2. Run the complete offline test suite.
3. Initialize/verify the database schema.
4. Validate the national county universe.
5. Discover and live-validate authoritative parcel sources.
6. Ingest a bounded batch of validated counties.
7. Persist properties/deals/comparables to Supabase.
8. Record ingestion provenance in `ingestion_runs` and `ingestion_records`.
9. Publish optional Redis/KV cache data when configured.
10. Commit the generated web bundle as a fallback artifact.

The web API reads verified deals directly from Supabase first, then optional Redis/KV caches. It does **not** expose hard-coded demo opportunities.

## Tests

```bash
python -m pytest pipeline/tests/
```

The production smoke test is intentionally manual because it requires real production Supabase credentials:

`.github/workflows/production-smoke.yml`

## Data quality

DealScan does not manufacture opportunities when a county source is missing, stale, malformed, or insufficiently verifiable. Candidates are rejected when required source/valuation/vacancy evidence is not strong enough. Only deals marked `verification_status=verified` are eligible for the public deals API.
