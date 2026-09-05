from config.counties.national_registry import PILOT_COUNTIES
from scrapers.counties import COUNTY_SCRAPERS
from validation.national_validator import _config_for, validate_all_counties


def test_national_validation_returns_all_registered_counties():
    report = validate_all_counties()
    assert report["counts"]["total"] == len(report["results"])
    assert report["counts"]["total"] >= 3
    statuses={"not_started", "invalid", "ready", "etl_verified"}
    assert statuses >= (set(report["counts"]) - {"total"})


def test_national_validation_does_not_claim_etl_from_source_configuration():
    report = validate_all_counties()
    for row in report["results"]:
        if row["status"] == "ready":
            assert row["coverage_status"] not in {"tier_4", "tier_5"} or row["verification_status"] == "verified"


def test_national_validator_prefers_authoritative_pilot_source_metadata(monkeypatch):
    county_id = "el_paso_tx"
    authoritative = PILOT_COUNTIES[county_id]
    monkeypatch.setitem(COUNTY_SCRAPERS, county_id, {
        "scraper_type": "arcgis",
        "data_source_type": "arcgis",
        "arcgis_root": "https://stale.example/root",
        "arcgis_layer_url": "https://stale.example/layer",
        "gis_url": "https://stale.example/gis",
        "parcel_source_url": "https://stale.example/parcel",
        "fields": {"parcel_id": "stale_id"},
    })

    cfg = _config_for({"county_id": county_id, "field_mapping": {"parcel_id": "registered_id"}})

    assert cfg["arcgis_layer_url"] == authoritative["arcgis_layer_url"]
    assert cfg["arcgis_root"] == authoritative["arcgis_layer_url"]
    assert cfg["gis_url"] == authoritative["gis_url"]
    assert cfg["parcel_source_url"] == authoritative["parcel_source_url"]
    assert cfg["data_mode"] == "arcgis"
    assert cfg["fields"] == {"parcel_id": "stale_id"}
