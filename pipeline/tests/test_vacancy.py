from scrapers.arcgis import is_vacant_residential


def test_unknown_improvement_status_is_not_automatically_vacant():
    assert not is_vacant_residential(
        {"apn": "A1", "lot_size_acres": 1}, "unknown_county"
    )


def test_explicit_vacant_land_use_is_candidate():
    assert is_vacant_residential(
        {"apn": "A1", "land_use": "Vacant Residential", "has_improvements": None},
        "unknown_county",
    )


def test_explicit_no_improvements_with_residential_zoning_is_candidate():
    assert is_vacant_residential(
        {"apn": "A1", "has_improvements": False, "zoning": "R-1"},
        "unknown_county",
    )


def test_improved_parcel_is_not_vacant_without_vacant_land_use():
    assert not is_vacant_residential(
        {"apn": "A1", "has_improvements": True, "land_use": "Residential"},
        "unknown_county",
    )
