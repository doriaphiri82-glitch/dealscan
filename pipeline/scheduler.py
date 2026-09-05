"""Compatibility scheduler; all work delegates to the gated, bounded CLI.

Production scheduling belongs to .github/workflows/scrape.yml. The optional local
watcher is never a second path around registry hydration or failure reporting.
"""
from __future__ import annotations
import argparse
import os
import time
from main import main as pipeline_main, bounded


def run_all_counties(mode: str = 'etl-only', county: str | None = None, max_records: int = 250) -> int:
    if mode not in {'publish','etl-only'}: raise ValueError('Unsupported scheduler mode')
    argv = ['--run','--max-records',str(max_records)]
    if mode == 'etl-only': argv.append('--etl-only')
    if county: argv.extend(['--county',county])
    return pipeline_main(argv)


def main(argv=None):
    parser = argparse.ArgumentParser(description='DealScan gated local scheduler')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--run-once',action='store_true')
    action.add_argument('--watch','-w',action='store_true',help='Local only; production uses GitHub Actions')
    parser.add_argument('--county','-c')
    parser.add_argument('--mode','-m',default='etl-only',choices=['publish','etl-only'])
    parser.add_argument('--max-records',type=lambda v:bounded(v,1,5000),default=250)
    args = parser.parse_args(argv)
    if args.watch:
        if os.getenv('DEALSCAN_ENV') == 'production':
            parser.error('Production scheduling must use the controlled ingestion workflow')
        try:
            import schedule
        except ImportError:
            print('Install the pinned pipeline dependencies to use the local watcher')
            return 1
        def job():
            code = run_all_counties(args.mode,args.county,args.max_records)
            print(f'Scheduled ingestion exit_code={code}; no work or partial results are failures')
        schedule.every().day.at('06:30').do(job)
        print('Local scheduler started; no ingestion has run yet')
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            return 130
    if args.run_once or args.county:
        return run_all_counties(args.mode,args.county,args.max_records)
    parser.print_help()
    return 0


if __name__ == '__main__': raise SystemExit(main())
