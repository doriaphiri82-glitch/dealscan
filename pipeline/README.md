# DealScan Pipeline

Land-deal screening pipeline: scrapes county parcel data, scores deals, and
publishes a web bundle. See also `docs/DATA_PIPELINE_SCOPE.md` for the full
plan and `scrapers/` for data sources.

## Layout

```
pipeline/
├── config/            # counties + settings
├── scrapers/
│   ├── base.py        # polite HTTP + cache + robots.txt + probing
│   ├── argis.py       # ArcGIS REST adapter (parcel layers)
│   └── counties.py    # per-county source registry
├── scoring/           # deal_scorer (signals, ARV, 1-100 score)
├── delivery/          # email digest (Resend/SendGrid/console)
├── runners.py         # orchestration of one county run
├── scheduler.py       # daily/weekly scheduling + --run-once (CI)
├── publish.py         # push bundle to Vercel KV / REDIS_URL
├── runregistry.py     # run history + bundle artifact
├── demo_pipeline.py   # offline demo data run
├── main.py            # CLI (setup-db / run / probe / dry-run / bundle / demo)
└── tests/             # offline unit tests
```

## Commands

```bash
python main.py --setup-db                    # create SQLite schema
python main.py --run                         # scrape + score + publish bundle
python main.py --run --county cochise_az     # one county
python main.py --run --etl-only              # ETL only, no publish
python main.py --probe                       # probe county data sources
python main.py --dry-run --county cochise_az # ETL offline (data_file mode)
python main.py --bundle                      # show published bundle summary
python main.py --demo                        # offline demo run
python scheduler.py --run-once               # all counties once (CI cron)
python scheduler.py --watch                  # scheduled local loop (needs schedule)
```

## Scheduling

* **Production (recommended):** `.github/workflows/scrape.yml` (repo root)
  runs `scheduler.py --run-once` on a cron — daily delta + weekly full —
  inside GitHub Actions, then commits `pipeline/data/bundle.json` +
  `registry.json` and copies them to `landing/data/` so Vercel serves the
  latest artifact.
* **Local:** `python scheduler.py --watch`.

## Publishing to the webapp

Producers write `data/bundle.json` (top scored deals) + `data/registry.json`
(run history). The webapp reads, in order:

1. `REDIS_URL` — Upstash REST (`https://`) or native (`redis://`)
2. `KV_REST_API_URL` + `KV_REST_API_TOKEN` — Vercel KV REST
3. committed `landing/data/bundle.json` artifact

Set the secret in GitHub Actions to publish through your store. Otherwise the
committed artifact is used automatically (deploy-time snapshot).

## Tests

```bash
python -m pytest pipeline/tests/   # offline fixtures, no network
```

## Delivery

`delivery/email_sender.py` sends the daily digest. Configure
`EMAIL_PROVIDER` + `EMAIL_API_KEY` in `.env` (see `.env.example`).