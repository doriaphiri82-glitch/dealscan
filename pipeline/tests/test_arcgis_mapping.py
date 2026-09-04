from scrapers.arcgis import map_attributes, resolve_field_mapping


def test_resolve_field_mapping_matches_source_case():
    mapping = {
        "apn": "apn",
        "address": "situs_addr",
        "lot_size_acres": "acres",
    }
    resolved = resolve_field_mapping(mapping, ["APN", "SITUS_ADDR", "ACRES"])
    assert resolved == {
        "apn": "APN",
        "address": "SITUS_ADDR",
        "lot_size_acres": "ACRES",
    }


def test_map_attributes_reads_source_case_insensitively():
    attrs = {"APN": "123", "SITUS_ADDR": "1 Main", "ACRES": 2.5}
    mapping = {"apn": "apn", "address": "situs_addr", "lot_size_acres": "acres"}
    result = map_attributes(attrs, mapping, "test_aa", {})
    assert result["apn"] == "123"
    assert result["address"] == "1 Main"
    assert result["lot_size_acres"] == 2.5


def test_map_attributes_supports_case_insensitive_nested_paths():
    attrs = {"Owner": {"Name": "Owner One"}}
    result = map_attributes(attrs, {"owner_name": "owner.name"}, "test_aa", {})
    assert result["owner_name"] == "Owner One"
