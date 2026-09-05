# County expansion: research is not permission

The active source configuration is `config/counties/national_registry.py`,
`config/source_config.py`, and `scrapers/counties.py`. Keep the exact source URL,
GEOID, units, mapping and reviewed authority evidence consistent across them.
Do not reintroduce generic price-per-acre defaults or unknown vacancy-code meanings.

1. Load official county geography explicitly with `python main.py --refresh-universe`.
   Its coverage is geography, not live parcels. Preserve a failed refresh as failed.
2. Discover plausible county/assessor/GIS sources. Store candidates as unvalidated,
   unauthorized research. AI review or a reachable URL cannot authorize ETL.
3. Review the source's governmental ownership, exact county and authority evidence.
4. Validate the exact county with `--validate-live 1 --county COUNTY_ID`.
   Demonstrate current fields, records, count, stable object ID and real pagination.
   Missing units, empty samples, schema drift and inaccessible sources fail closed.
5. Explicitly authorize the unchanged fingerprint with `--authorize-ingestion COUNTY_ID`.
6. Ingest at most 250 real records initially and verify persistence and the current
   audit chain. Use Supabase explicitly for production; never send fixtures.
7. Review any real financial candidate separately. Missing source asking/costs or
   valid comparable sales means no public opportunity, not a generated substitute.

Revalidation is mandatory after seven days or a source/configuration change.
Production registry hydration prevents fresh workflow checkouts from using stale
local permissions. Runtime registries and raw data are ignored by Git.

The source-research workflow cannot automatically ingest discoveries. Flat-file
reader implementations do not replace live validation and authorization for those
source types. Private/local cache exports are not public coverage evidence.

Refer to `docs/production-runbook.md` at the repository root for actual deployment
and production proof. Do not describe configured pilots or Census rows as national
live parcel coverage.
