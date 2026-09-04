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
        {"county_id": "test", "market_value": 1000, "lot_size_acres": 1, "has_improvements": False},
        [], {},
    )
    assert result is None


def test_score_does_not_invent_county_market_value_when_source_value_is_missing():
    result = score_and_enrich_deal(
        {"county_id": "cochise_az", "lot_size_acres": 10, "has_improvements": False}, [], {},
    )
    assert result is None


def test_profit_estimate_reports_unavailable_without_valuation_evidence():
    result = calculate_profit_estimate([], 10, 0)
    assert result["valuation_basis"] == "unavailable"
    assert result["estimated_profit_low"] == 0
    assert result["estimated_profit_high"] == 0


def test_asking_price_alone_never_creates_synthetic_arv():
    result = calculate_profit_estimate([], 5, 5000)
    assert result["valuation_basis"] == "unavailable"
    assert result["estimated_arv_low"] == 0
    assert result["estimated_profit_low"] == 0


def test_unknown_accessibility_and_competition_are_neutral():
    result = score_and_enrich_deal(
        {"county_id": "test", "market_value": 40000, "lot_size_acres": 1, "has_improvements": False},
        [], {},
    )
    assert result is not None
    assert result["competition_level"] == "medium"
    assert result["deal_score"] < 60


def test_invalid_source_asking_price_cannot_qualify():
    result = score_and_enrich_deal(
        {"county_id": "test", "market_value": 100000, "asking_price": 0, "lot_size_acres": 1},
        [], {},
    )
    assert result is None
