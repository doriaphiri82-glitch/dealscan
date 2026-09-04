"""National county registry with a Census-backed geography universe."""
from __future__ import annotations
import json, urllib.request
from typing import Any, Dict
from .registry import register_county, get_county

PILOT_COUNTIES: Dict[str, Dict[str, Any]] = {
    "cochise_az": {"county_name":"Cochise County","state":"Arizona","state_fips":"04","county_fips":"003","geoid":"04003","population":125447,"data_source_type":"arcgis","assessor_url":"https://www.cochise.az.gov/departments/assessor","gis_url":"https://gis-cochise.opendata.arcgis.com","parcel_source_url":"https://gis-cochise.opendata.arcgis.com/datasets/Cad_Parcel_TaxInfo","source_vendor":"esri","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_4","notes":"ArcGIS Hub -> Cad_Parcel_TaxInfo"},
    "mohave_az": {"county_name":"Mohave County","state":"Arizona","state_fips":"04","county_fips":"015","geoid":"04015","population":217853,"data_source_type":"arcgis","assessor_url":"https://www.mohave.gov/departments/assessor","gis_url":"https://az-mohave.opendata.arcgis.com","parcel_source_url":"https://mohave.maps.arcgis.com","source_vendor":"esri","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_4","notes":"ArcGIS Hub -> Mohave MapServer/38"},
    "el_paso_tx": {"county_name":"El Paso County","state":"Texas","state_fips":"48","county_fips":"141","geoid":"48141","population":865424,"data_source_type":"arcgis","assessor_url":"https://www.epcad.org","gis_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","parcel_source_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","source_vendor":"esri","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_4","notes":"EPCAD direct ArcGIS FeatureServer"},
    "yavapai_az": {"county_name":"Yavapai County","state":"Arizona","state_fips":"04","county_fips":"025","geoid":"04025","data_source_type":"arcgis","assessor_url":"https://www.yavapaiaz.gov/Mapping-and-Properties","gis_url":"https://gis.yavapaiaz.gov/arcgis/rest/services/Property/FeatureServer","parcel_source_url":"https://gis.yavapaiaz.gov/arcgis/rest/services/Property/FeatureServer/10","source_vendor":"yavapai_county","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_2","notes":"Official Yavapai County Property FeatureServer; Vacant Land layer identified, field validation pending"},
    "washoe_nv": {"county_name":"Washoe County","state":"Nevada","state_fips":"32","county_fips":"031","geoid":"32031","data_source_type":"arcgis","assessor_url":"https://www.washoecounty.gov/assessor/","gis_url":"https://gisenterprise.washoecounty.gov/server/rest/services/WashoeGIS/Parcels/FeatureServer","parcel_source_url":"https://gisenterprise.washoecounty.gov/server/rest/services/WashoeGIS/Parcels/FeatureServer/0","source_vendor":"washoe_county","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_2","notes":"Official WashoeGIS parcel FeatureServer with assessor attributes; field validation pending"},
    "pinal_az": {"county_name":"Pinal County","state":"Arizona","state_fips":"04","county_fips":"021","geoid":"04021","data_source_type":"arcgis","assessor_url":"https://www.pinal.gov/assessor","gis_url":"https://rogue.casagrandeaz.gov/arcgis/rest/services/Pinal_County/Pinal_County_Parcels/FeatureServer","parcel_source_url":"https://rogue.casagrandeaz.gov/arcgis/rest/services/Pinal_County/Pinal_County_Parcels/FeatureServer/0","source_vendor":"casa_grande_gis","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_2","notes":"Public Pinal County parcel service published by Casa Grande GIS; field validation pending"},
}

_STATE_NAMES={"01":"Alabama","02":"Alaska","04":"Arizona","05":"Arkansas","06":"California","08":"Colorado","09":"Connecticut","10":"Delaware","11":"District of Columbia","12":"Florida","13":"Georgia","15":"Hawaii","16":"Idaho","17":"Illinois","18":"Indiana","19":"Iowa","20":"Kansas","21":"Kentucky","22":"Louisiana","23":"Maine","24":"Maryland","25":"Massachusetts","26":"Michigan","27":"Minnesota","28":"Mississippi","29":"Missouri","30":"Montana","31":"Nebraska","32":"Nevada","33":"New Hampshire","34":"New Jersey","35":"New Mexico","36":"New York","37":"North Carolina","38":"North Dakota","39":"Ohio","40":"Oklahoma","41":"Oregon","42":"Pennsylvania","44":"Rhode Island","45":"South Carolina","46":"South Dakota","47":"Tennessee","48":"Texas","49":"Utah","50":"Vermont","51":"Virginia","53":"Washington","54":"West Virginia","55":"Wisconsin","56":"Wyoming"}

