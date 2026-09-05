import importlib


def test_deal_provenance_persists(tmp_path, monkeypatch):
    import database

    db_path = tmp_path / "dealscan.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(database, "get_db_path", lambda: str(db_path))
    importlib.reload(database)
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(database, "get_db_path", lambda: str(db_path))

    database.init_db()
    property_id = database.save_property(
        {
            "apn": "TEST-123",
            "county_id": "test_county",
            "address": "123 Test Rd",
            "lot_size_acres": 1.5,
        }
    )
    deal_id = database.save_deal(
        {
            "property_id": property_id,
            "deal_score": 82,
            "asking_price": 25000,
            "source": "county_arcgis",
            "source_url": "https://example.test/parcel",
            "source_vendor": "Test County",
            "source_quality": "strong",
            "verification_status": "verified",
            "data_freshness": "2026-09-01",
            "valuation_basis": "market_value",
            "valuation_confidence": 0.75,
        }
    )

    rows = database.get_top_deals(limit=10, min_score=0, county_id="test_county")
    assert rows == []  # Caller-provided verification cannot bypass evidence review.
    rows = [database.get_backend().get_deal_for_verification(deal_id)]
    assert rows[0]["id"] == deal_id
    assert rows[0]["source_url"] == "https://example.test/parcel"
    assert rows[0]["source_vendor"] == "Test County"
    assert rows[0]["source_quality"] == "strong"
    assert rows[0]["verification_status"] == "pending_review"
    assert rows[0]["data_freshness"] == "2026-09-01"
    assert rows[0]["valuation_basis"] == "market_value"
    assert rows[0]["valuation_confidence"] == 0.75
