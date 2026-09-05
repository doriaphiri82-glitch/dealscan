# Data pipeline scope and release evidence

## Actual architecture

```text
Official county geography → candidate-source research
                                     ↓
                     live validation → authority review
                                     ↓
                         explicit authorization
                                     ↓
                        bounded county ingestion
                                     ↓
             Supabase properties + private assessments
             private ingestion runs/records + comparables
                                     ↓
               separate source/financial verification
                                     ↓
             transactional publication and expiry + RLS
                                     ↓
             Next.js verified-only APIs / research UI
```

There is no public bundle, Redis or demonstration-data fallback. An empty live
database is authoritative. A database outage is a 503, not a successful empty feed.

## Separate measurements

1. **Geography registered:** county/county-equivalent identity only.
2. **Source discovered:** a candidate URL, not permission or proof of usability.
3. **Validating / unavailable:** an honest technical state, not coverage.
4. **Live validated:** current schema, sample, record-count and pagination evidence.
5. **Ingestion ready:** current validation plus reviewed authority and a matching
   explicitly authorized fingerprint, including the source object-ID field.
6. **Ingested:** actual persisted properties from a completed bounded run.
7. **Published:** separately verified opportunities with unexpired evidence.

The admin API computes current stored/verified inventory from the database.
Python registry reports explicitly label their metrics as last-batch outcomes.
Neither ingestion time nor successful HTTP transport is substituted for source
freshness. A published count does not prove a monitoring service is operating.

## Data requirements

- Missing, invalid and conflicting facts are not converted to zero/default values.
- An unoccupied building is not vacant land. Vacancy needs defensible source evidence.
- An assessment is not an asking price. Costs must be complete and source-backed.
- ARV uses at least three genuine, distinct, geographically/temporally relevant,
  qualified vacant-at-sale records. The documented model is replayed at review.
- Raw source facts, exact JSON/hash, mapping, source identity, county, run and
  normalized evidence must agree. Review and source changes are race-safe.
- Public output is allowlisted. Owners, mailing addresses, subscriber records,
  financial audit documents and raw payloads remain private.
- No source row or owner payload is uploaded in ordinary CI artifacts.

## Implemented versus externally proved

Offline regression coverage exercises Python normalization/ingestion, adapter
failures, authorization, provenance, HTTP transport, actual SQL migrations/RLS,
publication rollback/races, API privacy, auth, waitlist durability and browser data
contracts. Web typecheck and production build are local build evidence only.

Production gates still require inspection/application of the actual Supabase
schema, real securely configured credentials, executable source access, a bounded
current-run ingestion, deployed API agreement and production Auth configuration.
No production run or Vercel deployment is claimed from tests or metadata research.

Only `cochise_az`, `mohave_az` and `el_paso_tx` are configured pilots. The Census
universe implementation must not be described as nationwide parcel availability.
Begin real proof with the bounded El Paso zero-improvement source query; keep
missing prices and comparable evidence private rather than inventing deals.

See [production runbook](production-runbook.md) for exact operator actions and
[ingestion integrity](ingestion-integrity.md) for persistence/verification rules.
