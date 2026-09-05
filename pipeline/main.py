"""DealScan CLI. Failed, partial, skipped or unattempted ingestion is nonzero."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from database import get_backend, init_db, verify_deal
from runners import run as run_county
from config.counties.national_registry import ensure_national_counties, ensure_pilot_counties
from config.counties.registry import _load_registry, list_counties
from config.source_config import county_config
from validation.gates import authorization_error, authorize_county, authorize_validated_batch, validation_error
from validation.live_validator import validate_live_batch
from registry_sync import pull_registry, push_registry


def bounded(value, low=0, high=100):
    try: result=int(value)
    except ValueError: raise argparse.ArgumentTypeError('Expected an integer') from None
    if not low<=result<=high: raise argparse.ArgumentTypeError(f'Expected {low}–{high}')
    return result


def completed(result, success_key='ok', expected_work=True):
    if 'status' in result: return result['status'] in {'ok','completed','verified'}
    attempted=result.get('attempted',0)
    return (not expected_work and attempted==0) or attempted>0 and result.get(success_key,0)==attempted


def safe_report(value):
    private={'raw_payload','raw_payload_canonical','normalized_payload','field_mapping','source_config','source_authorization','registry_patch',
             'owner_name','owner_address','owner_state','email','financial_evidence','token','key','password'}
    if isinstance(value,dict): return {key:safe_report(item) for key,item in value.items() if key not in private and not key.startswith('_')}
    if isinstance(value,list): return [safe_report(item) for item in value]
    return value


def coverage():
    counties=list_counties(); meta=_load_registry().get('meta',{})
    configs={county['county_id']:county_config(county['county_id'],county) for county in counties}
    return {'scope':'county_registry','counties':len(counties),'universe_complete':bool(meta.get('universe_complete')),
            'universe_source':meta.get('universe_source'),'discovered':sum(bool(cfg.get('arcgis_layer_url') or cfg.get('data_url')) for cfg in configs.values()),
            'validating':sum(c.get('validation_status')=='validating' for c in counties),
            'live_validated':sum(not validation_error(c,configs[c['county_id']]) for c in counties),
            'ingestion_ready':sum(not authorization_error(c,configs[c['county_id']]) for c in counties),
            'ingested':sum(c.get('ingestion_status')=='ingested' and (c.get('persisted_count') or 0)>0 for c in counties),
            'unavailable':sum(c.get('validation_status') in {'invalid','unreachable'} for c in counties),
            'note':'County geography and configured sources do not imply national parcel or opportunity coverage'}


def run_all(mode='publish',only='',max_records=5000):
    from validation.gates import authorization_error
    counties=list_counties()
    ids=[only] if only else [c['county_id'] for c in counties if not authorization_error(c,county_config(c['county_id'],c))]
    results=[run_county(cid,mode=mode,max_records=max_records) for cid in ids]
    return {'attempted':len(results),'ok':sum(completed(row) for row in results),'results':results}


def production_smoke(county_id, max_records, app_url):
    from validation.production_smoke import public_key, verify_ingestion, web_origin
    if os.getenv('DEALSCAN_DB_BACKEND')!='supabase' or os.getenv('DEALSCAN_ENV')!='production':
        raise RuntimeError('Production smoke requires DEALSCAN_ENV=production and DEALSCAN_DB_BACKEND=supabase')
    from database_supabase import SupabaseDatabase
    if not isinstance(get_backend(),SupabaseDatabase):
        raise RuntimeError('The initialized database backend is not Supabase')
    # Reject missing deployment/RLS configuration before making ingestion writes.
    web_origin(app_url or ''); public_key(); init_db()
    validation=validate_live_batch(1,True,county_id=county_id)
    push_registry()
    if not completed(validation,'valid'): return {'status':'error','stage':'validate','validation':validation}
    authorization=authorize_county(county_id); push_registry()
    if not authorization['authorized']: return {'status':'error','stage':'authorize','authorization':authorization}
    ingestion=run_county(county_id,mode='etl-only',max_records=max_records)
    if not completed(ingestion): return {'status':'error','stage':'ingest','ingestion':ingestion}
    verified=verify_ingestion(ingestion['audit_run_id'],county_id=county_id,max_records=max_records,app_url=app_url,require_web=True)
    return {'status':'verified','scope':'bounded_real_ingestion_and_public_api','ingestion':ingestion,'verification':verified,
            'note':'No deal is automatically published; zero verified opportunities is valid when financial evidence is missing'}


def parser():
    p=argparse.ArgumentParser(description='Source-backed DealScan pipeline')
    action=p.add_mutually_exclusive_group()
    for flag in ('setup-db','run','probe','bundle','coverage','validate','refresh-universe','sync-registry','statewide-audit','deliver'):
        action.add_argument('--'+flag,action='store_true')
    for flag in ('discover-national','run-national','validate-live','authorize-valid'):
        action.add_argument('--'+flag,type=bounded,metavar='N')
    action.add_argument('--authorize-county')
    action.add_argument('--verify-deal',type=lambda v:bounded(v,1,2**63-1),metavar='ID')
    action.add_argument('--verify-ingestion-run',type=lambda v:bounded(v,1,2**63-1),metavar='ID')
    action.add_argument('--production-smoke',metavar='COUNTY_ID')
    p.add_argument('--county','-c')
    p.add_argument('--max-records',type=lambda v:bounded(v,1,5000),default=250)
    p.add_argument('--etl-only',action='store_true')
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--include-validated',action='store_true')
    p.add_argument('--app-url',default=os.getenv('PRODUCTION_APP_URL'))
    p.add_argument('--require-web-api',action='store_true')
    p.add_argument('--report-file')
    p.add_argument('--states',default='')
    p.add_argument('--discovery-limit',type=bounded,default=25)
    p.add_argument('--etl-limit',type=bounded,default=0)
    from cli.county_commands import add_county_commands
    add_county_commands(p.add_subparsers())
    return p


def main(argv=None):
    p=parser(); args=p.parse_args(argv)
    if args.dry_run and not (args.run or args.run_national is not None or args.discover_national is not None or args.statewide_audit):
        p.error('--dry-run is supported only for ingestion and source discovery')
    mutable=any((args.run,args.run_national is not None,args.validate_live is not None,args.authorize_county,
                 args.authorize_valid is not None,args.discover_national is not None,args.refresh_universe,args.sync_registry,args.production_smoke)) and not args.dry_run
    needs_registry = mutable or args.coverage or args.validate or args.probe or args.dry_run or hasattr(args,'func')
    result={}; code=0; registry_loaded=False
    try:
        if needs_registry:
            pull_registry()
            if mutable: ensure_pilot_counties()
            registry_loaded=True
        if args.setup_db: init_db(); result={'status':'ok','schema':'checked'}
        elif args.refresh_universe:
            ensure_national_counties(); result=coverage()
            code=0 if _load_registry().get('meta',{}).get('universe_refresh_status')=='ok' else 1
        elif args.sync_registry: push_registry(); result={'status':'ok','scope':'registry_metadata'}
        elif args.validate_live is not None:
            result=validate_live_batch(args.validate_live,args.include_validated,county_id=args.county)
            code=0 if completed(result,'valid',args.validate_live>0) else 1
        elif args.authorize_county:
            result=authorize_county(args.authorize_county); code=0 if result['authorized'] else 1
        elif args.authorize_valid is not None:
            result=authorize_validated_batch(args.authorize_valid)
            code=0 if completed(result,'authorized',args.authorize_valid>0) else 1
        elif args.run:
            result=run_all(mode='dry_run' if args.dry_run else 'etl-only' if args.etl_only else 'publish',only=args.county or '',max_records=args.max_records)
            code=0 if completed(result) else 1
        elif args.run_national is not None:
            from discovery.national_source_worker import run_national_batch
            result=run_national_batch(args.run_national,args.max_records,'dry_run' if args.dry_run else 'etl-only' if args.etl_only else 'publish')
            code=0 if completed(result,expected_work=args.run_national>0) else 1
        elif args.discover_national is not None:
            from discovery.national_source_worker import discover_and_register
            result=discover_and_register(args.discover_national,persist=not args.dry_run)
            code=1 if result.get('statewide_error') or any(row.get('status')=='error' for row in result.get('results',[])) else 0
        elif args.production_smoke:
            result=production_smoke(args.production_smoke,args.max_records,args.app_url)
            code=0 if completed(result) else 1
        elif args.verify_ingestion_run:
            from validation.production_smoke import verify_ingestion
            result=verify_ingestion(args.verify_ingestion_run,county_id=args.county,max_records=args.max_records,
                                    app_url=args.app_url,require_web=args.require_web_api)
        elif args.verify_deal:
            init_db(); result=verify_deal(args.verify_deal)
        elif args.coverage: result=coverage()
        elif args.validate:
            from validation.national_validator import validate_all_counties
            result=validate_all_counties()
            result['scope']='configuration_only_not_live_validation'
            code=1 if result.get('counts',{}).get('invalid') else 0
        elif args.statewide_audit:
            from discovery.national_source_worker import run_statewide_batch
            result=run_statewide_batch(states=[s.strip() for s in args.states.split(',') if s.strip()] or None,
                discovery_limit=args.discovery_limit,etl_limit=args.etl_limit,max_records=args.max_records,mode='dry_run')
            etl=result.get('etl',{})
            code=1 if (args.etl_limit and not completed(etl)) or result.get('discovery',{}).get('statewide_error') else 0
        elif args.probe:
            from scrapers.counties import COUNTY_SCRAPERS,probe_county
            result={'results':[{'county_id':cid,'reachable':r.reachable,'error':r.error} for cid in ([args.county] if args.county else COUNTY_SCRAPERS) for r in probe_county(cid)]}
            code=0 if result['results'] and all(row['reachable'] for row in result['results']) else 1
        elif args.bundle:
            from runregistry import load_bundle
            value=load_bundle()
            result={'status':'ok' if value else 'not_found','count':value.get('count') if value else None}
            code=0 if value else 1
        elif args.deliver:
            result={'status':'unavailable','error':'Automated email delivery requires configured consent, unsubscribe and delivery controls'}; code=1
        elif hasattr(args,'func'):
            result=args.func() or {'status':'ok','scope':'registry_display'}
            code=0 if completed(result) else 1
        else: p.print_help(); return 0
    except Exception as exc:
        # Request bodies and source/owner data must never enter workflow artifacts.
        result={'status':'error','error':f'{type(exc).__name__}: operation failed; check configuration, schema and source connectivity'}
        code=1
    finally:
        if mutable and registry_loaded:
            try: push_registry()
            except Exception as exc:
                result['registry_sync']='unavailable'; result['status']='degraded' if code==0 else 'error'; code=1
    report=safe_report(result)
    print(json.dumps(report,indent=2,allow_nan=False))
    if args.report_file:
        path=Path(args.report_file); path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return code


if __name__=='__main__': raise SystemExit(main())
