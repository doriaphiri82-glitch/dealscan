from scrapers.adapter import BaseScraperAdapter
from scrapers.arcgis_adapter import ArcGISFeatureServerAdapter


class MappingAdapter(BaseScraperAdapter):
    def discover(self, cfg):
        return [{"PARCEL_ID": "ABC-123", "VALUE": "125000"}]

    def parse(self, raw):
        return [raw]

    def validate(self, record):
        return bool(record.get("apn"))


def test_normalization_happens_before_validation():
    result, records = MappingAdapter().run(
        {
            "county_id": "example",
            "fields": {"apn": "PARCEL_ID", "market_value": "VALUE"},
        }
    )
    assert result.normalized == 1
    assert result.rejected == 0
    assert records[0]["apn"] == "ABC-123"
    assert records[0]["market_value"] == 125000.0


def test_arcgis_adapter_records_source_errors():
    adapter = ArcGISFeatureServerAdapter()
    adapter.last_error = "HTTP 503"
    result, _ = adapter.run({"county_id": "example", "arcgis_layer_url": "https://example.invalid/FeatureServer/0"})
    assert result.errors
    assert any("source_error" in error for error in result.errors)
