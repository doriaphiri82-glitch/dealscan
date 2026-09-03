"""
DealScan AI - Main Pipeline Orchestrator

Usage:
    python main.py --setup-db       # Initialize database
    python main.py --run            # Run full pipeline
    python main.py --demo           # Run with demo data (for testing)
    python main.py --deliver        # Send daily deals to subscribers
    python main.py --probe-all      # Probe all configured county sources
    python main.py --health         # Show county health dashboard
    python main.py --counties       # List configured counties
    python main.py --expand         # Generate county expansion report
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.counties import COUNTY_SCRAPERS  # noqa: E402
from config.settings import MIN_DEAL_SCORE, MAX_DEALS_PER_EMAIL  # noqa: E402
from database import init_db, get_top_deals  # noqa: E402
from runners import run as run_county  # noqa: E402
from runregistry import load_bundle  # noqa: E402
from scoring.deal_scorer import score_and_enrich_deal  # noqa: E402
from scrapers.counties import probe_county  # noqa: E402
from cli.county_commands import add_county_commands  # noqa: E402


def _print_run_summary(summary: dict) -> None:
    counts = summary.get("counts", {})
    print(f"[{summary['county_id']}] {summary.get('status', 'unknown')}  "
          f"found={counts.get('discovered', counts.get('found', 0))} "
          f"downloaded={counts.get('downloaded', 0)} "
          f"parsed={counts.get('parsed', 0)} "
          f"normalized={counts.get('normalized', 0)} "
          f"rejected={counts.get('rejected', 0)} "
          f"stored={counts.get('stored', 0)} "
          f"scored={counts.get('scored', 0)} "
          f"published={counts.get('published', 0)}")
    if summary.get('error'):
        print(f"  ERROR: {summary['error'][:200]}")
    rejection = counts.get('rejection_reasons') or {}
    if rejection:
        print(f"  REJECTIONS: {rejection}")


def run_all(mode: str = 'publish', only: str = '') -> None:
    ids = [only] if only else list(COUNTY_SCRAPERS.keys())
    for cid in ids:
        summary = run_county(cid, mode=mode)
        _print_run_summary(summary)


def cmd_probe():
    """Probe configured data sources. Mark sources verified/blocked."""
    print("Probing county data sources...\n")
    for cid in COUNTY_SCRAPERS:
        for r in probe_county(cid):
            status = 'OK' if r.reachable else 'FAIL'
            print(f"  {status:4} {cid:12} {r.source_name:28} "
                  f"{r.detail or r.error[:60]}")
    print("\nSource probe complete.")


def cmd_run(args):
    init_db()
    mode = 'etl-only' if args.etl_only else 'publish'
    run_all(mode=mode, only=args.county or '')


def cmd_bundle():
    bundle = load_bundle()
    if bundle is None:
        print("No bundle present yet. Run --run first.")
        return
    print(f"generated_at={bundle.get('generated_at')}  "
          f"count={bundle.get('count')}  "
          f"counties={bundle.get('meta', {}).get('scraped_counties')}  "
          f"status={bundle.get('meta', {}).get('status')}")
    for d in bundle.get('deals', []):
        print(f"  {d.get('deal_score', 0):>3}/100  {d.get('county_id'):12}  "
              f"{d.get('address')}")


def main():
    global args
    parser = argparse.ArgumentParser(description='DealScan AI Pipeline')
    parser.add_argument('--setup-db', action='store_true')
    parser.add_argument('--run', action='store_true', help='Run scrapers')
    parser.add_argument('--county', '-c', help='Limit to one county id')
    parser.add_argument('--etl-only', action='store_true',
                        help='ETL without publishing the web bundle')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--probe', action='store_true',
                        help='Probe configured county data sources')
    parser.add_argument('--deliver', action='store_true')
    parser.add_argument('--bundle', action='store_true',
                        help='Show current web bundle summary')
    add_county_commands(parser.add_subparsers())
    args = parser.parse_args()

    if args.setup_db:
        init_db()
        print("Database initialized.")
    elif args.probe:
        cmd_probe()
    elif args.bundle:
        cmd_bundle()
    elif args.run:
        cmd_run(args)
    elif args.demo:
        init_db()
        run_demo_pipeline()
    elif args.deliver:
        print("Delivery requires EMAIL_API_KEY in .env. See pipeline README.")
    elif hasattr(args, 'func'):
        args.func()
    else:
        parser.print_help()


def run_demo_pipeline():
    """Keep original demo pipeline for local testing (no network)."""
    from demo_pipeline import run
    run()


if __name__ == '__main__':
    main()
