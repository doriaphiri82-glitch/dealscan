"""Financial fixtures are isolated unit inputs, never seed/publication data."""
from datetime import datetime, timedelta, timezone
import pytest
from scoring.deal_scorer import (
    calculate_deal_score, calculate_profit_estimate, calculate_recommended_offer,
    detect_motivation_signals, score_and_enrich_deal, valid_comparables,
)


def comps():
    sold = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    return [{'sale_price': price, 'lot_size_acres': 1, 'sale_date': sold, 'distance_miles': 1,
             'source_url': 'https://county.example/sales', 'source_record_id': str(i),
             'sale_qualified': True, 'vacant_at_sale': True}
            for i, price in enumerate([100000, 110000, 120000])]


def property_input():
    return {'apn': 'fixture', 'county_id': 'fixture', 'lot_size_acres': 1, 'land_use': 'Vacant land',
            'asking_price': 40000, 'estimated_costs': 10000, 'costs_complete': True,
            'costs_source_url': 'https://county.example/fixture-costs',
            'source_url': 'https://county.example/fixture-listing', '_field_sources': {'asking_price': 'LIST_PRICE'}}


def test_official_assessment_is_not_invented_resale_value():
    result = calculate_profit_estimate([], 1, 60000, market_value=100000, assessed_value=100000)
    assert result['valuation_basis'] == 'unavailable'
    assert result['estimated_arv_low'] is None


def test_recommended_offer_is_bounded_by_asking_price_and_profit():
    result = calculate_recommended_offer(100000, 20000, 40000)
    assert 0 <= result['recommended_offer_low'] <= result['recommended_offer_high'] <= 100000


def test_source_market_value_cannot_create_an_asking_price():
    result = score_and_enrich_deal({'market_value': 1000000, 'lot_size_acres': 1, 'land_use': 'Vacant land'}, comps(), {})
    assert result is None


def test_score_does_not_invent_county_market_value_when_source_value_is_missing():
    assert score_and_enrich_deal({'county_id': 'cochise_az', 'lot_size_acres': 10, 'has_improvements': False}, [], {}) is None


def test_profit_estimate_reports_missing_not_zero_without_evidence():
    result = calculate_profit_estimate([], 10, 0)
    assert result['valuation_basis'] == 'unavailable'
    assert result['estimated_profit_low'] is None and result['estimated_profit_high'] is None


def test_asking_price_alone_never_creates_synthetic_arv():
    result = calculate_profit_estimate([], 5, 5000)
    assert result['estimated_arv_low'] is None and result['estimated_profit_low'] is None


def test_missing_costs_prevent_profit_even_when_real_comps_exist():
    result = calculate_profit_estimate(comps(), 1, 40000)
    assert result['estimated_arv_high'] == 110000
    assert result['estimated_profit_low'] is None
    data = property_input(); data.pop('costs_complete')
    assert score_and_enrich_deal(data, comps(), {}) is None


def test_source_backed_calculations_are_reproducible_and_pending_review():
    result = score_and_enrich_deal(property_input(), comps(), {'market_velocity': .99})
    assert result is not None
    assert result['estimated_arv_high'] == 110000
    assert result['estimated_arv_low'] == 88000
    assert result['estimated_profit_low'] == 38000
    assert result['asking_price_basis'] == 'source'
    assert result['financial_evidence']['model_version'] == 'vacant_land_comps_v1'
    assert result['verification_status'] == 'pending_review'
    assert result['market_velocity'] is None and result['competition_level'] is None


def test_losses_are_not_silently_clipped_to_zero():
    result = calculate_profit_estimate(comps(), 1, 150000, estimated_costs=10000)
    assert result['estimated_profit_low'] == -72000
    data = property_input(); data['asking_price'] = 150000
    assert score_and_enrich_deal(data, comps(), {}) is None


@pytest.mark.parametrize('asking', [0, -1, float('inf'), float('nan'), None, 'bad', True])
def test_invalid_source_asking_price_cannot_qualify(asking):
    assert score_and_enrich_deal({**property_input(), 'asking_price': asking}, comps(), {}) is None


def test_untraceable_and_duplicate_sales_are_not_comparables():
    rows = comps()
    assert len(valid_comparables([rows[0], rows[0]], 1)) == 1
    for key in ('source_url', 'source_record_id', 'sale_date', 'vacant_at_sale', 'sale_qualified'):
        invalid = [{k: v for k, v in row.items() if k != key} for row in rows]
        assert valid_comparables(invalid, 1) == []


def test_future_far_away_and_incompatible_sales_are_rejected():
    rows = comps()
    future = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    for changes in ({'sale_date': future}, {'distance_miles': 11}, {'lot_size_acres': 100}, {'sale_price': float('inf')}):
        assert valid_comparables([{**row, **changes} for row in rows], 1) == []


def test_unknown_signals_do_not_increase_scores_or_invent_probate():
    assert detect_motivation_signals({'owner_name': 'Example Trust or Estate'}) == []
    assert calculate_deal_score({}) == 0
