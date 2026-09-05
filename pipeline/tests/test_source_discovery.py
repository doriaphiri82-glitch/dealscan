from types import SimpleNamespace

from discovery import source_discovery


def _response(body):
    return SimpleNamespace(ok=True, body=body)


def test_statewide_portals_are_discovery_candidates_only():
    candidates = source_discovery.discover_statewide_sources("North Carolina")
    assert len(candidates) == 1
    assert candidates[0].source_type == "arcgis_layer"
    assert candidates[0].confidence < 1.0
    assert "verification" in candidates[0].notes


def test_unknown_state_has_no_statewide_candidates():
    assert source_discovery.discover_statewide_sources("Not A State") == []


def test_statewide_arcgis_layer_enumerates_distinct_counties(monkeypatch):
    requested = []

    def fake_fetch(url, **kwargs):
        requested.append(url)
        return _response({
            "features": [
                {"attributes": {"cntyname": "Alpha County", "cntyfips": "1"}},
                {"attributes": {"cntyname": "Beta County", "cntyfips": "002"}},
                {"attributes": {"cntyname": "Alpha County", "cntyfips": "001"}},
            ]
        })

    monkeypatch.setattr(source_discovery, "fetch", fake_fetch)
    result = source_discovery.enumerate_statewide_counties("North Carolina")

    assert len(result) == 2
    assert result[0]["county_fips"] == "001"
    assert result[0]["county_name"] == "Alpha County"
    assert result[0]["discovery_status"] == "DISCOVERED_NOT_VERIFIED"
    assert result[0]["verified"] is False
    assert "returnDistinctValues=true" in requested[0]


def test_statewide_enumeration_falls_back_to_server_side_grouping(monkeypatch):
    requested = []

    def fake_fetch(url, **kwargs):
        requested.append(url)
        if "returnDistinctValues=true" in url:
            return _response({"error": {"code": 400, "message": "distinct values unsupported"}})
        return _response({
            "features": [
                {"attributes": {"cntyname": "Alpha County", "cntyfips": "001", "parcel_count": 123}},
                {"attributes": {"cntyname": "Beta County", "cntyfips": "002", "parcel_count": 456}},
            ]
        })

    monkeypatch.setattr(source_discovery, "fetch", fake_fetch)
    result = source_discovery.enumerate_statewide_counties("North Carolina")

    assert [row["county_fips"] for row in result] == ["001", "002"]
    assert "groupByFieldsForStatistics=cntyname%2Ccntyfips" in requested[1]
    assert "outStatistics" in requested[1]


def test_statewide_enumeration_falls_back_when_distinct_query_is_truncated(monkeypatch):
    requested = []

    def fake_fetch(url, **kwargs):
        requested.append(url)
        if "returnDistinctValues=true" in url:
            return _response({"features": [{"attributes": {"cntyname": "Alpha County", "cntyfips": "001"}}], "exceededTransferLimit": True})
        return _response({"features": [{"attributes": {"cntyname": "Beta County", "cntyfips": "002", "parcel_count": 10}}]})

    monkeypatch.setattr(source_discovery, "fetch", fake_fetch)
    result = source_discovery.enumerate_statewide_counties("North Carolina")

    assert [row["county_fips"] for row in result] == ["002"]
    assert len(requested) == 2


def test_unknown_state_has_no_enumerated_counties():
    assert source_discovery.enumerate_statewide_counties("Not A State") == []


def test_discovery_rejects_generic_geometry_layer(monkeypatch):
    calls = []

    def fake_fetch(url, **kwargs):
        calls.append(url)
        return _response({
            "results": [{
                "type": "Feature Service",
                "title": "Cochise County Roads",
                "snippet": "County transportation network",
                "url": "https://example.test/roads",
            }]
        })

    monkeypatch.setattr(source_discovery, "fetch", fake_fetch)
    assert source_discovery.discover_arcgis_county_config("cochise_az", "Cochise County", "Arizona") is None
    assert len(calls) == 1


def test_discovery_requires_parcel_identifier_and_useful_fields(monkeypatch):
    responses = {
        "https://example.test/parcels?f=json": {
            "fields": [
                {"name": "OBJECTID", "alias": "Object ID"},
                {"name": "Shape", "alias": "Shape"},
            ],
            "objectIdField": "OBJECTID",
            "geometryType": "esriGeometryPolygon",
        },
    }

    def fake_fetch(url, **kwargs):
        if "sharing/rest/search" in url:
            return _response({
                "results": [{
                    "type": "Feature Service",
                    "title": "Cochise County Parcels",
                    "snippet": "Official parcel boundaries",
                    "url": "https://example.test/parcels",
                }]
            })
        return _response(responses[url])

    monkeypatch.setattr(source_discovery, "fetch", fake_fetch)
    assert source_discovery.discover_arcgis_county_config("cochise_az", "Cochise County", "Arizona") is None


def test_discovery_accepts_strong_parcel_layer(monkeypatch):
    def fake_fetch(url, **kwargs):
        if "sharing/rest/rest" in url:
            return _response({"results": []})
        if "sharing/rest/search" in url:
            return _response({
                "results": [{
                    "type": "Feature Service",
                    "title": "Cochise County Parcels",
                    "snippet": "Assessor property parcels",
                    "url": "https://example.test/parcels",
                    "modified": 1757000000000,
                }]
            })
        return _response({
            "fields": [
                {"name": "APN", "alias": "Parcel Number"},
                {"name": "SITUS_ADDR", "alias": "Situs Address"},
                {"name": "ACRES", "alias": "Lot Acres"},
                {"name": "MARKET_VALUE", "alias": "Market Value"},
                {"name": "OWNER_NAME", "alias": "Owner Name"},
                {"name": "LAND_USE", "alias": "Land Use"},
            ],
            "objectIdField": "OBJECTID",
            "geometryType": "esriGeometryPolygon",
        })

    monkeypatch.setattr(source_discovery, "fetch", fake_fetch)
    result = source_discovery.discover_arcgis_county_config("cochise_az", "Cochise County", "Arizona")
    assert result is not None
    assert result["arcgis_layer_url"] == "https://example.test/parcels"
    assert result["source_quality"] == "usable"
    assert result["source_quality_score"] >= 55
    assert result["verified"] is False
