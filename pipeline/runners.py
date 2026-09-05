"""Bounded county ingestion: authorized source -> private evidence -> review.

An ingestion run never self-verifies or manufactures an opportunity. Authentic
vacant candidates survive missing financial evidence as private held properties.
"""
from __future__ import annotations
from config.counties.registry import get_county, mark_county_run
from database import get_backend, get_top_deals, init_db, save_comps, save_deal, save_property, sync_county
from persistence import record_key
from runregistry import record_run, write_bundle
from scoring.deal_scorer import MODEL_VERSION, qualification_reason, score_and_enrich_deal, _source_comparables
from scrapers.adapter import BaseScraperAdapter
from scrapers.arcgis_adapter import ArcGISFeatureServerAdapter, ArcGISHubAdapter
from scrapers.counties import COUNTY_SCRAPERS
from scrapers.flatfile_adapter import FlatFileAdapter, CSVAdapter, ExcelAdapter
from validation.gates import authorization_error, source_fingerprint, source_url
from validation.vacancy import vacancy_decision

ADAPTER_MAP = {'arcgis': ArcGISFeatureServerAdapter, 'arcgis_hub': ArcGISHubAdapter,
               'flatfile': FlatFileAdapter, 'csv': CSVAdapter, 'excel': ExcelAdapter,
               'state_parcel': ArcGISFeatureServerAdapter}


def _adapter_for(cfg: dict) -> BaseScraperAdapter | None:
    kind = cfg.get('scraper_type') or cfg.get('data_mode', 'arcgis')
    cls = ADAPTER_MAP.get(kind)
    if not cls or (kind in {'arcgis','arcgis_hub','state_parcel'} and not cfg.get('arcgis_layer_url')):
        return None
    return cls()


def _county_config(county_id):
    from config.source_config import county_config
    return county_config(county_id)


def fetch_parcels(cfg, county_id, max_records=5000):
    adapter = _adapter_for(cfg)
    if not adapter: raise ValueError('Unsupported or incomplete source adapter')
    result, normalized = adapter.run({**cfg, 'county_id': county_id}, max_records=max_records)
    # Keep rejected raw rows and partial-source diagnostics available for audit,
    # even when none normalized. The runner decides the terminal outcome.
    return normalized, result


class RunMetrics:
    COUNTERS = ('discovered','downloaded','parsed','normalized','rejected','skipped','stored','scored','qualified','held','failed','published')

    def __init__(self, county_id):
        self.county_id = county_id
        for key in self.COUNTERS: setattr(self, key, 0)
        self.rejection_reasons = {}; self.hold_reasons = {}; self.errors = []
        self.field_coverage = {}; self.vacancy_rejection_reasons = {}; self.comparable_count = 0

    def to_counts(self): return {key: getattr(self, key) for key in self.COUNTERS}

    def record_rejection(self, reason):
        self.rejected += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1

    def record_vacancy_rejection(self, reason):
        self.record_rejection(reason)
        self.vacancy_rejection_reasons[reason] = self.vacancy_rejection_reasons.get(reason, 0) + 1

    def record_hold(self, reason):
        self.held += 1
        self.hold_reasons[reason] = self.hold_reasons.get(reason, 0) + 1


def _shape_for_bundle(row):
    fields = ('id','apn','address','county_id','lot_size_acres','asking_price','asking_price_basis','deal_score',
              'estimated_arv_low','estimated_arv_high','estimated_costs','estimated_profit_low','estimated_profit_high',
              'recommended_offer_low','recommended_offer_high','zoning','latitude','longitude','valuation_basis',
              'valuation_confidence','source','source_url','source_vendor','source_quality','verification_status',
              'verified_at','verification_expires_at','valuation_model','data_freshness','comps')
    return {key: row.get(key) for key in fields}


def _provenance(cfg, county_id):
    return {'source_url': source_url(cfg), 'source_vendor': cfg.get('source_vendor'),
            'source_quality': cfg.get('source_quality'), 'verification_status': 'pending_review',
            'data_freshness': cfg.get('source_last_modified') or cfg.get('data_freshness'),
            'valuation_model': MODEL_VERSION}


def _vacancy_rejection_reason(prop, county_id):
    accepted, reason = vacancy_decision(prop, county_id, _county_config(county_id))
    return '' if accepted else reason


def _field_coverage(props):
    fields = ('apn','lot_size_acres','market_value','assessed_value','asking_price','land_use','use_code',
              'has_improvements','improvement_value','latitude','longitude','last_sale_price','last_sale_date')
    return {field: {'populated': sum(p.get(field) not in (None,'',' ') for p in props), 'total': len(props)} for field in fields}