_PRESERVE_KEYS=(
    "data_source_type","assessor_url","gis_url","parcel_source_url","tax_source_url",
    "delinquent_tax_source_url","zoning_source_url","source_vendor","scraper_type",
    "verification_status","coverage_status","last_successful_run","last_record_count",
    "data_freshness","field_mapping","notes","arcgis_layer_url","discovery_source",
    "discovery_score","source_quality","source_quality_score","useful_field_count",
    "missing_useful_fields","field_count",
)


def discover_national_counties()->Dict[str,Dict[str,Any]]:
    url="https://api.census.gov/data/2025/acs/acs5?get=NAME&for=county:*&in=state:*"
    try:
        with urllib.request.urlopen(url,timeout=30) as response: rows=json.loads(response.read().decode("utf-8"))
        header,*data=rows; idx={name:i for i,name in enumerate(header)}; out={}
        for row in data:
            sf=row[idx["state"]]; cf=row[idx["county"]]; name=row[idx["NAME"]]; geoid=sf+cf; clean=name.replace(" County","",1).strip(); slug="_".join("".join(ch.lower() if ch.isalnum() else " " for ch in clean).split()); state=_STATE_NAMES.get(sf,sf); cid=f"{slug}_{state.lower().replace(' ','_')[:2]}"
            out[cid]={"county_name":name,"state":state,"state_fips":sf,"county_fips":cf,"geoid":geoid,"data_source_type":None,"verification_status":"not_started","coverage_status":"not_covered","notes":"Geography registered from Census; source discovery pending"}
        return out
    except Exception:return {}


def ensure_national_counties()->Dict[str,Dict[str,Any]]:
    """Ensure the Census universe exists without destroying discovered/verified source metadata."""
    discovered=discover_national_counties(); combined=dict(discovered); combined.update(PILOT_COUNTIES)
    for county_id,meta in combined.items():
        existing=get_county(county_id) or {}
        payload=dict(meta)
        if existing:
            for key in _PRESERVE_KEYS:
                if existing.get(key) is not None and existing.get(key) != "":
                    payload[key]=existing[key]
        register_county(county_id=county_id,county_name=payload["county_name"],state=payload["state"],state_fips=payload["state_fips"],county_fips=payload["county_fips"],geoid=payload["geoid"],population=payload.get("population",existing.get("population")),data_source_type=payload.get("data_source_type"),assessor_url=payload.get("assessor_url"),gis_url=payload.get("gis_url"),parcel_source_url=payload.get("parcel_source_url"),tax_source_url=payload.get("tax_source_url"),delinquent_tax_source_url=payload.get("delinquent_tax_source_url"),zoning_source_url=payload.get("zoning_source_url"),source_vendor=payload.get("source_vendor"),scraper_type=payload.get("scraper_type"),verification_status=payload.get("verification_status","not_started"),coverage_status=payload.get("coverage_status","not_covered"),last_successful_run=payload.get("last_successful_run"),last_record_count=payload.get("last_record_count"),data_freshness=payload.get("data_freshness"),field_mapping=payload.get("field_mapping",{}),notes=payload.get("notes","") ,extra={k:payload[k] for k in _PRESERVE_KEYS if k not in {"data_source_type","assessor_url","gis_url","parcel_source_url","tax_source_url","delinquent_tax_source_url","zoning_source_url","source_vendor","scraper_type","verification_status","coverage_status","last_successful_run","last_record_count","data_freshness","field_mapping","notes"} and k in payload})
    return combined


def ensure_pilot_counties():
    for county_id,meta in PILOT_COUNTIES.items():
        register_county(county_id=county_id,county_name=meta["county_name"],state=meta["state"],state_fips=meta["state_fips"],county_fips=meta["county_fips"],geoid=meta["geoid"],population=meta.get("population"),data_source_type=meta.get("data_source_type"),assessor_url=meta.get("assessor_url"),gis_url=meta.get("gis_url"),parcel_source_url=meta.get("parcel_source_url"),source_vendor=meta.get("source_vendor"),scraper_type=meta.get("scraper_type"),verification_status=meta.get("verification_status","not_started"),coverage_status=meta.get("coverage_status","tier_0"),notes=meta.get("notes",""))
