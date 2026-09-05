# DealScan

Source-backed vacant-land research with a Next.js application, Python pipeline,
and Supabase persistence. **Missing evidence stays missing.** An empty verified
feed is an acceptable result; invented listings, comparable sales and profits are not.

## Current release status

The ingestion, publication, API and database-security contracts have offline
regression coverage. That is **not production verification**. No production
migration, real Supabase ingestion or Vercel deployment has been proved in this
engineering environment. Follow the [production runbook](docs/production-runbook.md).

Three pilots are configured: `cochise_az`, `mohave_az`, and `el_paso_tx`.
A Census county universe/discovery implementation exists, but county geography
is not national live parcel coverage. The official 2025 county ZIP and executable
live source validation still require a working network environment. Technical
metadata research alone does not authorize ingestion.

## Architecture and integrity

- **Supabase/Postgres:** authoritative production properties, private assessments,
  comparables, county state and durable ingestion evidence.
- **Python:** discover → live validate → explicitly authorize → bounded ingest.
  Ingestion does not publish opportunities. Separate verification replays source
  evidence, vacancy, qualified sales and the documented financial model.
- **PostgreSQL:** independent raw JSON/hash, mapping, evidence and arithmetic gates;
  changes revoke publication transactionally. RLS excludes unverified/expired rows.
- **Next.js/Vercel:** verified-only, allowlisted APIs and authenticated workspaces.
  Public reads never fall back to Redis, a committed bundle or demonstration data.
- **Waitlist:** private atomic Supabase writes, explicit consent, durable rate limits,
  a configured operator contact and no temporary-file success fallback.
- **SQLite:** explicit local development only; rejected as a production backend.

See [ingestion integrity](docs/ingestion-integrity.md) and
[data-pipeline scope](docs/DATA_PIPELINE_SCOPE.md) for limits and evidence requirements.

## Reproducible local checks

Python **3.11**, Node **22**:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r pipeline/requirements.lock.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q pipeline

cd landing
npm ci
npm test
npm run typecheck
npm run build
npm audit --audit-level=high
npm run dev -- --hostname 0.0.0.0
```

Tests use isolated fixtures and blocked external network access. They must never
point at a production project. See `.env.example`, `pipeline/.env.example`, and
`landing/.env.example`; keep real secrets out of Git and chat.

## Deployment and operation

1. Back up and inspect the actual database, then apply **all ordered migrations**
   in `supabase/migrations/`. They preserve history but revoke legacy publication.
2. Configure Vercel with root **`landing`**, Node 22, matching public Supabase
   URL/key and Supabase Auth callback URLs. Private admin/waitlist features use
   separate server-only credentials. Configure a real `WAITLIST_CONTACT_EMAIL`.
3. Configure the protected GitHub **production** environment with Supabase service
   and public keys. Do not expose the service key through `NEXT_PUBLIC_*`.
4. Dispatch the explicit production smoke for one reviewed county, initially
   **`el_paso_tx`, 250 real records**, and the actual deployed HTTPS app origin.
   Prove the current run's database/audit chain and the matching deployed API.
5. Review any actual financial candidates separately. Zero public opportunities
   is acceptable when asking prices, costs or suitable sales are missing.
6. Enable scheduled ingestion only after that proof with
   `ENABLE_PRODUCTION_INGESTION=true`. Cron is otherwise disabled.

No workflow commits runtime source rows or publishes a fallback data bundle.
The production workflow is intentionally separate from source-discovery research.

## Product boundaries

Saved parcels and recent research are browser-profile local, not account-synced.
Same-APN parcels remain county-scoped; legacy unscoped references are not guessed.
Paid checkout, automated email alerts and premium-service promises are not active.
Optional email/cache utilities fail closed by default and are not publication paths.


Browser research cancels superseded requests and never switches a same-APN parcel
into the wrong county after navigation or a late response. Saved references are
validated without silently truncating or reinterpreting corrupt data. Currency
formatting preserves source cents rather than rounding a small price to zero.
