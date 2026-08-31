# DealScan — Real Data Pipeline Scope

**Goal:** serve real, live property reports through the webapp instead of demo data, starting with the three pilot counties (Cochise AZ, Mohave AZ, El Paso TX).

**Date:** August 28, 2026 · Status: Scope/Plan — not started

---

## 1. Current state audit (what exists vs. what's missing)

| Component | Status | Notes |
|---|---|---|
| `pipeline/scoring/deal_scorer.py` | ✅ Working | Signal detection, ARV from comps (median $/acre ±20%), weighted 1–100 score, offer range |
| `pipeline/database.py` | ✅ Working | SQLite schema: properties, deals, comps, subscribers, deliveries, waitlist |
| `pipeline/models.py` | ✅ Working | Clean dataclasses matching the DB schema |
| `pipeline/delivery/email_sender.py` | ✅ Working | HTML digest + Resend/SendGrid/console providers |
| `pipeline/config/counties.py` | ✅ Working | 5 counties, URLs + FIPS + market metadata |
| `pipeline/scrapers/` | ❌ **Empty** | Zero data acquisition code. `main.py --run` falls back to demo |
| Scheduling | ❌ Missing | No cron/scheduled execution anywhere |
| Webapp ↔ pipeline bridge | ❌ Missing | Webapp reads Vercel KV; pipeline writes SQLite. No shared store |
| Deals API on webapp | ❌ Missing | `/api/deals` does not exist; site shows hardcoded demo rows |
| Accessibility data | ⚠️ Hardcoded | `deal_scorer.py` sets `has_road_access: True` — must be removed once real data exists (don't fabricate) |

**Net:** the scoring/reporting half is built; the entire data-acquisition half and the integration layer are not.

---

## 2. Data source strategy (the critical decision)

County parcel data is public-record, but access methods differ per county. In order of preference:

1. **Official bulk downloads / open data portals** — most reliable, explicitly permitted. Several AZ/TX appraisal districts publish CSV exports or FTP data.
2. **Official property-search pages** — scrape politely (identify UA, rate-limit 1 req/2–4s, cache aggressively, honor robots.txt, avoid peak hours). Requires ongoing maintenance.
3. **Tax-delinquency / lien-sale lists** — published annually by county treasurers; the single best "motivated seller" source and usually a simple PDF/CSV.
4. **Recorder recent-transfers index** — the comps source (real sale prices, dates, parcel IDs).
5. **Paid APIs (Regrid, ATTOM, Estated)** — $50–500/mo fallback if a county blocks scraping.

### County source matrix (to be verified in Phase 0 spike)

| County | Assessor parcel data | Comps (transfers) | Tax delinquency | Priority |
|---|---|---|---|---|
| Cochise AZ (`cochise_az`) | assessor.cochise.az.gov search; check for CSV/FTP | Recorder recorded-docs index | Treasurer publishes annual lien-sale list | **1st** (notes say delinquent lists available) |
| Mohave AZ (`mohave_az`) | assessor.mohave.gov search; AZ parcel datasets | Recorder | Treasurer delinquent list | 2nd |
| El Paso TX (`el_paso_tx`) | epcad.org property search (TX CADs usually offer bulk files) | EPCAD sales data | Tax resale lists (TX posts before tax sales) | 3rd |

**Phase 0 spike (1–2 days, must be first):** for each county, document (a) does a bulk export exist, (b) search-page structure, (c) robots.txt/ToS, (d) delinquent-list location, (e) sample of 5 real parcels to validate field mapping against `models.Property`. Output: `pipeline/config/counties.py` gains a `sources` block per county.

---

## 3. Target architecture

```
GitHub Actions (cron: weekly full, daily delta)
  └─► scrapers/ (per-county adapter: county_config.sources)
        └─► raw cache (committed JSON artifacts, 30-day TTL)
              └─► normalize → models.Property / CompSale
                    └─► SQLite (existing schema) inside the Actions runner
                          ├─► scoring/deal_scorer.py (unchanged logic)
                          └─► publish:
                                ├─► Vercel KV  (top N deals + reports JSON — what the site reads)
                                └─► Neon Postgres (free) — durable full dataset (Phase 2+)
Webapp (Vercel)
  ├─► GET /api/deals            → reads KV (top deals), cached
  ├─► GET /api/deals/[apn]      → full report: signals, comps, score, evidence
  └─► SampleDeal section        → real reports when fresh; falls back to labeled demo
```

**Why GitHub Actions:** free (2,000 min/mo private, unlimited public), network egress included, supports Playwright if ever needed, native cron scheduling, and keeps Vercel functions short-lived. Vercel Cron is unsuitable for long scrapes.

**Why publish only top-N to KV:** KV value size is limited; the site only needs scored top deals + individual reports. The full dataset lives in the SQLite artifact / Postgres.

---

## 4. Phased plan

### Phase 1 — Source spike + scraper framework (week 1)
- Phase 0 spike per §2; write `sources` config per county
- `scrapers/base.py`: polite HTTP client (UA string identifying DealScan, 2–4s jittered delay, 429/backoff, response cache, robots.txt guard)
- `scrapers/cochise_az.py` end-to-end: parcels → `models.Property` → SQLite (`save_property`)
- Field-mapping tests against 5 real parcels
- **Exit criteria:** `--run` produces ≥100 real Cochise parcels in SQLite, zero demo data

### Phase 2 — Comps + real scoring (week 2)
- Recorder transfers → `CompSale` records (sale price, date, distance via geocode)
- Remove `has_road_access: True` hardcode; accessibility from parcel attributes or "Unverified"
- Run `score_and_enrich_deal` on real comps; tune `MIN_PROFIT_ESTIMATE` against real distributions
- **Exit criteria:** ≥10 real scored deals, manually sanity-checked against listing reality

### Phase 3 — Serve real reports (week 3)
- Publish step: top 25 deals + per-deal report JSON → Vercel KV (`deals:top`, `deal:{apn}`), with `generated_at`
- Webapp: `GET /api/deals`, `GET /api/deals/[apn]` (KV-backed, 60s cache)
- Site sections render real reports with `Data updated {generated_at}`; **fall back to labeled demo** when stale/absent — never show stale as live
- Waitlist bridge: webapp KV waitlist → pipeline `subscribers` (pipeline reads KV on run)
- **Exit criteria:** a visitor sees a real Cochise parcel report generated <7 days ago

### Phase 4 — Scheduling + delivery (week 4)
- GitHub Actions: weekly full scrape + daily delta/publish; failure alerts
- Resend account + `EMAIL_API_KEY` → daily digest via existing `email_sender.py` (free tier 3k/mo)
- Free-tier delay logic (already specced in `settings.py`: 48h delay, 3 deals/week)
- **Exit criteria:** subscribers receive the digest automatically

---

## 5. DealScore reconciliation (required before Phase 3)

The pipeline computes a single profit-weighted `deal_score` (1–100), but the site presents five dimensions (Value / Market / Seller / Access / Risk). Reconciliation:

- **Value** → spread vs. comps (profit ratio exists today)
- **Market** → market velocity + days-on-market (velocity exists)
- **Seller** → motivation signals (exist: tax delinquent, absentee, probate, long ownership)
- **Access** → road/utilities/zoning — currently hardcoded; needs real attributes or "Unverified"
- **Risk** → inverse of data-quality issues + unverified flood/access items
- The site's evidence lines must render the actual computed reasons, not static strings.

---

## 6. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| County ToS prohibits scraping | Blocked source | Prefer bulk/portal data; contact county IT for permission; paid API fallback for that county only |
| Site markup changes break scrapers | Stale data | Version-pinned parsers, snapshot tests on 5 known parcels, alert on parse failure |
| CAPTCHA on search pages | Blocked | Delinquent-list bulk files first; paid API fallback |
| Rate-limit ban / county complaint | IP blocked, legal noise | Hard rate caps, off-peak windows, 7-day cache TTL, UA identifying DealScan |
| KV size limits | Truncated reports | Publish top-N + individual reports only; full dataset stays in Actions artifact / Postgres |
| Fabricated-looking scores | Credibility damage | Remove hardcoded accessibility; every evidence line traced to a real field; "Unverified" where data absent |
| Local env broken (Node 24 SIGBUS) | Dev friction | Build and test in GitHub Actions (Ubuntu), not this sandbox |

## 7. Costs

| Item | Cost |
|---|---|
| GitHub Actions | $0 (public repo unlimited; private free tier 2,000 min/mo) |
| Neon Postgres free tier | $0 |
| Vercel KV (current Upstash free tier) | $0 |
| Resend free tier | $0 (3,000 emails/mo) |
| Paid data API (only if scraping blocked) | $50–500/mo — decision deferred to Phase 1 findings |

**Total base plan: $0/mo.**

## 8. Definition of done

1. `--run` executes a real scrape → SQLite → scoring → publish with zero demo data
2. Site shows real Cochise reports with real `generated_at` timestamps and per-field evidence
3. Demo sections render **only** as clearly-labeled fallback
4. Weekly scheduled run with failure alerting
5. Waitlist entries flow into delivery

