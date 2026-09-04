"""DealScan - scraper tests (no network; use fixtures)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers import arcgis  # noqa: E402

FIXTURE = {
    "attributes": {
        "APN": "123-45-678A",
        "SITUS_ADDR": "Lot 12, Sierra Vista Estates",
        "LAND_ACRES": "2.31",
        "LIMITED_VALUE": 2100,
        "FULL_CASH_VALUE": 9700,
        "OWNER_NAME": "JOHN R SMITH",
        "OWNER_MAIL_STATE": "CA",
        "TAX_AMT": "45.00",
        "TAX_DELINQ_YEARS": 3,
        "SALE_YEAR": 2008,
        "ZONING": "RURAL RESIDENTIAL",
        "LAND_USE": "VACANT",
        "HAS_IMPROVEMENTS": "N",
        "LATITUDE": 31.5,
        "LONGITUDE": -109.9,
        "SALE_PRICE": 2100,
        "SALE_DATE": 2010,
    }
}

FIELD_MAP = {
    "apn": "APN",
    "address": "SITUS_ADDR",
    "lot_size_acres": "LAND_ACRES",
    "assessed_value": "LIMITED_VALUE",
    "market_value": "FULL_CASH_VALUE",
    "owner_name": "OWNER_NAME",
    "owner_state": "OWNER_MAIL_STATE",
    "tax_amount": "TAX_AMT",
    "tax_delinquent_years": "TAX_DELINQ_YEARS",
    "year_acquired": "SALE_YEAR",
    "zoning": "ZONING",
    "land_use": "LAND_USE",
    "has_improvements": "HAS_IMPROVEMENTS",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "last_sale_price": "SALE_PRICE",
    "last_sale_date": "SALE_DATE",
}


def test_map_attributes():
    prop = arcgis.map_attributes(FIXTURE["attributes"], FIELD_MAP,
                                 "cochise_az", {"county_state": "Arizona"})
    assert prop["apn"] == "123-45-678A"
    assert prop["lot_size_acres"] == 2.31
    assert prop["market_value"] == 9700.0
    assert prop["tax_delinquent_years"] == 3
    assert prop["county_id"] == "cochise_az"
    assert prop["county_state"] == "Arizona"
    assert prop["latitude"] == 31.5
    assert prop["longitude"] == -109.9


def test_to_float_handles_garbage():
    assert arcgis._to_float(None) is None
    assert arcgis._to_float("") is None
    assert arcgis._to_float("abc") is None
    assert arcgis._to_float("2.5") == 2.5


def test_is_vacant_residential():
    assert not arcgis.is_vacant_residential({"has_improvements": False}, "x")
    assert not arcgis.is_vacant_residential({"has_improvements": "N"}, "x")
    assert arcgis.is_vacant_residential({"has_improvements": False, "land_use": "Residential"}, "x")
    assert arcgis.is_vacant_residential({"land_use": "Vacant Land"}, "x")
    assert not arcgis.is_vacant_residential({"has_improvements": True, "land_use": "house"}, "x")
