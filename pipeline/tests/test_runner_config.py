from runners import _county_config
from config.counties.national_registry import PILOT_COUNTIES
import runners


def test_pilot_source_identity_overrides_stale_scraper_endpoint(monkeypatch):
    stale = dict(runners.COUNTY_SCRAPERS["el_paso_tx"])
    stale["arcgis_layer_url"] = "https://example.invalid/FeatureServer/999"
    stale["arcgis_root"] = "https://example.invalid/FeatureServer/999"
    monkeypatch.setitem(runners.COUNTY_SCRAPERS, "el_paso_tx", stale)

    cfg = _county_config("el_paso_tx")

    assert cfg["arcgis_layer_url"] == PILOT_COUNTIES["el_paso_tx"]["arcgis_layer_url"]
    assert cfg["arcgis_root"] == PILOT_COUNTIES["el_paso_tx"]["arcgis_layer_url"]
    assert cfg["fields"] == stale["fields"]
