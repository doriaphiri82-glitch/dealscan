from discovery.statewide_reconciliation import build_coverage_report, reconcile_statewide_counties


def test_reconcile_prefers_state_and_county_fips():
    statewide = [
        {
            "state": "North Carolina",
            "state_fips": "37",
            "county_fips": "001",
            "county_name": "Alamance",
            "source_url": "https://example.test/nc",
            "verified": False,
        }
    ]
    census = [
        {
            "county_id": "alamance_37_001",
            "county_name": "Alamance County",
            "state": "North Carolina",
            "state_fips": "37",
            "county_fips": "001",
            "geoid": "37001",
        }
    ]

    result = reconcile_statewide_counties(statewide, census)

    assert result[0]["reconciliation_status"] == "matched"
    assert result[0]["reconciliation_method"] == "fips"
    assert result[0]["county_id"] == "alamance_37_001"
    assert result[0]["geoid"] == "37001"
    assert result[0]["verified"] is False


def test_coverage_report_identifies_missing_census_counties():
    statewide = [
        {"state_fips": "12", "county_fips": "001", "reconciliation_status": "matched", "geoid": "12001"},
        {"state_fips": "12", "county_fips": "999", "reconciliation_status": "unmatched"},
    ]
    census = [
        {"state_fips": "12", "county_fips": "001", "geoid": "12001"},
        {"state_fips": "12", "county_fips": "003", "geoid": "12003"},
    ]

    report = build_coverage_report(statewide, census)

    assert report["expected_counties"] == 2
    assert report["discovered_counties"] == 2
    assert report["matched_counties"] == 1
    assert report["missing_counties"] == 1
    assert report["unmatched_discoveries"] == 1
    assert report["coverage_ratio"] == 0.5
