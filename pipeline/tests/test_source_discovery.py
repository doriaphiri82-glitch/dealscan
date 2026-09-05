from types import SimpleNamespace

from discovery import source_discovery


def _response(body):
    return SimpleNamespace(ok=True, body=body)


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
