from scrapers import arcgis


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
