from discovery.statewide_sources import all_statewide_sources, statewide_sources_for_state


def test_statewide_source_lookup_is_case_insensitive():
    sources = statewide_sources_for_state("oHIO")
    assert len(sources) == 1
    assert sources[0].name == "Ohio Parcels"
    assert sources[0].source_type == "statewide_portal"


def test_statewide_sources_have_unique_urls_and_valid_metadata():
    sources = all_statewide_sources()
    urls = [source.url for source in sources]
    assert len(sources) >= 8
    assert len(urls) == len(set(urls))
    assert all(source.state.strip() for source in sources)
    assert all(source.name.strip() for source in sources)
    assert all(source.url.startswith("https://") for source in sources)
    assert all(source.source_type in {"statewide_portal", "arcgis_layer"} for source in sources)


def test_high_value_statewide_portals_are_registered():
    for state in ("Colorado", "Florida", "Maryland", "North Carolina"):
        sources = statewide_sources_for_state(state)
        assert len(sources) == 1
        assert sources[0].url.startswith("https://")


def test_arcgis_statewide_sources_expose_county_enumeration_fields():
    florida = statewide_sources_for_state("Florida")[0]
    north_carolina = statewide_sources_for_state("North Carolina")[0]
    washington = statewide_sources_for_state("Washington")[0]

    assert florida.source_type == "arcgis_layer"
    assert florida.county_fips_field == "CO_NO"
    assert florida.parcel_id_field == "PARCEL_ID"

    assert north_carolina.county_name_field == "cntyname"
    assert north_carolina.county_fips_field == "cntyfips"
    assert north_carolina.parcel_id_field == "parno"

    assert washington.county_name_field == "COUNTY_NM"
    assert washington.county_fips_field == "FIPS_NR"
    assert washington.parcel_id_field == "PARCEL_ID_NR"


def test_unknown_state_has_no_false_positive():
    assert statewide_sources_for_state("Not A State") == []
