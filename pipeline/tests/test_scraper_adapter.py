from scrapers.arcgis import is_vacant_residential
from scrapers.arcgis_adapter import ArcGISFeatureServerAdapter


def test_unknown_improvement_status_is_not_treated_as_vacant():
    assert not is_vacant_residential(
        {"land_use": "", "zoning": "", "has_improvements": None},
        "el_paso_tx",
    )


def test_known_residential_no_improvements_is_vacant():
    assert is_vacant_residential(
        {"land_use": "Residential", "has_improvements": False},
        "el_paso_tx",
    )


def test_arcgis_adapter_resolves_field_casing(monkeypatch):
    class Response:
        ok = True
        body = {"features": [{"attributes": {"APN": "123"}}]}
        error = None

    monkeypatch.setattr("scrapers.arcgis_adapter.layer_fields", lambda *_: ["APN"])
    monkeypatch.setattr("scrapers.arcgis_adapter.post_json", lambda *args, **kwargs: Response())
    adapter = ArcGISFeatureServerAdapter()
    result, records = adapter.run(
        {
            "county_id": "test_county",
            "arcgis_layer_url": "https://example.com/FeatureServer/0",
            "fields": {"apn": "apn"},
        },
        max_records=10,
    )
    assert records and records[0]["apn"] == "123"
    assert result.errors == []


def test_arcgis_adapter_surfaces_source_errors(monkeypatch):
    class Response:
        ok = False
        body = None
        error = "timeout"

    monkeypatch.setattr("scrapers.arcgis_adapter.layer_fields", lambda *_: ["APN"])
    monkeypatch.setattr("scrapers.arcgis_adapter.post_json", lambda *args, **kwargs: Response())
    adapter = ArcGISFeatureServerAdapter()
    result, records = adapter.run(
        {
            "county_id": "test_county",
            "arcgis_layer_url": "https://example.com/FeatureServer/0",
            "fields": {"apn": "APN"},
        },
        max_records=10,
    )
    assert records == []
    assert result.errors
    assert any("timeout" in error for error in result.errors)


def test_arcgis_adapter_rejects_empty_layer_metadata(monkeypatch):
    monkeypatch.setattr("scrapers.arcgis_adapter.layer_fields", lambda *_: [])
    adapter = ArcGISFeatureServerAdapter()
    result, records = adapter.run(
        {
            "county_id": "test_county",
            "arcgis_layer_url": "https://example.com/FeatureServer/0",
            "fields": {"apn": "APN"},
        },
        max_records=10,
    )
    assert records == []
    assert any("metadata contains no fields" in error for error in result.errors)
