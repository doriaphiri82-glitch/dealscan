"""Read-only production handoff checks. Never authorize, ingest, seed or migrate.

Can run with missing credentials so the protected workflow reports precisely
which external configuration is absent without revealing any secret values.
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from validation.production_smoke import SmokeFailure, _get, public_key, verify_public_api, web_origin


EXPECTED_CONTACT = 'doriaphiri82@gmail.com'


def probe_source(county_id: str) -> dict:
    from config.counties.national_registry import PILOT_COUNTIES
    from config.source_config import county_config
    from scrapers import arcgis
    from normalization import normalize
    from validation.etl_validator import validate_county_config
    if county_id not in PILOT_COUNTIES:
        raise SmokeFailure('Readiness probing requires an exact configured pilot county')
    cfg = county_config(county_id, PILOT_COUNTIES[county_id])
    layer = cfg['arcgis_layer_url']
    metadata = arcgis.layer_metadata(layer, live=True)
    if metadata.get('type') != 'Feature Layer' or 'Query' not in str(metadata.get('capabilities', '')):
        raise SmokeFailure('The configured source is not a queryable parcel layer')
    fields = [field['name'] for field in metadata.get('fields', []) if field.get('name')]
    cfg['fields'] = arcgis.resolve_field_mapping(cfg.get('fields') or {}, fields)
    report = validate_county_config(county_id, cfg, source_fields=fields)
    if not report['valid']:
        raise SmokeFailure('The configured mapping does not match live source fields')
    # Query only identity/area/vacancy/location facts; no owner sample is exported.
    selected = []
    for field in ('apn','lot_size_acres','lot_size_unit','improvement_value','land_use','use_code','latitude','longitude'):
        value = cfg['fields'].get(field)
        selected.extend(value if isinstance(value,(tuple,list)) else [value] if value else [])
    count = arcgis.query_count(layer, cfg.get('where','1=1'))
    if count < 1:
        raise SmokeFailure('The source query returned no real records')
    diagnostics = {}
    sample = list(arcgis.query_layer(layer, cfg.get('where','1=1'), list(dict.fromkeys(selected)),
                  max_records=min(count,5), page_size=2, metadata=metadata, diagnostics=diagnostics))
    if len(sample) != min(count,5) or (count>2 and diagnostics.get('pages',0)<2):
        raise SmokeFailure('Source sample pagination was not demonstrated')
    normalized = [normalize(row,cfg) for row in sample]
    if not all(row.get('apn') and row.get('lot_size_acres') for row in normalized):
        raise SmokeFailure('Source samples lack usable parcel identity or acreage')
    return {'status':'passed','scope':'technical_read_only_sample','county_id':county_id,
            'source_url':layer,'object_id_field':arcgis.object_id_field(metadata),
            'source_count':count,'sample_checked':len(sample),'pages_checked':diagnostics.get('pages',0),
            'ingestion_authorized':False}


def database_counts(db) -> dict:
    totals = {}
    for table in ('counties','properties','deals','ingestion_runs','ingestion_records'):
        field = 'county_id' if table=='counties' else 'id'
        response = db._request('HEAD',table,params={'select':field,'limit':'0'},
                               headers={**db.headers,'Prefer':'count=exact'})
        total = response.headers.get('Content-Range','').rsplit('/',1)[-1]
        if not total.isdigit():
            raise SmokeFailure('Database did not return an exact count for '+table)
        totals[table] = int(total)
    return totals


def deployment_probe(app_url: str, expected_contact: str) -> dict:
    origin = web_origin(app_url)
    response = _get(origin+'/api/health')
    if response.status_code != 200:
        return {'status':'failed','http_status':response.status_code,'reason':'deployed_health_unavailable'}
    body = response.json()
    if not isinstance(body,dict) or body.get('database') != 'ok' or not body.get('database_origin'):
        return {'status':'failed','reason':'deployed_database_contract_not_ready'}
    privacy = _get(origin+'/privacy')
    contact_matches = privacy.status_code==200 and 'mailto:'+expected_contact in privacy.text
    return {'status':'passed' if contact_matches else 'failed','http_status':200,
            'operator_contact_matches':contact_matches,'reason':None if contact_matches else 'operator_contact_not_deployed'}


def _failure(exc: Exception) -> dict:
    # Never export arbitrary exception bodies, credentials, source rows or SQL.
    return {'status':'failed','reason':str(exc) if isinstance(exc,SmokeFailure) else type(exc).__name__}


def run_preflight(county_id: str, app_url: str, max_records: int = 250) -> dict:
    checks = {}
    missing = [key for key in ('SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY') if not os.getenv(key)]
    public = False
    try:
        public_key()
        public = True
    except SmokeFailure:
        missing.append('SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY')
    mode_ok = os.getenv('DEALSCAN_ENV')=='production' and os.getenv('DEALSCAN_DB_BACKEND')=='supabase'
    if not mode_ok: missing.append('explicit production Supabase mode')
    contact = os.getenv('WAITLIST_CONTACT_EMAIL') or ''
    if contact != EXPECTED_CONTACT: missing.append('requested WAITLIST_CONTACT_EMAIL')
    checks['configuration'] = {'status':'passed' if not missing else 'failed','missing':missing}
    checks['platform_access'] = {key:bool(os.getenv(key)) or os.getenv('HAS_'+key)=='true' for key in ('VERCEL_TOKEN','SUPABASE_ACCESS_TOKEN','SUPABASE_DB_URL')}
    try:
        checks['deployment'] = deployment_probe(app_url,EXPECTED_CONTACT)
    except Exception as exc: checks['deployment'] = _failure(exc)
    try:
        checks['source'] = probe_source(county_id)
    except Exception as exc: checks['source'] = _failure(exc)
    if mode_ok and os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
        try:
            from database_supabase import SupabaseDatabase
            db = SupabaseDatabase()
            db.init_db()
            checks['database'] = {'status':'passed','schema_columns_checked':True,'counts':database_counts(db)}
        except Exception as exc:
            checks['database'] = _failure(exc)
        if checks['database']['status']=='passed' and public:
            try: checks['public_boundary'] = verify_public_api(db,app_url,expected_contact=EXPECTED_CONTACT)
            except Exception as exc: checks['public_boundary'] = _failure(exc)
        else:
            checks['public_boundary'] = {'status':'not_checked','reason':'database_access_schema_or_public_key_missing'}
    else:
        checks['database'] = {'status':'not_checked','reason':'private_configuration_missing'}
        checks['public_boundary'] = {'status':'not_checked','reason':'private_configuration_missing'}
    ready = all(checks[name].get('status') in {'passed','verified'}
                for name in ('configuration','deployment','source','database','public_boundary'))
    return {'status':'ready_for_bounded_smoke' if ready else 'blocked',
            'scope':'production_preflight_read_only','county_id':county_id,'planned_record_limit':max_records,
            'checked_at':datetime.now(timezone.utc).isoformat(),'commit':os.getenv('GITHUB_SHA'),
            'checks':checks,'production_writes_performed':False,'ingestion_status':'not_attempted',
            'note':'Passing preflight is not an ingestion, migration, authority-review or authenticated-login success'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--county',default='el_paso_tx')
    parser.add_argument('--app-url',required=True)
    parser.add_argument('--max-records',type=int,default=250)
    parser.add_argument('--report-file',required=True)
    args = parser.parse_args(argv)
    if not 1<=args.max_records<=5000: parser.error('Record limit must be 1–5000')
    report = run_preflight(args.county,args.app_url,args.max_records)
    path = Path(args.report_file); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if os.getenv('GITHUB_ACTIONS')=='true':
        # Keep minimized evidence readable through the Checks API as well as
        # blob-backed logs/artifacts. Never print source records or secret values.
        message=json.dumps(report,separators=(',',':')).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        level='notice' if report['status']=='ready_for_bounded_smoke' else 'error'
        print(f'::{level} title=Read-only production readiness::{message}')
    return 0 if report['status']=='ready_for_bounded_smoke' else 1


if __name__=='__main__': raise SystemExit(main())
