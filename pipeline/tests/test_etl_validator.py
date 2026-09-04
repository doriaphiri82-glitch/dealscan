from validation.etl_validator import validate_county_config


def _cfg():
    return {
        "county_id": "test_aa",
        "scraper_type": "arcgis",
        "arcgis_layer_url": "https://example.test/FeatureServer/0",
        "fields": {
            "apn": "APN",
            "address": "SITUS_ADDR",
            "lot_size_acres": "LAND_ACRES",
            "market_value": "FULL_CASH_VALUE",
            "owner_name": "OWNER_NAME",
        },
    }


def test_valid_config_and_sample():
    report = validate_county_config(
        "test_aa",
        _cfg(),
        source_fields=["APN", "SITUS_ADDR", "LAND_ACRES", "FULL_CASH_VALUE", "OWNER_NAME"],
        sample_records=[{"APN": "123", "SITUS_ADDR": "123 Main", "LAND_ACRES": 2.5, "FULL_CASH_VALUE": 10000, "OWNER_NAME": "Owner"}],
    )
    assert report["valid"] is True
    assert report["sample_invalid"] == 0


def test_case_insensitive_sample_fields_are_valid():
    cfg=_cfg()
    report=validate_county_config(
        "test_aa",
        cfg,
        source_fields=["APN", "SITUS_ADDR", "LAND_ACRES", "FULL_CASH_VALUE", "OWNER_NAME"],
        sample_records=[{"apn": "123", "situs_addr": "123 Main", "land_acres": 2.5, "full_cash_value": 10000, "owner_name": "Owner"}],
    )
    assert report["valid"] is True
    assert report["sample_invalid"] == 0


def test_missing_source_field_is_rejected():
    report = validate_county_config(
        "test_aa",
        _cfg(),
        source_fields=["APN", "SITUS_ADDR", "OWNER_NAME"],
    )
    assert report["valid"] is False
    assert any("LAND_ACRES" in error for error in report["errors"])


def test_missing_required_mapping_is_rejected():
    cfg = _cfg()
    del cfg["fields"]["owner_name"]
    report = validate_county_config("test_aa", cfg)
    assert report["valid"] is False
    assert "missing required field mappings: owner_name" in report["errors"]


def test_invalid_sample_numeric_is_rejected():
    report = validate_county_config(
        "test_aa",
        _cfg(),
        sample_records=[{"APN": "123", "SITUS_ADDR": "123 Main", "LAND_ACRES": "bad", "FULL_CASH_VALUE": "10,000", "OWNER_NAME": "Owner"}],
    )
    assert report["valid"] is False
    assert any("lot_size_acres not numeric" in error for error in report["errors"])
