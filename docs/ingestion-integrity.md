# Ingestion and publication integrity

## Backend and migration contract

Production ingestion must set `DEALSCAN_ENV=production` and
`DEALSCAN_DB_BACKEND=supabase`, with server-side `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY`. Unknown backend names and production SQLite are
errors, not fallbacks. SQLite is an isolated local-development backend.

Apply the ordered migrations in `supabase/migrations/` before running the new
pipeline. Database initialization checks the required schema; it does not alter
production tables or silently declare an old schema ready.

The ingestion migration upgrades missing columns in the earlier integer-ID
audit schema. Existing audit history is retained but marked with an audit gap;
it cannot authorize publication. Unsupported audit key types, duplicate deals
for one property, and invalid cross-county references fail migration rather than
being silently deleted. Back up and inspect an existing deployment first. The
local migration tests exercise a fresh database and a representative older audit
schema, **not the schema or migration state of the production project**.

The publication migration removes legacy permissive policies and table **and
column** grants on these application tables, then reinstalls the explicit
verified-only public projection. Audit rows, owners, financial evidence JSON,
subscriber data and waitlist entries remain private. Review any custom access
policies before applying it; custom policies on these application tables are
intentionally replaced by the secure contract.

## Source authorization

Discovery, live validation, explicit authorization and ingestion are separate
steps. Validation and authorization bind the effective URL, query, field mapping,
units, object-ID field and reviewed authority evidence to a source fingerprint. Validation expires
after seven days. New discoveries and changed sources must repeat those steps.
A Census county list is a geography universe, not evidence of parcel coverage.

An ingestion run stores the authorization/configuration snapshot. It is bounded
to 1–5,000 received records. Source transport errors remain failed/partial even
when some rows were recovered. A source with no usable parcel identities is not
a successful ingestion.

## Private persistence

- Properties use `(apn, county_id)` as their idempotent identity.
- Missing values remain null, including improvement evidence and finances.
- Source-backed vacancy-qualified properties are persisted even without asking
  price, cost, or comparable evidence. They remain held, not public opportunities.
- Records with inadequate/conflicting vacancy evidence are rejected and audited.
- Duplicate county/APN identities are held rather than selecting one for pricing.
- Deals are unique per property. Ordinary writes always set `pending_review`.
- Each run has a unique operation key and running/terminal state, heartbeat,
  counters, timestamps and safe diagnostics. Failed and partial are not aliases
  for completed.
- Each source record has a deterministic per-run/source key, original payload,
  exact canonical JSON representation, normalized payload, mapping, identity, URL, decision and optional property/deal
  links. Raw payloads and owner data must not be uploaded as public CI artifacts.
- Counts are processing outcomes/upserts in that bounded run, not national totals
  or net-new inserts. `stored` counts properties; `qualified` counts persisted
  pending-review assessments; `published` stays zero during ingestion. Held rows
  are not also counted as rejected.

Audit failures are observable and do not roll back an otherwise successful
primary property/deal write. Those records cannot pass publication verification.
Only a confirmed missing audit context can be recovered as a new partial audit
with an explicit gap. A transport error does not prove a row is missing and must
not create a misleading duplicate successful run. Old running Supabase audits
with stale two-hour heartbeats are closed as failed within their county scope.

## Explicit publication review

`database.verify_deal(deal_id)` is a separate operation, never an automatic ETL
step. It requires a completed, intact run; current authorization; matching raw,
normalized and persisted parcel evidence; qualified vacancy; a raw sourced asking
price and complete costs; and at least three persisted source-backed qualified
vacant-land sales. Sales must pass date, distance, area, identity and county
checks. Financial results and score are recomputed rather than trusted.

PostgreSQL independently hashes the exact source JSON, compares it with the JSONB
audit and property digest, binds mappings to the authorized manifest, and checks
raw vacancy, asking price, costs, comparable facts and financial arithmetic. It
requires current county authorization and sets a review expiry no later than the
source validation deadline. RLS excludes expired reviews. Review does not turn
validation time into the source's own data-freshness timestamp.

Property, comparable, audit and authorization changes revoke affected deals in
the same database transaction. Revision checks prevent an older review from
promoting a concurrently changed assessment. Comparable replacement is an
atomic RPC: invalid replacements leave the prior set intact; an empty replacement
clears it and holds the deal.

Local bundles are minimized, verified-only database snapshots, not a public API
fallback. A historical bundle must never override an empty or unavailable live
database. Operational files are not deployment evidence.

## Evidence still required for release

Offline tests use ephemeral, clearly labeled fixtures and blocked network access.
They do not prove that a live source is available, that migrations were applied
in production, or that a production ingestion/deployment succeeded. A release
still needs real source validation/authority review, configured production
credentials, bounded Supabase ingestion and trace inspection, and deployed
verified-only API retrieval. No example or fixture data should ever be sent to
the production database.


## Read-only evidence verification

Current-run checks verify unique returned properties/audit IDs, reproducible audit
keys, complete outcome accounting and chronological run timestamps. Every stored
property field (including vacancy evidence) is reconstructed from the source;
a matching raw hash alone does not prove that a mutable property column is correct.
Values and owner information are not included in mismatch diagnostics.

Public API checks compare the financial values, source references and verification
deadlines of the selected county/APN pairs, not just their identities. Unfiltered
public database reads also check review expiry. Duplicate responses and invented
zero values for missing facts cannot count as API/database agreement.