def _source_manifest(cfg, county):
    keys = ('county_id','arcgis_layer_url','data_url','parcel_source_url','fields','where','acreage_units',
            'vacancy_codebook_url','vacant_use_codes','authority_reviewed','authority_evidence_url',
            'authority_source_url','source_county_geoid','geoid','source_object_id_field')
    config = {key: cfg.get(key) for key in keys}
    config['defaults'] = {'county_state': (cfg.get('defaults') or {}).get('county_state')}
    authorization_keys = ('validation_status','last_validated_at','validated_source_fingerprint',
                          'validation_source_fields_checked','validation_pagination_checked','validation_sample_checked',
                          'ingestion_authorized','authorized_source_fingerprint')
    return {'source_config': config, 'source_authorization': {key: county.get(key) for key in authorization_keys},
            'source_fingerprint': source_fingerprint(cfg),
            'authorized_source_fingerprint': county.get('authorized_source_fingerprint'),
            'source_validated_at': county.get('last_validated_at')}


def run(county_id, mode='publish', max_records=5000, dry_run=False, offline=False):
    cfg = _county_config(county_id); county = get_county(county_id) or {}; metrics = RunMetrics(county_id)
    dry_run = dry_run or mode == 'dry_run'
    summary = {'county_id': county_id, 'counts': metrics.to_counts(), 'status': 'ok', 'error': '', 'dry_run': dry_run}
    if mode not in {'publish','etl-only','dry_run'}:
        return {**summary, 'status': 'error', 'error': 'Invalid run mode'}
    reason = ('County has no configured source' if not cfg else 'offline mode: source not queried' if offline
              else 'max_records must be between 1 and 5000' if not 1 <= max_records <= 5000
              else authorization_error(county, cfg))
    if reason:
        summary.update(status='skipped', error=reason)
        if not dry_run: record_run(county_id, 'skipped', summary['counts'], reason, audit=False)
        return summary

    db = get_backend(); run_id = None; manifest = _source_manifest(cfg, county)
    audit_failures_before = len(db.audit_failures)
    audit_available = not dry_run
    audit_rows = []; candidates = []; rejected_apns = []; vacant_count = 0

    def audit_warning(operation, exc):
        nonlocal audit_available
        db.warn_audit(operation, exc)
        audit_available = False

    def heartbeat():
        if audit_available and run_id:
            try: db.update_ingestion_run(run_id, county_id, 'running', metrics.to_counts(), metadata=manifest)
            except Exception as exc: audit_warning('heartbeat', exc)

    try:
        if not dry_run:
            init_db()
            sync_county(county)
            try:
                run_id = db.ensure_active_ingestion_run(county_id, source_url(cfg))
                heartbeat()
            except Exception as exc: audit_warning('start_run', exc)
        props, result = fetch_parcels(cfg, county_id, max_records=max_records)
        if result:
            for key in ('discovered','downloaded','parsed','normalized','rejected','skipped'):
                setattr(metrics, key, getattr(result, key))
            metrics.rejection_reasons.update(result.rejection_reasons)
            metrics.errors.extend(result.errors)
            audit_rows.extend(result.metadata.get('audit_records', []))
        else:
            metrics.discovered = metrics.downloaded = metrics.parsed = metrics.normalized = len(props)
        heartbeat()
        if not metrics.discovered:
            metrics.errors.append('source_returned_zero_records')
        if metrics.discovered and not props: metrics.errors.append('source_returned_no_usable_parcel_identities')
        metrics.field_coverage = _field_coverage(props)
        ambiguous = {row.get('normalized_payload',{}).get('apn') for row in audit_rows if row.get('hold_reason') == 'duplicate_county_apn'}
        comp_pool = [prop for prop in props if prop.get('apn') not in ambiguous]
        for index, original in enumerate(props):
            prop = {**original, 'county_id': county_id, 'source_url': source_url(cfg),
                    'source_fingerprint': manifest['source_fingerprint'], '_defer_audit': True}
            accepted, vacancy_reason = vacancy_decision(prop, county_id, cfg)
            if original.get('county_id') != county_id:
                accepted, vacancy_reason = False, 'county_identity_mismatch'
            prop.update(vacancy_status='qualified' if accepted else 'rejected',
                        vacancy_evidence={'reason': vacancy_reason, 'field_mapping': prop.get('_field_sources') or {}})
            item = {'source_record_id': prop.get('_source_record_id') or prop.get('apn'), 'source_url': source_url(cfg),
                    'raw_payload': prop.get('_raw_payload') or {}, 'normalized_payload': prop}
            audit_rows.append(item)
            if not accepted:
                metrics.record_vacancy_rejection(vacancy_reason)
                item.update(status='rejected', rejection_reason=vacancy_reason)
                if prop.get('apn'): rejected_apns.append(prop['apn'])
                continue
            vacant_count += 1
            if not dry_run:
                try:
                    item['property_id'] = save_property(prop)
                    metrics.stored += 1
                except Exception as exc:
                    metrics.failed += 1
                    metrics.errors.append(f'property_persistence_error: {type(exc).__name__}')
                    item.update(status='failed', hold_reason='property_persistence_error')
                    continue
            if prop.get('apn') in ambiguous:
                metrics.record_hold('duplicate_county_apn')
                item.update(status='held', hold_reason='duplicate_county_apn')
                rejected_apns.append(prop['apn'])
                continue
            metrics.scored += 1
            scoring = {**prop, '_source_comp_pool': comp_pool}
            try:
                deal = score_and_enrich_deal(scoring, [], cfg)
                hold = qualification_reason(scoring, [])
                if deal is None and hold == 'insufficient_verified_comparables':
                    hold = qualification_reason(scoring, _source_comparables(scoring)) or 'below_min_profit'
            except Exception as exc:
                deal, hold = None, 'score_error'
                metrics.errors.append(f'score_error: {type(exc).__name__}')
            if deal is None:
                metrics.record_hold(hold or 'financial_evidence_incomplete')
                item.update(status='held', hold_reason=hold or 'financial_evidence_incomplete')
                if prop.get('apn'): rejected_apns.append(prop['apn'])
            else:
                item['status'] = 'candidate'
                deal.update(_provenance(cfg, county_id))
                candidates.append((prop, deal, item))
            if index % 50 == 0: heartbeat()

        if not dry_run:
            # Source rejection also revokes a previously verified assessment.
            rejected_apns.extend(row.get('normalized_payload', {}).get('apn') for row in audit_rows if row.get('status') in {'rejected','skipped'})
            db.hold_deals_for_parcels(county_id, [apn for apn in rejected_apns if apn])
        audit_index = {}
        if audit_available and run_id:
            try:
                db.record_ingestion_records(run_id, county_id, audit_rows)
                if candidates:
                    audit_index = {row['record_key']: row for row in db.get_ingestion_records(run_id, include_payloads=False)}
            except Exception as exc: audit_warning('record_sources', exc)
        for prop, deal, item in candidates:
            if dry_run:
                metrics.qualified += 1
                metrics.comparable_count += len(deal.get('comps') or [])
                continue
            try:
                key = record_key(source_url(cfg), item['source_record_id'], item['raw_payload'])
                deal.update(property_id=item['property_id'], source='county_ingestion',
                            ingestion_record_id=(audit_index.get(key) or {}).get('id'))
                for comp in deal.get('comps') or []:
                    key = record_key(comp.get('source_url'), comp.get('source_record_id'), {})
                    comp['ingestion_record_id'] = (audit_index.get(key) or {}).get('id')
                deal_id = save_deal(deal)
                save_comps(deal_id, deal.get('comps') or [])
                item.update(deal_id=deal_id, status='candidate')
                metrics.qualified += 1
                metrics.comparable_count += len(deal.get('comps') or [])
            except Exception as exc:
                metrics.errors.append(f'deal_persistence_error: {type(exc).__name__}')
                metrics.record_hold('deal_persistence_error')
                item.update(status='held', hold_reason='deal_persistence_error')
            heartbeat()
        if audit_available and run_id and candidates:
            try: db.record_ingestion_records(run_id, county_id, audit_rows)
            except Exception as exc: audit_warning('link_candidates', exc)
        if metrics.errors: summary['status'] = 'degraded' if metrics.stored or dry_run else 'error'
        # No new deal is published here, even when financial screening succeeds.
        # Zero opportunities with real held/rejected records is an honest outcome.
        if mode == 'publish' and not dry_run:
            rows = [_shape_for_bundle(row) for row in get_top_deals(limit=100, min_score=0)]
            summary['available_verified'] = len(rows)
            summary['bundle_path'] = write_bundle(rows, [county_id], status=summary['status'], error='; '.join(metrics.errors[:3]))
    except Exception as exc:
        summary['status'] = 'degraded' if metrics.stored else 'error'
        metrics.errors.append(f'run_error: {type(exc).__name__}')

    if len(db.audit_failures) > audit_failures_before:
        metrics.errors.append('audit_unavailable: source provenance or run finalization requires reconciliation')
        if summary['status'] == 'ok': summary['status'] = 'degraded'
    summary.update(counts=metrics.to_counts(), error='; '.join(metrics.errors[:3]),
                   rejection_reasons=metrics.rejection_reasons, hold_reasons=metrics.hold_reasons,
                   diagnostics={'field_coverage': metrics.field_coverage, 'vacancy': {'accepted': vacant_count,
                                'rejection_reasons': metrics.vacancy_rejection_reasons}, 'comparables': metrics.comparable_count})
    if not dry_run:
        entry = record_run(county_id, summary['status'], summary['counts'], summary['error'], run_id=run_id,
                           source_url=source_url(cfg), metadata={**manifest, 'record_limit': max_records,
                                                              'audit_gap': not audit_available})
        summary.update(status=entry['status'], error=entry['error'], audit_run_id=entry.get('audit_run_id'), audit_status=entry['audit_status'])
        try:
            mark_county_run(county_id, record_count=metrics.discovered, qualified_count=metrics.qualified,
                            published_count=metrics.published, persisted_count=metrics.stored,
                            status=summary['status'], error=summary['error'])
            updated_county = get_county(county_id)
            if updated_county: sync_county(updated_county)
        except Exception as exc:
            summary['error'] += f'; county_summary_error: {type(exc).__name__}'
            if summary['status'] == 'ok': summary['status'] = 'degraded'
    return summary


class CountyRunner:
    def __init__(self, county_id): self.county_id = county_id
    def run(self, mode='publish', **kwargs): return run(self.county_id, mode=mode, **kwargs)


COUNTRY_RUNNERS = {cid: CountyRunner(cid) for cid in COUNTY_SCRAPERS}
