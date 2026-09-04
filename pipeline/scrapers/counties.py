"""DealScan - per-county scraper registry."""
from __future__ import annotations
from typing import Any, Dict, List
from . import arcgis
from .base import probe, ProbeResult

_DEFAULT_FIELDS = {"apn":"APN","address":"SITUS_ADDR","lot_size_acres":"LAND_ACRES","assessed_value":"LIMITED_VALUE","market_value":"FULL_CASH_VALUE","owner_name":"OWNER_NAME","owner_address":"OWNER_MAIL_ADDR","owner_state":"OWNER_MAIL_STATE","tax_amount":"TAX_AMT","tax_delinquent_years":"TAX_DELINQ_YEARS","year_acquired":"SALE_YEAR","zoning":"ZONING","land_use":"LAND_USE","has_improvements":"HAS_IMPROVEMENTS","legal_description":"LEGAL_DESC","latitude":"LATITUDE","longitude":"LONGITUDE","last_sale_price":"SALE_PRICE","last_sale_date":"SALE_DATE"}

COUNTY_SCRAPERS: Dict[str, Dict[str, Any]] = {
    "cochise_az": {"name":"Cochise County, AZ","arcgis_root":"https://gis-cochise.opendata.arcgis.com","services":[("Parcels","Parcels",["parcel","ownership"]),("Assessor","Assessor",["parcel","ownership"]),("Hosted","Hosted",["parcel","ownership"])],"fields":{"apn":"apn","address":"situs_address","lot_size_acres":"acres","market_value":"fcv","owner_name":"owner_name1","owner_address":"address1","owner_state":"state","land_use":"use_code","legal_description":"legal_text","longitude":"geo_x","latitude":"geo_y"},"defaults":{"county_state":"Arizona"},"where":"1=1","verified":True,"html_search_url":"https://parcelinquirytreasurer.cochise.az.gov/Main/ParcelSearch","delinquent_list_url":"https://www.cochise.az.gov/treasurer"},
    "mohave_az": {"name":"Mohave County, AZ","arcgis_root":"https://az-mohave.opendata.arcgis.com","services":[("Parcels","Parcels",["parcel","ownership"]),("Hosted","Hosted",["parcel","ownership"])],"fields":{"apn":"TAXPIN","address":"SITE_ADDRESS","owner_name":"OWNER","owner_address":"MAILING_ADDRESS","owner_state":"STATE","market_value":"ASSESSED_FULL_CASH_VALUE"},"defaults":{"county_state":"Arizona"},"where":"1=1","verified":True,"html_search_url":"https://www.mohave.gov/departments/assessor/assessor-search/","delinquent_list_url":"https://www.mohave.gov/departments/information-technology/gis-maps/"},
    "el_paso_tx": {"name":"El Paso County, TX","data_mode":"arcgis","arcgis_layer_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","arcgis_root":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","fields":{"apn":"prop_id_text","address":["situs_num","situs_street_prefx","situs_street","situs_street_sufix","situs_city","situs_state","situs_zip"],"lot_size_acres":"legal_acreage","market_value":"market","improvement_value":"imprv_val","legal_description":["legal_desc","legal_desc2","legal_desc3"],"owner_name":"file_as_name"},"defaults":{"county_state":"Texas","land_use":"VACANT"},"where":"legal_acreage > 0 AND imprv_val = 0","verified":True,"html_search_url":"https://www.epcad.org","status":"EPCAD direct ArcGIS FeatureServer; vacant-land query uses official improvement value"},
    "yavapai_az": {"name":"Yavapai County, AZ","data_mode":"arcgis","arcgis_layer_url":"https://gis.yavapaiaz.gov/arcgis/rest/services/Property/FeatureServer/10","arcgis_root":"https://gis.yavapaiaz.gov/arcgis/rest/services/Property/FeatureServer/10","fields":{"apn":"PARLABEL","address":["SITENUMBER","SITESTREET","SITECITY","ZIPCODE"],"lot_size_acres":"ACREGIS","land_use":"LANDUSE","zoning":"ZONING","owner_name":"OWNER_NAME","market_value":"MARKET_VALUE","assessed_value":"ASSESSED_VALUE"},"defaults":{"county_state":"Arizona","land_use":"VACANT"},"where":"1=1","verified":False,"html_search_url":"https://www.yavapaiaz.gov/Mapping-and-Properties/GIS-Mapping/GIS-Mapping-Applications","status":"Official Vacant Land layer identified; run probe/field validation before production"},
    "washoe_nv": {"name":"Washoe County, NV","data_mode":"arcgis","arcgis_layer_url":"https://gisenterprise.washoecounty.gov/server/rest/services/WashoeGIS/Parcels/FeatureServer/0","arcgis_root":"https://gisenterprise.washoecounty.gov/server/rest/services/WashoeGIS/Parcels/FeatureServer/0","fields":{"apn":"APN","lot_size_acres":"ACREGIS","zoning":"ZONING","land_use":"FCODE","address":["SITENUMBER","SITESTREET","SITECITY","ZIPCODE"]},"defaults":{"county_state":"Nevada"},"where":"FCODE = 1","verified":False,"html_search_url":"https://www.washoecounty.gov/assessor/","status":"Official WashoeGIS parcel FeatureServer; field validation required before production"},
    "pinal_az": {"name":"Pinal County, AZ","data_mode":"arcgis","arcgis_layer_url":"https://rogue.casagrandeaz.gov/arcgis/rest/services/Pinal_County/Pinal_County_Parcels/FeatureServer/0","arcgis_root":"https://rogue.casagrandeaz.gov/arcgis/rest/services/Pinal_County/Pinal_County_Parcels/FeatureServer/0","fields":{"apn":"APN","address":"SITE_ADDRESS","lot_size_acres":"ACRES","owner_name":"OWNER_NAME","market_value":"MARKET_VALUE","assessed_value":"ASSESSED_VALUE"},"defaults":{"county_state":"Arizona"},"where":"1=1","verified":False,"html_search_url":"https://www.pinal.gov/assessor","status":"Public Pinal County parcel service; source is suitable for discovery, field validation required before production"},
}

def probe_county(county_id: str) -> List[ProbeResult]:
    cfg = COUNTY_SCRAPERS.get(county_id)
    if not cfg: return [ProbeResult(county_id,"registry","",False,0,"unknown county")]
    results: List[ProbeResult] = []
    root = cfg.get("arcgis_root")
    if root:
        if "opendata.arcgis.com" in root:
            layer = arcgis.find_layer_via_hub(root,["parcel","ownership"])
            results.append(ProbeResult(county_id,"arcgis-hub-dcat",f"{root}/api/feed/dcat-us/1.1.json",bool(layer),200 if layer else 404,layer or "no parcel layer found in DCAT feed",verified=bool(layer),extras={"layer":layer or ""}))
        else:
            url = root + ("?f=json" if "/FeatureServer/" in root else "/arcgis/rest/services?f=json")
            r = probe(url,county_id,"arcgis-layer" if "/FeatureServer/" in root else "arcgis-root",expect="arcgis")
            results.append(r)
    return results
