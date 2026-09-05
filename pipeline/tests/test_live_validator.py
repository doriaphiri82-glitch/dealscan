from validation import live_validator
from helpers import layer_metadata


def _cfg():
    return {"scraper_type":"arcgis","arcgis_layer_url":"https://example.test/FeatureServer/0","fields":{"apn":"APN","address":"SITUS_ADDR","lot_size_acres":"ACRES","market_value":"VALUE","owner_name":"OWNER"}}


def _patch_persistence(monkeypatch):
    monkeypatch.setattr(live_validator,"mark_county_validation",lambda *a,**k:None)
    monkeypatch.setattr(live_validator,"update_county",lambda *a,**k:None)


def test_live_validator_accepts_matching_layer(monkeypatch):
    county={"county_id":"test_aa","county_name":"Test County","state":"Arizona","field_mapping":{}}
    cfg=_cfg()
    monkeypatch.setattr(live_validator,"_config",lambda _:cfg)
    monkeypatch.setattr(live_validator,"_resolve_layer",lambda _:cfg["arcgis_layer_url"])
    monkeypatch.setattr(live_validator.arcgis,"layer_metadata",lambda *a,**k: layer_metadata(["APN","SITUS_ADDR","ACRES","VALUE","OWNER"]))
    monkeypatch.setattr(live_validator.arcgis,"query_count",lambda *a,**k:1)
    monkeypatch.setattr(live_validator.arcgis,"query_layer",lambda *a,**k:[{"APN":"1","SITUS_ADDR":"1 Main","ACRES":2,"VALUE":10000,"OWNER":"Owner"}])
    _patch_persistence(monkeypatch)
    result=live_validator.validate_county_live(county)
    assert result["status"]=="valid"
    assert result["sample_count"]==1


def test_live_validator_resolves_source_field_casing(monkeypatch):
    county={"county_id":"test_case","county_name":"Test County","state":"Arizona","field_mapping":{}}
    cfg={**_cfg(),"fields":{"apn":"apn","address":"situs_addr","lot_size_acres":"acres","market_value":"value","owner_name":"owner"}}
    monkeypatch.setattr(live_validator,"_config",lambda _:cfg)
    monkeypatch.setattr(live_validator,"_resolve_layer",lambda _:cfg["arcgis_layer_url"])
    monkeypatch.setattr(live_validator.arcgis,"layer_metadata",lambda *a,**k: layer_metadata(["APN","SITUS_ADDR","ACRES","VALUE","OWNER"]))
    monkeypatch.setattr(live_validator.arcgis,"query_count",lambda *a,**k:1)
    captured={}
    def query(*args,**kwargs):
        captured["fields"]=args[2]
        return [{"APN":"1","SITUS_ADDR":"1 Main","ACRES":2,"VALUE":10000,"OWNER":"Owner"}]
    monkeypatch.setattr(live_validator.arcgis,"query_layer",query)
    _patch_persistence(monkeypatch)
    result=live_validator.validate_county_live(county)
    assert result["status"]=="valid"
    assert captured["fields"]==["APN","SITUS_ADDR","ACRES","VALUE","OWNER"]


def test_live_validator_rejects_empty_live_layer(monkeypatch):
    county={"county_id":"test_empty","county_name":"Test County","state":"Arizona","field_mapping":{}}
    cfg=_cfg()
    monkeypatch.setattr(live_validator,"_config",lambda _:cfg)
    monkeypatch.setattr(live_validator,"_resolve_layer",lambda _:cfg["arcgis_layer_url"])
    monkeypatch.setattr(live_validator.arcgis,"layer_metadata",lambda *a,**k: layer_metadata(["APN","SITUS_ADDR","ACRES","VALUE","OWNER"]))
    monkeypatch.setattr(live_validator.arcgis,"query_count",lambda *a,**k:1)
    monkeypatch.setattr(live_validator.arcgis,"query_layer",lambda *a,**k:[])
    _patch_persistence(monkeypatch)
    result=live_validator.validate_county_live(county)
    assert result["status"]=="invalid"
    assert "live layer returned no sample records" in result["errors"]


def test_live_validator_records_unreachable(monkeypatch):
    county={"county_id":"test_bb","county_name":"Test County","state":"Arizona"}
    monkeypatch.setattr(live_validator,"_config",lambda _: {})
    monkeypatch.setattr(live_validator,"_resolve_layer",lambda _: "")
    monkeypatch.setattr(live_validator,"mark_county_validation",lambda *a,**k:None)
    result=live_validator.validate_county_live(county)
    assert result["status"]=="unreachable"
