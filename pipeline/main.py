"""DealScan AI - Main Pipeline Orchestrator."""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrapers.counties import COUNTY_SCRAPERS, probe_county
from database import init_db
from runners import run as run_county
from runregistry import load_bundle
from cli.county_commands import add_county_commands
from config.counties.national_registry import ensure_national_counties
from config.counties.registry import county_summary, list_counties


def _print_run_summary(summary):
    c=summary.get("counts",{}); print(f"[{summary.get('county_id','?')}] {summary.get('status','unknown')} found={c.get('discovered',0)} downloaded={c.get('downloaded',0)} parsed={c.get('parsed',0)} normalized={c.get('normalized',0)} rejected={c.get('rejected',0)} stored={c.get('stored',0)} scored={c.get('scored',0)} qualified={c.get('qualified',0)} published={c.get('published',0)}")
    if summary.get("error"): print(f"  ERROR: {summary['error'][:300]}")

def run_all(mode='publish',only=''):
    ensure_national_counties(); ids=[only] if only else list(COUNTY_SCRAPERS.keys())
    for cid in ids:_print_run_summary(run_county(cid,mode=mode))

def cmd_probe():
    ensure_national_counties(); print("Probing configured county data sources...\n")
    for cid in COUNTY_SCRAPERS:
        for r in probe_county(cid):print(f"  {'OK' if r.reachable else 'FAIL':4} {cid:12} {r.source_name:28} {r.detail or r.error[:60]}")
    print("\nSource probe complete.")

def cmd_run(args):
    init_db(); run_all(mode='etl-only' if args.etl_only else 'publish',only=args.county or '')

def cmd_discover(args):
    from discovery.national_source_worker import discover_and_register
    result=discover_and_register(args.discover_national); print(f"National discovery: attempted={result['attempted']} found={result['found']}")
    for row in result['results']:print(f"  {row['county_id']:24} {row['status']:12} fields={row.get('field_count','-')} {row.get('url','')}")

def cmd_run_national(args):
    from discovery.national_source_worker import run_national_batch
    init_db(); result=run_national_batch(args.run_national,args.max_records,'etl-only' if args.etl_only else 'publish'); print(f"National ETL: attempted={result['attempted']} ok={result['ok']}")
    for row in result['results']:_print_run_summary(row)

def cmd_validate():
    ensure_national_counties(); from validation.national_validator import validate_all_counties
    report=validate_all_counties(); c=report['counts']; print(f"National config validation: total={c['total']} ready={c['ready']} invalid={c['invalid']} not_started={c['not_started']} etl_verified={c['etl_verified']}")
    for row in report['results']:
        if row['status']!='ready':print(f"  {row['county_id']:28} {row['status']:12} {'; '.join(row.get('errors',[])[:3])}")
    print("Configuration validation is read-only; it does not claim live source health or ETL success.")

def cmd_validate_live(args):
    ensure_national_counties(); from validation.live_validator import validate_live_batch
    report=validate_live_batch(args.validate_live,args.include_validated); print(f"National live validation: attempted={report['attempted']} valid={report['valid']} invalid={report['invalid']} unreachable={report['unreachable']}")
    for row in report['results']:
        detail='; '.join(row.get('errors',[])[:2]); print(f"  {row['county_id']:28} {row['status']:12} {detail}")

def cmd_coverage():
    ensure_national_counties(); s=county_summary(); counties=list_counties(); total=s['total'] or 1
    discovered=sum(1 for c in counties if c.get('data_source_type') or c.get('arcgis_layer_url') or c.get('parcel_source_url'))
    source_verified=sum(1 for c in counties if c.get('verification_status') in ('source_verified','verified'))
    live_verified=sum(1 for c in counties if c.get('validation_status')=='valid')
    etl_verified=sum(1 for c in counties if c.get('verification_status')=='verified')
    covered=sum(1 for c in counties if c.get('coverage_status') in ('tier_4','tier_5') and c.get('last_successful_run'))
    published=sum(1 for c in counties if c.get('coverage_status')=='tier_5' and c.get('last_successful_run'))
    print(f"National counties: {s['total']}")
    print(f"Sources discovered: {discovered} ({discovered/total:.1%})")
    print(f"Sources field/sample live-validated: {live_verified} ({live_verified/total:.1%})")
    print(f"Sources verified by successful ETL: {etl_verified} ({etl_verified/total:.1%})")
    print(f"Actually covered with persisted ETL data: {covered} ({covered/total:.1%})")
    print(f"Counties with published deals: {published} ({published/total:.1%})")
    print(f"By status: {s['by_coverage_status']}")

def cmd_bundle():
    bundle=load_bundle()
    if bundle is None:print("No bundle present yet. Run --run or --run-national first.");return
    print(f"generated_at={bundle.get('generated_at')} count={bundle.get('count')} counties={bundle.get('meta',{}).get('scraped_counties')} status={bundle.get('meta',{}).get('status')}")
    for d in bundle.get('deals',[]):print(f"  {d.get('deal_score',0):>3}/100 {d.get('county_id',''):12} {d.get('address','')}")

def run_demo_pipeline():
    from demo_pipeline import run;run()

def main():
    parser=argparse.ArgumentParser(description='DealScan AI Pipeline'); parser.add_argument('--setup-db',action='store_true'); parser.add_argument('--run',action='store_true'); parser.add_argument('--county','-c'); parser.add_argument('--etl-only',action='store_true'); parser.add_argument('--demo',action='store_true'); parser.add_argument('--probe',action='store_true'); parser.add_argument('--deliver',action='store_true'); parser.add_argument('--bundle',action='store_true'); parser.add_argument('--discover-national',type=int,metavar='N',help='Discover up to N new public ArcGIS sources'); parser.add_argument('--run-national',type=int,metavar='N',help='Run up to N discovered counties through ETL'); parser.add_argument('--validate-live',type=int,metavar='N',help='Live-validate up to N counties with discovered/configured sources'); parser.add_argument('--include-validated',action='store_true',help='Allow live validation to revisit recently validated counties'); parser.add_argument('--max-records',type=int,default=5000); parser.add_argument('--coverage',action='store_true'); parser.add_argument('--validate',action='store_true',help='Validate every registered county configuration without changing coverage state'); add_county_commands(parser.add_subparsers()); args=parser.parse_args()
    if args.setup_db:init_db();print('Database initialized.')
    elif args.probe:cmd_probe()
    elif args.validate:cmd_validate()
    elif args.validate_live is not None:cmd_validate_live(args)
    elif args.coverage:cmd_coverage()
    elif args.discover_national is not None:cmd_discover(args)
    elif args.run_national is not None:cmd_run_national(args)
    elif args.bundle:cmd_bundle()
    elif args.run:cmd_run(args)
    elif args.demo:init_db();run_demo_pipeline()
    elif args.deliver:print('Delivery requires EMAIL_API_KEY in .env. See pipeline README.')
    elif hasattr(args,'func'):args.func()
    else:parser.print_help()

if __name__=='__main__':main()
