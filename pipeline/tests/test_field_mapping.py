"""
DealScan - Field mapping tests.
"""
from __future__ import annotations

from config.field_mapping import FieldMapper, FIELD_ALIASES

import pytest


@pytest.fixture()
def mapper() -> FieldMapper:
    return FieldMapper()


class TestFieldMapper:
    def test_exact_alias_match(self, mapper: FieldMapper):
        mapping, results = mapper.map_fields([
            "APN", "SITUS_ADDR", "LAND_ACRES", "FULL_CASH_VALUE", "OWNER_NAME"
        ])
        assert mapping["parcel_id"] == "APN"
        assert mapping["property_address"] == "SITUS_ADDR"
        assert mapping["acreage"] == "LAND_ACRES"
        assert mapping["market_value"] == "FULL_CASH_VALUE"
        assert mapping["owner_name"] == "OWNER_NAME"

    def test_missing_field_returns_none(self, mapper: FieldMapper):
        mapping, results = mapper.map_fields(["UNKNOWN_FIELD"])
        assert mapping.get("parcel_id") is None
        assert mapping.get("market_value") is None

    def test_manual_override_is_honored(self, mapper: FieldMapper):
        mapping, results = mapper.map_fields(
            ["APN", "OWNER"],
            existing_map={"parcel_id": "OWNER"},
        )
        assert mapping["parcel_id"] == "OWNER"
        apn_result = next(r for r in results if r.canonical_field == "parcel_id")
        assert apn_result.method == "manual_override"
        assert apn_result.confidence == 1.0

    def test_validation_flags_missing_required(self, mapper: FieldMapper):
        mapping, _ = mapper.map_fields(["APN", "SITUS_ADDR", "LAND_ACRES", "FULL_CASH_VALUE"])
        report = mapper.validate_mapping(mapping, [
            {"APN": "123", "SITUS_ADDR": "123 Main", "LAND_ACRES": "2.5", "FULL_CASH_VALUE": "abc"}
        ])
        assert "parcel_id" in report["required_found"]
        assert "property_address" in report["required_found"]
        assert "acreage" in report["required_found"]
        assert "market_value" in report["required_found"]
        assert any("not numeric" in issue for issue in report["field_issues"])

    def test_alias_registry_coverage(self):
        for canonical in FIELD_ALIASES:
            assert canonical
            assert isinstance(FIELD_ALIASES[canonical], list)
            assert FIELD_ALIASES[canonical]
