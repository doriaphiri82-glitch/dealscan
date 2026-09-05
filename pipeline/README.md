# DealScan pipeline

The canonical entry point is `main.py`. `runner.py` and `scheduler.py --run-once`
delegate to it and preserve failures. Production scheduling belongs to the
controlled GitHub workflow, not an independently running watcher.

## Install and test

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r pipeline/requirements.lock.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q pipeline
```

Python 3.11 is the tested runtime. The exact lock was also installed and tested in
a clean environment. Tests isolate databases, registries and credentials, and
reject unmocked network access. Do not run fixtures against production.

## Operation

Source discovery is research, **not ingestion permission**. New and changed
sources must pass live schema/pagination/record checks and authority review before
explicit authorization. Validation expires after seven days.

From `pipeline/`, after securely configuring the intended backend:

```bash
python main.py --setup-db
python main.py --coverage
python main.py --validate
python main.py --validate-live 1 --county el_paso_tx
python main.py --authorize-ingestion el_paso_tx
python main.py --run --county el_paso_tx --max-records 250 --etl-only
```

`--authorize-ingestion` must follow review of the exact source and its authority
evidence. The commands above do not create test records. Real source access and
validation are required. For production, set `DEALSCAN_ENV=production`,
`DEALSCAN_DB_BACKEND=supabase`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`.
There is no fallback to SQLite when production configuration is missing.

Use the [production runbook](../docs/production-runbook.md) for migrated-schema,
current-run and deployed-API proof. CLI partial, failed, skipped and unattempted
ingestion remain non-successful. Discovery/coverage may report unavailable sources
without pretending that they were ingested.

## Storage and publication

- County state is hydrated from Supabase, including an authoritative empty registry.
- Primary parcel identity is `(county_id, apn)`; writes are idempotent.
- Audits retain exact raw JSON, JSONB, normalized values, mapping, URL, source ID,
  run identity and the authorization manifest. Raw/owner data stays private.
- Supported vacancy is required. Financially incomplete parcels remain held.
- An assessment is private until `--verify-deal` replays its complete evidence.
- Publication expires no later than validation or comparable-age deadlines.
- Public APIs and RLS exclude revoked, expired and unverified records.

Read [ingestion integrity](../docs/ingestion-integrity.md) for the detailed model.
Local summaries are operational aids, not fallback APIs or proof of deployment.
Optional cache export rereads the verified database; supplied bundles are ignored.

## Coverage limits

The three configured ArcGIS pilots are not nationwide live coverage. The official
Census Gazetteer is geography only. Use `--refresh-universe` explicitly; a failed
refresh is a failure, not a fabricated county list. Expansion requires per-source
validation and authorization.

CSV/delimited readers enforce byte, record, schema and ZIP-expansion limits.
Headerless/multi-file sources require explicit configuration. Excel readers need
an installed compatible engine and fail explicitly if unavailable. These reader
classes do not constitute live-validated, production-authorized flat-file coverage.

Email CLI delivery is disabled. Optional provider utilities require actual consent,
a real unsubscribe URL and explicit enabling; they report provider acceptance,
not confirmed inbox delivery. Waitlist requests do not become alert subscriptions.


HTTP reads and ArcGIS query responses enforce a 16 MiB default expanded-byte cap,
a per-request deadline, bounded retries and no redirects. Bulk readers have their
own explicit cap. JSON duplicate keys and nonfinite JSON constants are errors.
Optional private caches are atomic, size-bounded and separated by response format;
cache failure does not falsify a successful uncached read. ArcGIS pagination must
actually produce strictly increasing, valid object IDs, including 64-bit IDs.
