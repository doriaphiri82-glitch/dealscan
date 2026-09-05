"""Conservative, reproducible land screening. Missing evidence never becomes money."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from statistics import median
from typing import Any, Optional
from urllib.parse import urlsplit

from config.settings import MIN_PROFIT_ESTIMATE, SCORING_WEIGHTS
from normalization import boolean, number, sale_date
from validation.vacancy import vacancy_decision

MIN_COMPARABLES = 3
MAX_COMP_AGE_DAYS = 3 * 365
MAX_COMP_DISTANCE_MILES = 10
MODEL_VERSION = 'vacant_land_comps_v1'


def _url(value: Any) -> bool:
    try:
        parsed = urlsplit(str(value or ''))
        return parsed.scheme in {'https', 'http'} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def _number(value: Any) -> Optional[float]:
    return number(value)


def _sale_year(value: Any) -> Optional[int]:
    parsed = sale_date(value)
    return parsed.year if parsed else None


def _distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 3958.7613 * asin(min(1.0, sqrt(a)))


def valid_comparables(comps: list[dict], lot_size_acres: float) -> list[dict]:
    """Only recent, identified, qualified vacant-land sales can influence value."""
    now = datetime.now(timezone.utc)
    valid, seen = [], set()
    for comp in comps or []:
        price, acres, distance = (number(comp.get(key)) for key in ('sale_price', 'lot_size_acres', 'distance_miles'))
        sold = sale_date(comp.get('sale_date'))
        source_id = comp.get('source_record_id') or comp.get('source_apn')
        identity = (comp.get('source_url'), source_id)
        if not _url(comp.get('source_url')) or not source_id or identity in seen:
            continue
        if boolean(comp.get('sale_qualified')) is not True or boolean(comp.get('vacant_at_sale')) is not True:
            continue
        if price is None or price <= 0 or acres is None or acres <= 0 or distance is None or not 0 <= distance <= MAX_COMP_DISTANCE_MILES:
            continue
        if sold is None or not now - timedelta(days=MAX_COMP_AGE_DAYS) <= sold <= now:
            continue
        if not lot_size_acres * 0.25 <= acres <= lot_size_acres * 4:
            continue
        seen.add(identity)
        valid.append({**comp, 'sale_price': price, 'lot_size_acres': acres,
                      'sale_date': sold.isoformat(), 'distance_miles': distance,
                      'price_per_acre': price / acres, 'source_record_id': str(source_id)})
    return valid


def _source_comparables(property_data: dict) -> list[dict]:
    pool = property_data.get('_source_comp_pool')
    if not isinstance(pool, list):
        return []
    lat, lon, acres = (number(property_data.get(key)) for key in ('latitude', 'longitude', 'lot_size_acres'))
    if lat is None or lon is None or acres is None or acres <= 0 or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return []
    candidates = []
    for row in pool:
        if row.get('county_id') != property_data.get('county_id') or row.get('apn') == property_data.get('apn'):
            continue
        row_lat, row_lon = number(row.get('latitude')), number(row.get('longitude'))
        if row_lat is None or row_lon is None or not (-90 <= row_lat <= 90 and -180 <= row_lon <= 180):
            continue
        if not vacancy_decision(row, row.get('county_id', ''))[0]:
            continue
        candidates.append({
            'address': row.get('address'), 'sale_price': row.get('last_sale_price'),
            'sale_date': row.get('last_sale_date'), 'lot_size_acres': row.get('lot_size_acres'),
            'distance_miles': _distance_miles(lat, lon, row_lat, row_lon),
            'source': 'county_parcel_last_sale', 'source_url': row.get('source_url'),
            'source_record_id': row.get('_source_record_id') or row.get('apn'),
            'source_apn': row.get('apn'), 'county_id': row.get('county_id'),
            'sale_qualified': row.get('sale_qualified'), 'vacant_at_sale': row.get('vacant_at_sale'),
        })
    valid = valid_comparables(candidates, acres)
    return sorted(valid, key=lambda row: row['distance_miles'])[:8]


def calculate_profit_estimate(comps: list[dict], lot_size_acres: float, asking_price: float,
                              assessed_value: float = 0, market_value: float = 0,
                              *, estimated_costs: Optional[float] = None) -> dict:
    """Median real sale $/acre × area; low case has a documented 20% discount.

    Assessed/market values are intentionally NOT resale evidence. Profit needs
    an explicit complete cost estimate and a real acquisition/asking price.
    Losses remain negative instead of being clipped to zero.
    """
    empty = {key: None for key in ('estimated_arv_low', 'estimated_arv_high', 'estimated_costs', 'estimated_profit_low', 'estimated_profit_high')}
    empty.update(valuation_basis='unavailable', valuation_confidence=0.0)
    acres, asking, costs = number(lot_size_acres), number(asking_price), number(estimated_costs)
    if acres is None or acres <= 0:
        return empty
    valid = valid_comparables(comps, acres)
    if len(valid) < MIN_COMPARABLES:
        return empty
    high = round(median(comp['price_per_acre'] for comp in valid) * acres, 2)
    low = round(high * 0.8, 2)
    result = {**empty, 'estimated_arv_low': low, 'estimated_arv_high': high,
              'valuation_basis': 'comparable_sales', 'valuation_confidence': min(0.9, 0.6 + len(valid) * 0.05)}
    if asking is None or asking <= 0 or costs is None or costs < 0:
        return result
    result.update(estimated_costs=costs, estimated_profit_low=round(low - asking - costs, 2),
                  estimated_profit_high=round(high - asking - costs, 2))
    return result


def calculate_recommended_offer(asking_price: float, profit_low: float, profit_high: float) -> dict:
    """Screening proposal, not a seller quote: 60–80% of sourced asking price."""
    asking = number(asking_price)
    if asking is None or asking <= 0 or number(profit_low) is None or number(profit_high) is None:
        return {'recommended_offer_low': None, 'recommended_offer_high': None}
    return {'recommended_offer_low': round(asking * .6, 2), 'recommended_offer_high': round(asking * .8, 2)}


def detect_motivation_signals(property_data: dict) -> list[str]:
    signals = []
    delinquent = number(property_data.get('tax_delinquent_years'))
    if delinquent is not None and delinquent >= 2:
        signals.append('tax_delinquent')
    # Without source-normalized state codes, do not compare 'AZ' to 'Arizona'.
    owner = str(property_data.get('owner_state') or '').strip().upper()
    county = str(property_data.get('county_state') or '').strip().upper()
    if len(owner) == len(county) == 2 and owner != county:
        signals.append('absentee_owner')
    acquired = number(property_data.get('year_acquired'))
    year = datetime.now(timezone.utc).year
    if acquired is not None and 1800 <= acquired <= year - 10:
        signals.append('long_ownership')
    if boolean(property_data.get('has_improvements')) is False:
        signals.append('no_improvements')
    if vacancy_decision(property_data, property_data.get('county_id', ''))[0]:
        signals.append('vacant_land')
    # An owner named 'Trust' or 'Estate' is not evidence of probate/motivation.
    return signals


def calculate_deal_score(deal_data: dict) -> int:
    asking = number(deal_data.get('asking_price'))
    low, high = number(deal_data.get('estimated_profit_low')), number(deal_data.get('estimated_profit_high'))
    ratio = (low + high) / (2 * asking) if asking and low is not None and high is not None else 0
    profit_score = next((score for threshold, score in [(5,100),(3,90),(2,70),(1,50),(.5,30)] if ratio >= threshold), 0)
    signals = deal_data.get('motivation_signals') or []
    scores = {'profit_ratio': profit_score, 'motivation_signals': min(100, len(set(signals)) * 20),
              'market_velocity': 0, 'competition': 0,
              'accessibility': sum(1 for key in ('has_road_access', 'utilities_nearby', 'is_buildable') if deal_data.get(key) is True) * (100 / 3)}
    confidence = number(deal_data.get('valuation_confidence')) or 0
    return max(0, min(100, int(sum(scores.get(key, 0) * weight for key, weight in SCORING_WEIGHTS.items()) * confidence)))


def qualification_reason(property_data: dict, comps: list[dict]) -> str:
    asking = number(property_data.get('asking_price'))
    if asking is None or asking <= 0:
        return 'missing_source_asking_price'
    sources = property_data.get('_field_sources') or {}
    if not sources.get('asking_price') or not _url(property_data.get('asking_price_source_url') or property_data.get('source_url')):
        return 'untraceable_asking_price'
    if boolean(property_data.get('costs_complete')) is not True or not _url(property_data.get('costs_source_url')) or number(property_data.get('estimated_costs')) is None:
        return 'missing_complete_cost_evidence'
    acres = number(property_data.get('lot_size_acres')) or 0
    if acres <= 0 or len(valid_comparables(comps, acres)) < MIN_COMPARABLES:
        return 'insufficient_verified_comparables'
    return ''


def score_and_enrich_deal(property_data: dict, comps: list[dict], county_config: dict) -> Optional[dict]:
    if not vacancy_decision(property_data, property_data.get('county_id', ''), county_config)[0]:
        return None
    # Do not scan an entire county for comps when basic financial inputs are absent.
    initial_reason = qualification_reason(property_data, [])
    if initial_reason and initial_reason != 'insufficient_verified_comparables':
        return None
    comps = comps or _source_comparables(property_data)
    if qualification_reason(property_data, comps):
        return None
    asking, acres, costs = (number(property_data.get(key)) for key in ('asking_price', 'lot_size_acres', 'estimated_costs'))
    valid = valid_comparables(comps, acres)
    profit = calculate_profit_estimate(valid, acres, asking, estimated_costs=costs)
    if profit['estimated_profit_low'] is None or profit['estimated_profit_low'] < MIN_PROFIT_ESTIMATE:
        return None
    evidence = {
        'model_version': MODEL_VERSION, 'asking_price_basis': 'source',
        'asking_price': asking, 'asking_price_field': property_data['_field_sources']['asking_price'],
        'asking_price_source_url': property_data.get('asking_price_source_url') or property_data['source_url'],
        'costs_complete': True, 'estimated_costs': costs, 'costs_source_url': property_data['costs_source_url'],
        'lot_size_acres': acres, 'low_value_factor': .8,
        'arv_formula': 'median(qualified sale_price / sale_acres) * subject_acres; low = high * 0.8',
        'profit_formula': 'ARV - sourced asking price - sourced complete costs',
        'offer_formula': 'sourced asking price * [0.6, 0.8]; proposal, not seller quote',
        'comparable_count': len(valid),
    }
    signals = detect_motivation_signals(property_data)
    deal = {**profit, **calculate_recommended_offer(asking, profit['estimated_profit_low'], profit['estimated_profit_high']),
            'asking_price': asking, 'asking_price_basis': 'source', 'financial_evidence': evidence,
            'motivation_signals': signals, 'motivation_score': min(1, len(signals) / 5),
            'market_velocity': None, 'competition_level': None, 'comps': valid,
            'verification_status': 'pending_review', 'status': 'discovered'}
    deal['deal_score'] = calculate_deal_score(deal)
    return deal
