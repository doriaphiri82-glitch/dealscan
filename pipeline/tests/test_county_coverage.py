from config.counties.registry import get_county
from scrapers.arcgis import is_vacant_residential,map_attributes
from scrapers.counties import COUNTY_SCRAPERS

COUNTY_IDS=("cochise_az","mohave_az","el_paso_tx","yavapai_az","washoe_nv","pinal_az","hudson_co","socorro_nm")

def test_all_configured_counties_have_sources():
    assert set(COUNTY_IDS).issubset(COUNTY_SCRAPERS)
    for county_id in COUNTY_IDS:
        cfg=COUNTY_SCRAPERS[county_id]; assert cfg["data_mode"]=="arcgis"; assert "/FeatureServer/" in cfg["arcgis_layer_url"] or "/MapServer/" in cfg["arcgis_layer_url"]; assert cfg["fields"].get("apn"); assert cfg["fields"].get("lot_size_acres")

def test_yavapai_has_vacant_layer_to_parcel_enrichment():
    cfg=COUNTY_SCRAPERS["yavapai_az"]; enrichment=cfg["enrichment"]; assert enrichment["join_source"]=="PARCELNO"; assert enrichment["join_target"]=="PARCEL_ID"; assert {"address","owner_name","zoning"}.issubset(enrichment["fields"])

def test_washoe_uses_assessor_land_use_and_improvement_value():
    cfg=COUNTY_SCRAPERS["washoe_nv"]; assert cfg["fields"]["land_use"]=="LAND_USE"; assert cfg["fields"]["improvement_value"]=="BUILDASS"; assert cfg["fields"]["market_value"]=="TOTALASS"
    prop=map_attributes({"APN":123456,"ACREAGE":2.5,"LAND_USE":"RESIDENTIAL","BUILDASS":0,"Zoning":"Residential"},cfg["fields"],"washoe_nv",cfg["defaults"]); assert is_vacant_residential(prop,"washoe_nv") is True

def test_pinal_zero_building_area_is_treated_as_no_improvement():
    cfg=COUNTY_SCRAPERS["pinal_az"]; prop=map_attributes({"PARCELID":"P-123","GROSSAC":5.0,"BLDGAREA":0,"USEDSCRP":"RESIDENTIAL VACANT","LNDVALUE":18000,"CNTASSDVAL":18000},cfg["fields"],"pinal_az",cfg["defaults"]); assert prop["lot_size_acres"]==5.0; assert prop["improvement_value"]==0.0; assert is_vacant_residential(prop,"pinal_az") is True

def test_huerfano_uses_colorado_state_parcel_composite():
    cfg=COUNTY_SCRAPERS["hudson_co"]; assert "gis.colorado.gov" in cfg["arcgis_layer_url"]; assert "08055" in cfg["where"]; prop=map_attributes({"parcel_id":"H-1","landAcres":3.2,"landUseDsc":"Vacant Land","zoningDesc":"Residential"},cfg["fields"],"hudson_co",cfg["defaults"]); assert prop["lot_size_acres"]==3.2; assert is_vacant_residential(prop,"hudson_co") is True

def test_socorro_uses_state_parcel_layer_and_structure_count():
    cfg=COUNTY_SCRAPERS["socorro_nm"]; assert "/MapServer/28" in cfg["arcgis_layer_url"]; prop=map_attributes({"AccountNumber":"R123","LandArea":1.0,"LandUseDescription":"Residential","ZoningDescription":"Residential","StructureCount":0},cfg["fields"],"socorro_nm",cfg["defaults"]); assert prop["improvement_value"]==0.0; assert is_vacant_residential(prop,"socorro_nm") is True

def test_all_configured_counties_are_present_in_persistent_registry():
    for county_id in COUNTY_IDS: assert get_county(county_id) is not None
