# DealScan AI - Data Pipeline
# Core engine for finding, scoring, and delivering land deals

## Architecture

```
pipeline/
├── config/
│   ├── counties.py          # County configurations (URLs, data formats)
│   └── settings.py          # Global settings (thresholds, scoring weights)
├── scrapers/
│   ├── base.py              # Base scraper class
│   ├── county_scraper.py    # County-specific data collection
│   └── comps_scraper.py     # Comparable sales data
├── scoring/
│   ├── deal_scorer.py       # Deal scoring algorithm (1-100)
│   ├── profit_calculator.py # Profit estimation engine
│   └── motivated_seller.py  # Motivated seller signal detection
├── delivery/
│   ├── email_sender.py      # Daily email delivery
│   └── templates.py         # Email templates
├── models.py                # Data models
├── database.py              # SQLite database management
├── main.py                  # Main pipeline orchestrator
└── requirements.txt         # Python dependencies
```

## Setup

```bash
cd pipeline
pip install -r requirements.txt
python main.py --setup-db    # Initialize database
python main.py --run         # Run full pipeline
python main.py --county cochise_az  # Run for specific county
```

## How It Works

1. **Collect**: Scrape county assessor data for target counties
2. **Filter**: Identify motivated seller signals
3. **Enrich**: Pull comparable sales data
4. **Score**: Calculate deal score (1-100) and profit estimate
5. **Deliver**: Send top deals via email/community
