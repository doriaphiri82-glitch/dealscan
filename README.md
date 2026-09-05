# DealScan AI

**AI-Powered Vacant Land Deal Finder**

DealScan discovers authoritative county parcel sources, screens vacant-land records for investment signals, scores opportunities, and exposes only verified deals through the web application.

## Project Structure

```
dealscan/
├── landing/          # Next.js application, auth, dashboard and public API
├── pipeline/         # Python discovery, validation, ETL and scoring engine
│   ├── config/       # National county registry + source configuration
│   ├── scrapers/     # ArcGIS/public-record adapters
│   ├── scoring/      # Deal scoring and valuation evidence
│   ├── delivery/     # Optional email delivery
│   └── main.py       # Pipeline orchestrator
├── docs/             # Architecture and pipeline documentation
└── .github/workflows # CI, production ingestion and smoke validation
```

## Production Architecture

- **Supabase/Postgres:** durable source of truth for counties, properties, deals, comparables and ingestion audit history.
- **GitHub Actions:** production ingestion every 15 minutes with bounded discovery/validation/ETL batches.
- **Next.js/Vercel:** public site, authentication, dashboard and server-side API routes.
- **Redis/Vercel KV:** optional low-latency cache; DealScan does not require it for primary deal reads.
- **SQLite:** local development fallback only.

Every production candidate retains source provenance. The pipeline records ETL runs in `ingestion_runs` and persisted source records in `ingestion_records`. Public deal endpoints filter for `verification_status=verified` and never fall back to hard-coded demo opportunities.

## Quick Start

### Landing page

```bash
cd landing
npm install
npm run dev
```

### Local pipeline

```bash
cd pipeline
python3 main.py --setup-db
python3 main.py --validate
python3 main.py --run-national 1 --max-records 250
```

For production Supabase mode, configure `DEALSCAN_DB_BACKEND=supabase`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`. Never expose the service-role key to browser code.

## Production validation

The normal CI workflow verifies Python compilation/tests and the Next.js production build. The explicit production smoke workflow validates real Supabase credentials, live source validation, one bounded production ingestion, persisted deals, and the ingestion audit trail.

## Data-quality policy

DealScan is deliberately conservative. Missing, stale, malformed, or insufficiently verifiable county data is rejected rather than fabricated. A candidate must pass source, normalization, vacant-land and financial-evidence checks before it can become a public verified deal.

## Pricing Model

| Tier | Price | Features |
|------|-------|----------|
| Free | $0/mo | Limited verified opportunities |
| Pro | $297/mo | Full deal analysis and expanded opportunities |
| Elite | $697/mo | Everything + premium support/coaching |

Pricing is product configuration and can be changed independently of the ingestion engine.

## Status

- [x] Next.js application and responsive UI
- [x] Supabase authentication integration
- [x] Protected dashboard routes
- [x] Public verified-deals API
- [x] National county discovery/validation pipeline
- [x] Supabase production persistence adapter
- [x] Ingestion provenance/audit trail
- [x] Automated CI for Python + web build
- [x] Scheduled production ingestion workflow
- [x] Explicit production smoke test
- [ ] Configure GitHub production Supabase secrets
- [ ] Run first successful production national ingestion
- [ ] Verify Vercel production environment variables/domain
