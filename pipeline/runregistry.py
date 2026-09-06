"""Private local run summaries and verified-only cache snapshots.

Supabase/SQLite audit rows are authoritative. Local files are operational aids,
never a fallback for the public API and never an excuse to report false success.
"""
from __future__ import annotations
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from normalization import sale_date
from persistence import AuditRunNotFound, PUBLIC_COMP_FIELDS, PUBLIC_DEAL_FIELDS, PUBLIC_PROPERTY_FIELDS

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
REGISTRY_PATH = os.path.join(DATA_DIR, 'registry.json')
BUNDLE_PATH = os.path.join(DATA_DIR, 'bundle.json')
log = logging.getLogger(__name__)


def _read(path, default):
    try:
        with open(path, encoding='utf-8') as file: return json.load(file)
    except FileNotFoundError: return default


def _atomic_write(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=os.path.dirname(path), delete=False) as file:
            temporary = file.name
            json.dump(payload, file, allow_nan=False, indent=1)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)


def load_registry():
    return _read(REGISTRY_PATH, {'runs': [], 'last_run': None})


def record_run(county_id, status, counts, error='', *, audit=True, run_id=None, source_url=None, metadata=None):
    entry = {'county_id': county_id, 'status': status, 'counts': dict(counts), 'error': error,
             'at': datetime.now(timezone.utc).isoformat(), 'audit_status': 'not_started'}
    if audit:
        from database import get_backend
        db = get_backend()
        run_id = run_id or db.active_run_id(county_id)
        try:
            if run_id:
                try:
                    db.update_ingestion_run(run_id, county_id, status, counts, error, metadata=metadata)
                except AuditRunNotFound:
                    # Only a positively identified lost/mismatched audit context
                    # may be recovered. A timeout is NOT evidence of a missing run.
                    recovery = {**(metadata or {}), 'recovered_from_run_id': run_id, 'audit_gap': True}
                    entry.update(status='degraded' if status == 'ok' else status, audit_status='recovered_with_gap',
                                 error=(error+'; Original audit run unavailable; reconciliation required').strip('; '))
                    run_id = db.record_ingestion_run(county_id, entry['status'], counts,
                        'Original audit run unavailable; primary records require reconciliation', source_url=source_url, metadata=recovery)
            else:
                if (metadata or {}).get('audit_gap'):
                    raise RuntimeError('Audit start outcome is unknown; do not create a duplicate run')
                run_id = db.record_ingestion_run(county_id, status, counts, error, source_url=source_url, metadata=metadata)
            entry['audit_run_id'] = run_id
            if entry['audit_status'] == 'not_started': entry['audit_status'] = 'recorded'
        except Exception as exc:
            db.warn_audit('finalize_run', exc)
            entry.update(audit_status='unavailable', status='degraded' if status == 'ok' else status,
                         error=(error+'; audit_finalization_unavailable').strip('; '))
        finally:
            db.clear_active_run()
    try:
        registry = load_registry()
        registry.setdefault('runs', []).insert(0, entry)
        registry['runs'] = registry['runs'][:100]
        registry['last_run'] = entry
        _atomic_write(REGISTRY_PATH, registry)
    except Exception as exc:
        log.warning('Local run summary unavailable (%s)', type(exc).__name__)
        entry['local_registry_status'] = 'unavailable'
        if entry['status'] == 'ok': entry['status'] = 'degraded'
    return entry


def write_bundle(deals, scraped_counties, status='ok', error=''):
    # Replace with a fresh DB snapshot. Merging a historical file would retain
    # deleted/revoked deals, and APN-only keys collide across counties.
    unique = {}
    for deal in deals:
        if (not isinstance(deal, dict) or deal.get('verification_status') != 'verified'
                or not deal.get('verified_at') or not deal.get('county_id') or not deal.get('apn')):
            continue
        expiry=sale_date(deal.get('verification_expires_at'))
        if not expiry or expiry<=datetime.now(timezone.utc): continue
        clean = {field:deal.get(field) for field in (*PUBLIC_DEAL_FIELDS,*PUBLIC_PROPERTY_FIELDS)}
        clean['comps'] = [{field:comp.get(field) for field in PUBLIC_COMP_FIELDS} for comp in deal.get('comps') or [] if isinstance(comp,dict)]
        unique[(deal['county_id'], deal['apn'])] = clean
    bundle = {'generated_at': datetime.now(timezone.utc).isoformat(), 'count': len(unique),
              'deals': list(unique.values()), 'error': error,
              'meta': {'scraped_counties': sorted(set(scraped_counties)), 'status': status,
                       'source': 'verified_database_snapshot'}}
    _atomic_write(BUNDLE_PATH, bundle)
    return BUNDLE_PATH


def load_bundle():
    return _read(BUNDLE_PATH, None)
