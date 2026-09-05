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
    assert all(source.source_type == "statewide_portal" for source in sources)


def test_high_value_statewide_portals_are_registered():
    for state in ("Colorado", "Florida", "Maryland", "North Carolina"):
        sources = statewide_sources_for_state(state)
        assert len(sources) == 1
        assert sources[0].url.startswith("https://")


def test_unknown_state_has_no_false_positive():
    assert statewide_sources_for_state("Not A State") == []
