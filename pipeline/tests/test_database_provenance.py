import database


def test_deal_provenance_fields_persist(tmp_path, monkeypatch):
    db_path = tmp_path / "dealscan.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))

    database.init_db()
    property_id = database.save_property(
        {
            "apn": "TEST-APN-1",
            "county_id": "test_county",
            "address": "1 Test Road",
            "lot_size_acres": 1.5,
            "has_improvements": False,
        }
    )
    deal_id = database.save_deal(
        {
            "property_id": property_id,
            "deal_score": 82,
            "asking_price": 40000,
            "estimated_arv_low": 70000,
            "estimated_arv_high": 85000,
            "estimated_profit_low": 15000,
            "estimated_profit_high": 25000,
            "recommended_offer_low": 30000,
            "recommended_offer_high": 35000,
            "source": "arcgis",
            "source_url": "https://example.com/FeatureServer/0",
            "source_vendor": "esri",
            "source_quality": "strong",
            "verification_status": "verified",
            "data_freshness": "2026-09-04T00:00:00+00:00",
            "valuation_basis": "market_value",
            "valuation_confidence": 0.75,
        }
    )

    rows = database.get_top_deals(limit=5, min_score=0, county_id="test_county")
    assert deal_id > 0
    assert rows == []
    row = database.get_backend().get_deal_for_verification(deal_id)
    assert row["source_url"].endswith("FeatureServer/0")
    assert row["source_vendor"] == "esri"
    assert row["source_quality"] == "strong"
    assert row["verification_status"] == "pending_review"
    assert row["valuation_basis"] == "market_value"
    assert row["valuation_confidence"] == 0.75
