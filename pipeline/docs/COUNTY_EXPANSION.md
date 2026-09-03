"""
DealScan - County expansion documentation.

How to add a new county to DealScan.
"""
from __future__ import annotations

DOC = """
# Adding a New County to DealScan

## Prerequisites

1. The county must have publicly accessible parcel/property data.
2. Prefer official ArcGIS REST/FeatureServer/MapServer, bulk flat-file downloads,
   CSV, XLS/XLSX, JSON APIs, or official GIS portals.
3. The data source must permit programmatic access or polite scraping.

## Step-by-step

1. Choose a stable county ID using FIPS/GEOID: `{state_fips}{county_fips}`.
   Example: Pima County, AZ = `pima_az` with GEOID `04019`.

2. Add county metadata to `pipeline/config/counties/national_registry.py`:
   - county_name, state, state_fips, county_fips, geoid
   - assessor_url, gis_url, parcel_source_url
   - source_vendor, scraper_type
   - verification_status, coverage_status, notes

3. Add a scraper configuration entry to `pipeline/scrapers/counties.py`:
   - data_mode: `arcgis`, `flatfile`, `csv`, `excel`, or `data_file`
   - arcgis_root or arcgis_layer_url
   - fields mapping from source fields to canonical property fields
   - where clause for filtering vacant land where applicable
   - defaults such as county_state

4. If the county uses ArcGIS:
   - Use `python main.py --probe-all` to verify the source is reachable
     and identify available fields.
   - Update the `fields` mapping in `pipeline/scrapers/counties.py`
     to match the actual source field names.
   - Add any county-specific vacant land use codes to
     `pipeline/scrapers/arcgis.py` -> `VACANT_LAND_USE_CODES`.

5. If the county uses flat files:
   - Configure `parcel_source_url` or `open_gov_url`.
   - Update field mapping aliases in `pipeline/scrapers/flatfile.py`.

6. Run validation:
   - `python main.py --counties` to confirm the county is registered.
   - `python main.py --probe` to verify source reachability.
   - `python main.py --run --county <county_id>` to run the scraper.
   - `python main.py --health` to confirm the county appears in the dashboard.

7. Verify data quality:
   - The pipeline reports discovered, downloaded, parsed, normalized,
     rejected, stored, scored, qualified, and published counts.
   - If `stored == 0` but `discovered > 0`, check rejection reasons.
   - Never mark a county production-ready without validated records.

8. For GitHub Actions:
   - Add the county ID to the matrix in `.github/workflows/scrape.yml`
     if you want it included in the CI run.
   - Use a separate matrix entry or batched execution for large counties.

## Field mapping rules

- The source field names MUST be mapped to the canonical schema.
- Use `pipeline/config/field_mapping.py` to validate mappings.
- Do NOT assume source field names are identical between counties.
- If a field is missing or ambiguous, leave it unmapped rather than
  guessing.

## Coverage tiers

- tier_0: Not researched
- tier_1: Source discovered
- tier_2: Source verified
- tier_3: Scraper implemented
- tier_4: Scraper producing valid records
- tier_5: Scraper producing qualified deals
- tier_6: Production monitored

## Anti-patterns

- Do NOT create fake county entries to inflate coverage numbers.
- Do NOT scrape aggressively; respect rate limits and robots.txt.
- Do NOT mix county-specific scraping logic with investment scoring.
- Do NOT mark a county as production-ready without passing validation.
- Do NOT allow one broken county to terminate the national pipeline.
"""


def documentation() -> str:
    return DOC.strip()
