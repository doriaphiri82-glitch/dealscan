"""Truthful source readiness and explicitly last-batch operational metrics.

County geography is not live parcel coverage. Successful ingestion timestamps
are never substituted for source freshness or publication evidence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from normalization import sale_date
from config.source_config import county_config
from validation.gates import authorization_error, validation_error, source_url


def count(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else 0


@dataclass
class CountyHealth:
    county_id: str
    status: str = 'not_implemented'
    coverage_tier: str = 'tier_0'
    source_stage: str = 'not_researched'
    source_reachable: bool = False
    live_validated: bool = False
    ingestion_ready: bool = False
    schema_changed: bool = False
    records_discovered: int = 0
    records_downloaded: int = 0
    records_parsed: int = 0
    records_normalized: int = 0
    records_rejected: int = 0
    rejection_reasons: dict[str,int] = field(default_factory=dict)
    records_stored: int = 0
    records_scored: int = 0
    records_qualified: int = 0
    records_published: int = 0
    error_rate: float = 0.0
    last_successful_run: str | None = None
    data_freshness: str | None = None
    scraper_version: str = '0.1.0'


def coverage_tier_name(tier: str) -> str:
    return {'tier_0':'Not Researched','tier_1':'Source Discovered','tier_2':'Live Validated',
            'tier_3':'Authorized for Ingestion','tier_4':'Source Properties Stored',
            'tier_5':'Private Financial Candidates','tier_6':'Verified Opportunities Published'}.get(tier,tier)


def health_status_symbol(status: str) -> str:
    return {'active':'🟢','ok':'🟢','completed':'🟢','degraded':'🟡','partial':'🟡',
            'failed':'🔴','error':'🔴','not_implemented':'⚪','skipped':'⚪'}.get(status,'⚪')


def _tier_from_status(status: str, counts: dict) -> str:
    if count(counts.get('published')): return 'tier_6'
    if count(counts.get('qualified')): return 'tier_5'
    if count(counts.get('stored',counts.get('saved'))): return 'tier_4'
    # A successful HTTP fetch, an error, or a skipped run is not validation.
    return 'tier_0'


def build_county_health(run_entry: dict[str,Any]) -> CountyHealth:
    counts = run_entry.get('counts') or {}
    status = run_entry.get('status','error')
    return CountyHealth(county_id=run_entry.get('county_id','unknown'),status=status,
        coverage_tier=_tier_from_status(status,counts),
        records_discovered=count(counts.get('discovered',counts.get('found'))),
        records_downloaded=count(counts.get('downloaded')),
        records_parsed=count(counts.get('parsed')),records_normalized=count(counts.get('normalized')),
        records_rejected=count(counts.get('rejected')),rejection_reasons=counts.get('rejection_reasons') or {},
        records_stored=count(counts.get('stored',counts.get('saved'))),
        records_scored=count(counts.get('scored')),records_qualified=count(counts.get('qualified')),
        records_published=count(counts.get('published')),
        last_successful_run=run_entry.get('at') if status in {'ok','completed'} else None,
        data_freshness=run_entry.get('data_freshness'))


def _registry_health(county: dict[str,Any]) -> CountyHealth:
    cfg = county_config(county.get('county_id',''),county)
    current = not validation_error(county,cfg)
    ready = not authorization_error(county,cfg)
    unavailable = county.get('validation_status') in {'invalid','unreachable'}
    source = source_url(cfg)
    stage = ('unavailable' if unavailable else 'validating' if county.get('validation_status')=='validating'
        else 'ingestion_ready' if ready else 'live_validated' if current
        else 'validation_expired' if county.get('validation_status')=='valid'
        else 'discovered' if source else 'not_researched')
    stored = count(county.get('persisted_count',county.get('last_persisted_count')))
    qualified = count(county.get('qualified_count'))
    published = count(county.get('published_count',county.get('last_published_count')))
    status = county.get('last_run_status')
    if unavailable or status in {'error','failed'}: status='failed'
    elif status in {'partial','degraded'} or stored and not ready: status='degraded'
    elif ready and stored and status in {'ok','completed'}: status='active'
    elif status!='skipped': status='not_implemented'
    tier = ('tier_6' if published else 'tier_5' if qualified else 'tier_4' if stored
        else 'tier_3' if ready else 'tier_2' if current else 'tier_1' if source else 'tier_0')
    return CountyHealth(county_id=county.get('county_id','unknown'),status=status,coverage_tier=tier,
        source_stage=stage,source_reachable=current,live_validated=current,ingestion_ready=ready,
        records_discovered=count(county.get('record_count',county.get('last_record_count'))),
        records_stored=stored,records_qualified=qualified,records_published=published,
        last_successful_run=county.get('last_successful_run'),data_freshness=county.get('data_freshness'))


def build_national_dashboard(registry: dict[str,Any],recent_runs: list[dict[str,Any]]) -> dict[str,Any]:
    runs_by_county = {}
    for run in recent_runs:
        cid, at = run.get('county_id'), sale_date(run.get('at'))
        if cid and at and (cid not in runs_by_county or at>sale_date(runs_by_county[cid]['at'])):
            runs_by_county[cid]=run
    status_counts, tier_counts, rows = {}, {}, []
    for county in registry.get('counties',{}).values():
        run = runs_by_county.get(county.get('county_id'))
        last_at = sale_date(county.get('last_run_at'))
        # Local run metrics may recover a lost local registry update. They must
        # never resurrect data after an authoritative production registry reset.
        if run and registry.get('meta',{}).get('runtime_source')!='supabase' and (not last_at or sale_date(run['at'])>last_at):
            counts = run.get('counts') or {}
            county={**county,'last_run_status':run.get('status'),'last_run_at':run.get('at'),
                    'record_count':count(counts.get('discovered',counts.get('found'))),
                    'persisted_count':count(counts.get('stored',counts.get('saved'))),
                    'qualified_count':count(counts.get('qualified')),'published_count':count(counts.get('published'))}
            if run.get('status') in {'ok','completed'}: county['last_successful_run']=run.get('at')
        health = _registry_health(county)
        rejection_reasons = (run.get('counts') or {}).get('rejection_reasons',{}) if run else {}
        status_counts[health.status]=status_counts.get(health.status,0)+1
        tier_counts[health.coverage_tier]=tier_counts.get(health.coverage_tier,0)+1
        rows.append({'county_id':health.county_id,'county_name':county.get('county_name',health.county_id),
            'state':county.get('state'),'status':health.status,'source_stage':health.source_stage,
            'live_validated':health.live_validated,'ingestion_ready':health.ingestion_ready,
            'symbol':health_status_symbol(health.status),'tier':health.coverage_tier,'tier_name':coverage_tier_name(health.coverage_tier),
            'records':health.records_stored,'published':health.records_published,'qualified':health.records_qualified,
            'last_run':county.get('last_run_at') or health.last_successful_run,'last_successful_run':health.last_successful_run,'data_freshness':health.data_freshness,
            'validation_status':county.get('validation_status'),'verification_status':county.get('verification_status'),
            'registry_coverage_status':county.get('coverage_status'),'rejection_reasons':rejection_reasons})
    return {'total_counties':len(rows),'status_counts':status_counts,'tier_counts':tier_counts,'counties':rows,
        'coverage_summary':{'total':len(rows),'total_counties':len(rows),
            **{key:status_counts.get(key,0) for key in ('active','degraded','failed','not_implemented','skipped')},
            'live_validated':sum(row['live_validated'] for row in rows),'ingestion_ready':sum(row['ingestion_ready'] for row in rows)},
        'metric_scope':'last_batch_not_current_public_inventory',
        'note':'Configured county geography is not national live coverage; use the database-backed admin API for current inventory',
        'generated_at':datetime.now(timezone.utc).isoformat()}
