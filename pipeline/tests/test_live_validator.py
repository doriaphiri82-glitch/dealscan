from validation import live_validator


def test_live_validator_accepts_matching_layer(monkeypatch):
    county={"county_id":"test_aa","county_name":"Test County","state":"Arizona","field_mapping":{}}
    cfg={"scraper_type":"arcgis","arcgis_layer_url":"https://example.test/FeatureServer/0","fields":{"apn":"APN","address":"SITUS_ADDR","lot_size_acres":"ACRES","market_value":"VALUE","owner_name":"OWNER"}}
    monkeypatch.setattr(live_validator,"_config",lambda _:cfg)
    monkeypatch.setattr(live_validator,"_resolve_layer",lambda _:cfg["arcgis_layer_url"])
    monkeypatch.setattr(live_validator.arcgis,"layer_fields",lambda _: ["APN","SITUS_ADDR","ACRES","VALUE","OWNER"])
    monkeypatch.setattr(live_validator.arcgis,"query_layer",lambda *a,**k:[{"APN":"1","SITUS_ADDR":"1 Main","ACRES":2,"VALUE":10000,"OWNER":"Owner"}])
    monkeypatch.setattr(live_validator,"mark_county_validation",lambda *a,**k:None)
    monkeypatch.setattr(live_validator,"update_county",lambda *a,**k:None)
    result=live_validator.validate_county_live(county)
    assert result["status"]=="valid"
    assert result["sample_count"]==1


def test_live_validator_records_unreachable(monkeypatch):
    county={"county_id":"test_bb","county_name":"Test County","state":"Arizona"}
    monkeypatch.setattr(live_validator,"_config",lambda _: {})
    monkeypatch.setattr(live_validator,"_resolve_layer",lambda _: "")
    monkeypatch.setattr(live_validator,"mark_county_validation",lambda *a,**k:None)
    result=live_validator.validate_county_live(county)
    assert result["status"]=="unreachable"
