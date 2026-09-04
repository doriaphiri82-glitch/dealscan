"""
DealScan AI - Deal Scoring Algorithm
Scores each deal 1-100 based on multiple weighted factors.
"""
from typing import List, Dict
from config.settings import SCORING_WEIGHTS, MIN_PROFIT_ESTIMATE


def calculate_deal_score(deal_data: Dict) -> int:
    """Calculate a deal score from 1-100."""
    scores = {}
    asking = deal_data.get('asking_price', 1)
    profit_mid = (deal_data.get('estimated_profit_low', 0) + deal_data.get('estimated_profit_high', 0)) / 2
    if asking > 0:
        ratio = profit_mid / asking
        if ratio >= 5: scores['profit_ratio'] = 100
        elif ratio >= 3: scores['profit_ratio'] = 90
        elif ratio >= 2: scores['profit_ratio'] = 70
        elif ratio >= 1: scores['profit_ratio'] = 50
        elif ratio >= 0.5: scores['profit_ratio'] = 30
        else: scores['profit_ratio'] = 10
    else:
        scores['profit_ratio'] = 0
    signals = deal_data.get('motivation_signals', [])
    signal_count = len(signals) if isinstance(signals, list) else 0
    high_value = {'tax_delinquent', 'probate', 'inherited'}
    high_count = sum(1 for s in signals if s in high_value) if isinstance(signals, list) else 0
    scores['motivation_signals'] = min(100, (signal_count * 20) + (high_count * 15))
    velocity = deal_data.get('market_velocity')
    try:
        scores['market_velocity'] = max(0, min(100, int(float(velocity) * 100))) if velocity is not None else 50
    except (TypeError, ValueError):
        scores['market_velocity'] = 50
    comp_map = {'low': 90, 'medium': 60, 'high': 30}
    scores['competition'] = comp_map.get(deal_data.get('competition_level'), 50)
    acc = 50
    if deal_data.get('has_road_access') is True: acc += 20
    if deal_data.get('utilities_nearby') is True: acc += 15
    if deal_data.get('is_buildable') is True: acc += 15
    scores['accessibility'] = min(100, acc)
    total = sum(scores.get(f, 0) * w for f, w in SCORING_WEIGHTS.items())
    confidence = deal_data.get('valuation_confidence', 1.0)
    try:
        confidence = max(0.5, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.5
    total *= confidence
    return max(1, min(100, int(total)))


def calculate_profit_estimate(comps: List[Dict], lot_size_acres: float, asking_price: float,
                               assessed_value: float = 0, market_value: float = 0) -> Dict:
    """Estimate ARV/profit and record the strength of the valuation evidence."""
    empty = {'estimated_arv_low': 0, 'estimated_arv_high': 0, 'estimated_costs': 0,
             'estimated_profit_low': 0, 'estimated_profit_high': 0,
             'valuation_basis': 'unavailable', 'valuation_confidence': 0.5}
    if not comps:
        source_value = market_value if market_value and market_value > 0 else assessed_value
        if source_value and source_value > 0:
            arv_low = source_value * 0.85
            arv_high = source_value * 1.05
            estimated_costs = arv_low * 0.12
            return {
                'estimated_arv_low': round(arv_low), 'estimated_arv_high': round(arv_high),
                'estimated_costs': round(estimated_costs),
                'estimated_profit_low': round(max(0, arv_low - asking_price - estimated_costs)),
                'estimated_profit_high': round(max(0, arv_high - asking_price - estimated_costs)),
                'valuation_basis': 'market_value' if market_value and market_value > 0 else 'assessed_value',
                'valuation_confidence': 0.75 if market_value and market_value > 0 else 0.65,
            }
        return empty
    prices_per_acre = []
    for comp in comps:
        try:
            acres = float(comp.get('lot_size_acres', 0) or 0)
            sale_price = float(comp.get('sale_price', 0) or 0)
            if acres > 0 and sale_price > 0: prices_per_acre.append(sale_price / acres)
        except (TypeError, ValueError):
            continue
    if not prices_per_acre: return empty
    prices_per_acre.sort()
    median_ppa = prices_per_acre[len(prices_per_acre) // 2]
    arv_low = median_ppa * lot_size_acres * 0.80
    arv_high = median_ppa * lot_size_acres
    estimated_costs = arv_low * 0.08
    return {
        'estimated_arv_low': round(arv_low), 'estimated_arv_high': round(arv_high),
        'estimated_costs': round(estimated_costs),
        'estimated_profit_low': round(max(0, arv_low - asking_price - estimated_costs)),
        'estimated_profit_high': round(max(0, arv_high - asking_price - estimated_costs)),
        'valuation_basis': 'comparable_sales',
        'valuation_confidence': min(1.0, 0.75 + len(prices_per_acre) * 0.05),
    }


def calculate_recommended_offer(asking_price: float, profit_low: float, profit_high: float) -> Dict:
    """Calculate recommended offer range (60-80% of asking)."""
    if asking_price <= 0: return {'recommended_offer_low': 0, 'recommended_offer_high': 0}
    offer_low = asking_price * 0.60
    offer_high = min(asking_price * 0.80, (profit_low + profit_high) / 2 + asking_price - 2000)
    offer_low = min(offer_low, offer_high * 0.85)
    return {'recommended_offer_low': round(max(0, offer_low)), 'recommended_offer_high': round(max(0, offer_high))}


def detect_motivation_signals(property_data: Dict) -> List[str]:
    """Detect motivated seller signals from property data."""
    signals = []
    if property_data.get('tax_delinquent_years', 0) >= 2: signals.append('tax_delinquent')
    owner_state = property_data.get('owner_state', '')
    county_state = property_data.get('county_state', '')
    if owner_state and county_state and owner_state != county_state: signals.append('absentee_owner')
    year_acq = property_data.get('year_acquired', 2026)
    if year_acq and (2026 - year_acq) >= 10: signals.append('long_ownership')
    if not property_data.get('has_improvements', False): signals.append('no_improvements')
    land_use = str(property_data.get('land_use') or '').lower()
    if 'vacant' in land_use or 'unimproved' in land_use: signals.append('vacant_land')
    owner_name = str(property_data.get('owner_name') or '').lower()
    if any(t in owner_name for t in ['estate', 'trust', 'heirs', 'executor']): signals.append('probate')
    return signals


def score_and_enrich_deal(property_data: Dict, comps: List[Dict], county_config: Dict) -> Dict:
    """Full pipeline: detect signals, calculate profit, score the deal."""
    signals = detect_motivation_signals(property_data)
    raw_market = property_data.get('market_value')
    raw_assessed = property_data.get('assessed_value')
    try: market_value = float(raw_market or 0)
    except (TypeError, ValueError): market_value = 0.0
    try: assessed_value = float(raw_assessed or 0)
    except (TypeError, ValueError): assessed_value = 0.0
    value_is_official = market_value > 0 or assessed_value > 0
    asking_price = property_data.get('asking_price')
    asking_price_basis = 'source' if asking_price is not None else 'screening_assumption'
    if asking_price is None:
        asking_price = market_value * 0.6 if market_value > 0 else 0
    else:
        try: asking_price = float(asking_price)
        except (TypeError, ValueError): asking_price = 0.0
        if asking_price <= 0:
            return None
    if asking_price <= 0: return None
    lot_size = property_data.get('lot_size_acres', 0) or 0
    try: lot_size = float(lot_size)
    except (TypeError, ValueError): lot_size = 0.0
    profit_data = calculate_profit_estimate(comps, lot_size, asking_price, assessed_value=assessed_value, market_value=market_value)
    if profit_data['estimated_profit_low'] < MIN_PROFIT_ESTIMATE: return None
    offer_data = calculate_recommended_offer(asking_price, profit_data['estimated_profit_low'], profit_data['estimated_profit_high'])
    comp_count = len(comps)
    competition = 'low' if 0 < comp_count <= 2 else 'medium' if comp_count <= 5 else 'high'
    valuation_confidence = profit_data.get('valuation_confidence', 0.5)
    if not value_is_official and not comps: valuation_confidence = min(valuation_confidence, 0.5)
    deal_data = {
        'asking_price': asking_price, 'asking_price_basis': asking_price_basis,
        'motivation_signals': signals, 'motivation_score': len(signals) / 5.0,
        'market_velocity': county_config.get('market_velocity'), 'competition_level': competition,
        'has_road_access': property_data.get('has_road_access'), 'utilities_nearby': property_data.get('utilities_nearby'),
        'is_buildable': property_data.get('is_buildable'), 'valuation_confidence': valuation_confidence,
        **profit_data, **offer_data,
    }
    deal_data['deal_score'] = calculate_deal_score(deal_data)
    return deal_data
