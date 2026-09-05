from discovery.statewide_queue import build_county_discovery_queue


def test_queue_only_contains_reconciled_unverified_counties():
    reconciled = [
        {
            "county_id": "alachua_12_001",
            "county_name": "Alachua County",
            "state": "Florida",
            "state_fips": "12",
            "county_fips": "001",
            "geoid": "12001",
            "source_url": "https://example.test/florida",
            "source_type": "arcgis_layer",
            "reconciliation_status": "matched",
        },
        {
            "county_id": "bad_12_999",
            "state_fips": "12",
            "county_fips": "999",
            "reconciliation_status": "unmatched",
        },
    ]

    result = build_county_discovery_queue(reconciled)

    assert [row["county_id"] for row in result] == ["alachua_12_001"]
    assert result[0]["verified"] is False
    assert result[0]["next_step"] == "discover_arcgis_county_config"


def test_queue_skips_existing_verified_counties_and_deduplicates():
    reconciled = [
        {"county_id": "a_12_001", "state_fips": "12", "county_fips": "001", "reconciliation_status": "matched"},
        {"county_id": "a_12_001", "state_fips": "12", "county_fips": "001", "reconciliation_status": "matched"},
        {"county_id": "b_12_003", "state_fips": "12", "county_fips": "003", "reconciliation_status": "matched"},
    ]
    registry = [{"county_id": "b_12_003", "verification_status": "source_verified"}]

    result = build_county_discovery_queue(reconciled, registry)

    assert [row["county_id"] for row in result] == ["a_12_001"]
