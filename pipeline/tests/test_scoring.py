from scoring.deal_scorer import calculate_profit_estimate, calculate_recommended_offer, score_and_enrich_deal


def test_official_market_value_is_used_as_valuation_basis():
    result = calculate_profit_estimate([], 1.0, 60000, market_value=100000)
    assert result["valuation_basis"] == "market_value"
    assert result["valuation_confidence"] == 0.75
    assert result["estimated_arv_low"] == 85000


def test_recommended_offer_is_bounded_by_asking_price_and_profit():
    result = calculate_recommended_offer(100000, 20000, 40000)
    assert 0 <= result["recommended_offer_low"] <= result["recommended_offer_high"] <= 100000


def test_score_returns_none_when_profit_threshold_is_not_met():
    result = score_and_enrich_deal(
        {
            "county_id": "test",
            "market_value": 10000,
            "lot_size_acres": 1,
            "has_improvements": False,
        },
        [],
        {},
    )
    assert result is None
