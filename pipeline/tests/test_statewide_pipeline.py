from discovery.statewide_pipeline import reconcile_enumerated_statewide_counties


def test_raw_statewide_enumeration_gets_state_fips_before_reconciliation():
    statewide = [
        {
            "state": "Florida",
            "county_fips": "001",
            "county_name": "Alachua",
            "source_type": "arcgis_layer",
            "verified": False,
        }
    ]
    census = [
        {
            "county_id": "alachua_12_001",
            "county_name": "Alachua County",
            "state": "Florida",
            "state_fips": "12",
            "county_fips": "001",
            "geoid": "12001",
        }
    ]

    result = reconcile_enumerated_statewide_counties(statewide, census)

    assert result[0]["state_fips"] == "12"
    assert result[0]["reconciliation_status"] == "matched"
    assert result[0]["reconciliation_method"] == "fips"
    assert result[0]["county_id"] == "alachua_12_001"
