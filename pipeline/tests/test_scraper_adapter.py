from scrapers.arcgis import is_vacant_residential
from scrapers.arcgis_adapter import ArcGISFeatureServerAdapter
from runners import _vacancy_rejection_reason


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


def test_vacancy_diagnostic_distinguishes_missing_signal():
    assert _vacancy_rejection_reason(
        {"land_use": None, "zoning": None, "has_improvements": None},
        "el_paso_tx",
    ) == "missing_vacancy_signal"


def test_vacancy_diagnostic_distinguishes_improved_property():
    assert _vacancy_rejection_reason(
        {"land_use": "Residential", "has_improvements": True},
        "el_paso_tx",
    ) == "improved_property"


def test_vacancy_diagnostic_distinguishes_unsupported_classification():
    assert _vacancy_rejection_reason(
        {"land_use": "Agricultural", "zoning": None, "has_improvements": False},
        "el_paso_tx",
    ) == "no_supported_vacancy_classification"


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
    assert result.metadata["source_fields"] == ["APN"]
    assert result.metadata["resolved_fields"]["apn"] == "APN"


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


def test_arcgis_adapter_records_partial_result_state(monkeypatch):
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
            "fields": {"apn": "APN"},
        },
        max_records=10,
    )
    assert records
    assert result.metadata["partial_results"] is False
