from discovery.statewide_coverage import build_statewide_coverage_report


def test_coverage_distinguishes_enumeration_discovery_and_verification():
    census = [
        {"county_id": "nc_001", "geoid": "37001", "state": "North Carolina", "state_fips": "37", "county_fips": "001"},
        {"county_id": "nc_003", "geoid": "37003", "state": "North Carolina", "state_fips": "37", "county_fips": "003"},
        {"county_id": "nc_005", "geoid": "37005", "state": "North Carolina", "state_fips": "37", "county_fips": "005"},
    ]
    reconciled = [
        {"county_id": "nc_001", "geoid": "37001", "state": "North Carolina", "state_fips": "37", "county_fips": "001", "reconciliation_status": "matched"},
        {"county_id": "nc_003", "geoid": "37003", "state": "North Carolina", "state_fips": "37", "county_fips": "003", "reconciliation_status": "matched"},
    ]
    registry = [
        {"county_id": "nc_001", "parcel_source_url": "https://example.test/nc1", "verification_status": "discovered_not_verified"},
        {"county_id": "nc_003", "parcel_source_url": "https://example.test/nc3", "validation_status": "valid"},
    ]

    report = build_statewide_coverage_report(reconciled, census, registry, states=["North Carolina"])
    nc = report["states"]["north carolina"]

    assert nc["expected_counties"] == 3
    assert nc["matched_counties"] == 2
    assert nc["source_discovered"] == 2
    assert nc["verified"] == 1
    assert nc["missing_counties"] == 1
    assert nc["missing_county_keys"] == ["nc_005"]
    assert nc["enumeration_coverage_ratio"] == 0.6667
    assert nc["source_discovery_ratio"] == 0.6667
    assert nc["verified_ratio"] == 0.3333


def test_coverage_scopes_requested_states():
    census = [
        {"county_id": "nc_001", "geoid": "37001", "state": "North Carolina", "state_fips": "37", "county_fips": "001"},
        {"county_id": "az_001", "geoid": "04001", "state": "Arizona", "state_fips": "04", "county_fips": "001"},
    ]
    reconciled = [
        {"county_id": "nc_001", "geoid": "37001", "state": "North Carolina", "state_fips": "37", "county_fips": "001", "reconciliation_status": "matched"},
    ]

    report = build_statewide_coverage_report(reconciled, census, states=["North Carolina"])
    assert list(report["states"]) == ["north carolina"]
    assert report["totals"]["expected_counties"] == 1
    assert report["totals"]["matched_counties"] == 1
    assert report["totals"]["enumeration_coverage_ratio"] == 1.0
