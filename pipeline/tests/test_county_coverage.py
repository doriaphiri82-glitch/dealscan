from config.counties.registry import get_county
from scrapers.arcgis import is_vacant_residential, map_attributes
from scrapers.counties import COUNTY_SCRAPERS


COUNTY_IDS = ("yavapai_az", "washoe_nv", "pinal_az")


def test_priority_counties_have_direct_arcgis_sources():
    for county_id in COUNTY_IDS:
        cfg = COUNTY_SCRAPERS[county_id]
        assert cfg["data_mode"] == "arcgis"
        assert "/FeatureServer/" in cfg["arcgis_layer_url"]
        assert cfg["fields"].get("apn")
        assert cfg["fields"].get("lot_size_acres")


def test_yavapai_has_vacant_layer_to_parcel_enrichment():
    cfg = COUNTY_SCRAPERS["yavapai_az"]
    enrichment = cfg["enrichment"]
    assert enrichment["join_source"] == "PARCELNO"
    assert enrichment["join_target"] == "PARCEL_ID"
    assert {"address", "owner_name", "zoning"}.issubset(enrichment["fields"])


def test_washoe_uses_assessor_land_use_and_improvement_value():
    cfg = COUNTY_SCRAPERS["washoe_nv"]
    assert cfg["fields"]["land_use"] == "LAND_USE"
    assert cfg["fields"]["improvement_value"] == "BUILDASS"
    assert cfg["fields"]["market_value"] == "TOTALASS"

    prop = map_attributes(
        {
            "APN": 123456,
            "ACREAGE": 2.5,
            "LAND_USE": "RESIDENTIAL",
            "BUILDASS": 0,
            "Zoning": "Residential",
        },
        cfg["fields"],
        "washoe_nv",
        cfg["defaults"],
    )
    assert is_vacant_residential(prop, "washoe_nv") is True


def test_pinal_zero_building_area_is_treated_as_no_improvement():
    cfg = COUNTY_SCRAPERS["pinal_az"]
    prop = map_attributes(
        {
            "PARCELID": "P-123",
            "GROSSAC": 5.0,
            "BLDGAREA": 0,
            "USEDSCRP": "RESIDENTIAL VACANT",
            "LNDVALUE": 18000,
            "CNTASSDVAL": 18000,
        },
        cfg["fields"],
        "pinal_az",
        cfg["defaults"],
    )
    assert prop["lot_size_acres"] == 5.0
    assert prop["improvement_value"] == 0.0
    assert is_vacant_residential(prop, "pinal_az") is True


def test_priority_counties_are_present_in_persistent_registry():
    for county_id in COUNTY_IDS:
        assert get_county(county_id) is not None
