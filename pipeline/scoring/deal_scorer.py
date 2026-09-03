"""
DealScan AI - Deal Scoring Algorithm
Scores each deal 1-100 based on multiple weighted factors.
"""
from typing import List, Dict
from config.settings import SCORING_WEIGHTS, MIN_PROFIT_ESTIMATE


def calculate_deal_score(deal_data: Dict) -> int:
    """Calculate a deal score from 1-100."""
    scores = {}

    # 1. Profit Ratio Score (0-100)
    asking = deal_data.get('asking_price', 1)
    profit_mid = (deal_data.get('estimated_profit_low', 0) +
                  deal_data.get('estimated_profit_high', 0)) / 2
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

    # 2. Motivation Signals Score (0-100)
    signals = deal_data.get('motivation_signals', [])
    signal_count = len(signals) if isinstance(signals, list) else 0
    high_value = {'tax_delinquent', 'probate', 'inherited'}
    high_count = sum(1 for s in signals if s in high_value) if isinstance(signals, list) else 0
    scores['motivation_signals'] = min(100, (signal_count * 20) + (high_count * 15))

    # 3. Market Velocity Score (0-100)
    velocity = deal_data.get('market_velocity', 0.5)
    scores['market_velocity'] = int(velocity * 100)

    # 4. Competition Score (inverse: less competition = higher)
    comp_map = {'low': 90, 'medium': 60, 'high': 30}
    scores['competition'] = comp_map.get(deal_data.get('competition_level', 'medium'), 50)

    # 5. Accessibility Score
    acc = 50
    if deal_data.get('has_road_access'): acc += 20
    if deal_data.get('utilities_nearby'): acc += 15
    if deal_data.get('is_buildable'): acc += 15
    scores['accessibility'] = min(100, acc)

    # Weighted total
    total = sum(scores.get(f, 0) * w for f, w in SCORING_WEIGHTS.items())
    return max(1, min(100, int(total)))


def calculate_profit_estimate(comps: List[Dict], lot_size_acres: float,
                               asking_price: float) -> Dict:
    """Calculate profit estimate based on comparable sales."""
    empty = {'estimated_arv_low': 0, 'estimated_arv_high': 0,
             'estimated_costs': 0, 'estimated_profit_low': 0,
             'estimated_profit_high': 0}
    if not comps:
        return empty

    prices_per_acre = []
    for comp in comps:
        if comp.get('lot_size_acres', 0) > 0:
            prices_per_acre.append(comp['sale_price'] / comp['lot_size_acres'])
    if not prices_per_acre:
        return empty

    prices_per_acre.sort()
    median_ppa = prices_per_acre[len(prices_per_acre) // 2]

    arv_low = median_ppa * lot_size_acres * 0.80
    arv_high = median_ppa * lot_size_acres * 1.0
    estimated_costs = arv_low * 0.08
    profit_low = max(0, arv_low - asking_price - estimated_costs)
    profit_high = max(0, arv_high - asking_price - estimated_costs)

    return {
        'estimated_arv_low': round(arv_low),
        'estimated_arv_high': round(arv_high),
        'estimated_costs': round(estimated_costs),
        'estimated_profit_low': round(profit_low),
        'estimated_profit_high': round(profit_high),
    }


def calculate_recommended_offer(asking_price: float,
                                 profit_low: float, profit_high: float) -> Dict:
    """Calculate recommended offer range (60-80% of asking)."""
    if asking_price <= 0:
        return {'recommended_offer_low': 0, 'recommended_offer_high': 0}
    offer_low = asking_price * 0.60
    offer_high = asking_price * 0.80
    max_for_profit = (profit_low + profit_high) / 2 + asking_price - 2000
    offer_high = min(offer_high, max_for_profit)
    offer_low = min(offer_low, offer_high * 0.85)
    return {
        'recommended_offer_low': round(max(0, offer_low)),
        'recommended_offer_high': round(max(0, offer_high)),
    }


def detect_motivation_signals(property_data: Dict) -> List[str]:
    """Detect motivated seller signals from property data."""
    signals = []
    if property_data.get('tax_delinquent_years', 0) >= 2:
        signals.append('tax_delinquent')
    owner_state = property_data.get('owner_state', '')
    county_state = property_data.get('county_state', '')
    if owner_state and county_state and owner_state != county_state:
        signals.append('absentee_owner')
    year_acq = property_data.get('year_acquired', 2026)
    if year_acq and (2026 - year_acq) >= 10:
        signals.append('long_ownership')
    if not property_data.get('has_improvements', False):
        signals.append('no_improvements')
    land_use = str(property_data.get('land_use') or '').lower()
    if 'vacant' in land_use or 'unimproved' in land_use:
        signals.append('vacant_land')
    owner_name = str(property_data.get('owner_name') or '').lower()
    if any(t in owner_name for t in ['estate', 'trust', 'heirs', 'executor']):
        signals.append('probate')
    return signals


def score_and_enrich_deal(property_data: Dict, comps: List[Dict],
                           county_config: Dict) -> Dict:
    """Full pipeline: detect signals, calculate profit, score the deal."""
    signals = detect_motivation_signals(property_data)
    asking_price = property_data.get('asking_price',
                   property_data.get('assessed_value', 0))
    lot_size = property_data.get('lot_size_acres', 1)
    profit_data = calculate_profit_estimate(comps, lot_size, asking_price)

    if profit_data['estimated_profit_low'] < MIN_PROFIT_ESTIMATE:
        return None

    offer_data = calculate_recommended_offer(
        asking_price, profit_data['estimated_profit_low'],
        profit_data['estimated_profit_high'])

    comp_count = len(comps)
    competition = 'low' if comp_count <= 2 else 'medium' if comp_count <= 5 else 'high'

    deal_data = {
        'asking_price': asking_price,
        'motivation_signals': signals,
        'motivation_score': len(signals) / 5.0,
        'market_velocity': county_config.get('market_velocity', 0.5),
        'competition_level': competition,
        'has_road_access': True,
        'utilities_nearby': False,
        'is_buildable': 'residential' in property_data.get('zoning', '').lower(),
        **profit_data,
        **offer_data,
    }
    deal_data['deal_score'] = calculate_deal_score(deal_data)
    return deal_data
