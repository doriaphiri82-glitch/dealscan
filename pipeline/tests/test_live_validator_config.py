from config.counties.national_registry import PILOT_COUNTIES
from validation.live_validator import _config
import validation.live_validator as live_validator


def test_live_validation_uses_authoritative_pilot_endpoint(monkeypatch):
    stale = dict(live_validator.COUNTY_SCRAPERS["el_paso_tx"])
    stale["arcgis_layer_url"] = "https://example.invalid/FeatureServer/999"
    stale["arcgis_root"] = "https://example.invalid/FeatureServer/999"
    monkeypatch.setitem(live_validator.COUNTY_SCRAPERS, "el_paso_tx", stale)

    cfg = _config({"county_id": "el_paso_tx"})

    assert cfg["arcgis_layer_url"] == PILOT_COUNTIES["el_paso_tx"]["arcgis_layer_url"]
    assert cfg["arcgis_root"] == PILOT_COUNTIES["el_paso_tx"]["arcgis_layer_url"]
    assert cfg["fields"] == stale["fields"]
