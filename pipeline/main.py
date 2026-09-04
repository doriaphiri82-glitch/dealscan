"""DealScan AI - Main Pipeline Orchestrator."""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrapers.counties import COUNTY_SCRAPERS, probe_county
from database import init_db, get_top_deals
from runners import run as run_county
from runregistry import load_bundle
from cli.county_commands import add_county_commands
from config.counties.national_registry import ensure_national_counties

def _print_run_summary(summary):
    c=summary.get("counts",{}); print(f"[{summary['county_id']}] {summary.get('status','unknown')} found={c.get('discovered',0)} downloaded={c.get('downloaded',0)} parsed={c.get('parsed',0)} normalized={c.get('normalized',0)} rejected={c.get('rejected',0)} stored={c.get('stored',0)} scored={c.get('scored',0)} published={c.get('published',0)}")
    if summary.get('error'): print(f"  ERROR: {summary['error'][:200]}")

def run_all(mode='publish',only=''):
    # Keep the national geography registry current. Only configured scrapers are run;
    # unconfigured counties remain explicitly NOT_COVERED instead of being misreported.
    ensure_national_counties()
    ids=[only] if only else list(COUNTY_SCRAPERS.keys())
    for cid in ids: _print_run_summary(run_county(cid,mode=mode))

def cmd_probe():
    ensure_national_counties(); print("Probing configured county data sources...\n")
    for cid in COUNTY_SCRAPERS:
        for r in probe_county(cid): print(f"  {'OK' if r.reachable else 'FAIL':4} {cid:12} {r.source_name:28} {r.detail or r.error[:60]}")
    print("\nSource probe complete.")

def cmd_run(args):
    init_db(); run_all(mode='etl-only' if args.etl_only else 'publish',only=args.county or '')

def cmd_bundle():
    bundle=load_bundle()
    if bundle is None: print("No bundle present yet. Run --run first."); return
    print(f"generated_at={bundle.get('generated_at')} count={bundle.get('count')} counties={bundle.get('meta',{}).get('scraped_counties')} status={bundle.get('meta',{}).get('status')}")
    for d in bundle.get('deals',[]): print(f"  {d.get('deal_score',0):>3}/100 {d.get('county_id',''):12} {d.get('address','')}")

def run_demo_pipeline():
    from demo_pipeline import run; run()

def main():
    parser=argparse.ArgumentParser(description='DealScan AI Pipeline'); parser.add_argument('--setup-db',action='store_true'); parser.add_argument('--run',action='store_true'); parser.add_argument('--county','-c'); parser.add_argument('--etl-only',action='store_true'); parser.add_argument('--demo',action='store_true'); parser.add_argument('--probe',action='store_true'); parser.add_argument('--deliver',action='store_true'); parser.add_argument('--bundle',action='store_true'); add_county_commands(parser.add_subparsers()); args=parser.parse_args()
    if args.setup_db: init_db(); print('Database initialized.')
    elif args.probe: cmd_probe()
    elif args.bundle: cmd_bundle()
    elif args.run: cmd_run(args)
    elif args.demo: init_db(); run_demo_pipeline()
    elif args.deliver: print('Delivery requires EMAIL_API_KEY in .env. See pipeline README.')
    elif hasattr(args,'func'): args.func()
    else: parser.print_help()

if __name__=='__main__': main()
