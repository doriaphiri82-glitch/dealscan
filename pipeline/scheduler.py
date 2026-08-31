"""
DealScan - Pipeline scheduling.

Two integration paths:
  * GitHub Actions workflow (pipeline/.github/workflows/scrape.yml) runs
    `python -m scheduler --run-once` on a cron. That's the production path:
    it has real network access to county sources.
  * Local `--watch` uses the `schedule` package for CLI demos / manual runs.

`schedule` (in requirements.txt) is optional at import time so the module
imports cleanly even if it's not installed in a given environment.
"""
from __future__ import annotations

import argparse
import time

from runners import COUNTRY_RUNNERS


def run_all_counties(mode: str = "publish") -> dict:
    """Run every configured county scraper in order. Returns summary."""
    results = {}
    for county_id, runner in COUNTRY_RUNNERS.items():
        try:
            results[county_id] = runner.run(mode=mode)
        except Exception as exc:  # keep going if one county fails
            results[county_id] = {"status": "error", "error": str(exc)[:200]}
    return results


def main():
    parser = argparse.ArgumentParser(description="DealScan pipeline scheduler")
    parser.add_argument("--run-once", action="store_true",
                        help="Run all counties once and exit (CI cron)")
    parser.add_argument("--watch", "-w", action="store_true",
                        help="Run forever on a schedule (local)")
    parser.add_argument("--county", "-c", choices=list(COUNTRY_RUNNERS.keys()),
                        help="Run only one county")
    parser.add_argument("--mode", "-m", default="publish",
                        choices=["publish", "etl-only"],
                        help="publish=write bundle; etl-only=no output")
    args = parser.parse_args()

    if args.county:
        runner = COUNTRY_RUNNERS[args.county]
        runner.run(mode=args.mode)
        return

    if args.run_once:
        results = run_all_counties(mode=args.mode)
        for cid, res in results.items():
            print(f"{cid}: {res.get('status')} "
                  f"(found={res.get('counts', {}).get('found', 0)}, "
                  f"saved={res.get('counts', {}).get('saved', 0)})")
        return

    if args.watch:
        try:
            import schedule  # type: ignore
        except ImportError:
            print("schedule not installed - install (pip install schedule) "
                  "or run with --run-once")
            return
        schedule.every().day.at("06:30").do(run_all_counties, mode=args.mode)
        schedule.every().monday.at("02:00").do(run_all_counties, mode=args.mode)
        print("Scheduler started. Ctrl+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(60)
        return

    parser.print_help()


if __name__ == "__main__":
    main()