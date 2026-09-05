"""National county registry with a complete Census-backed geography universe."""
from __future__ import annotations
import json, urllib.request
from typing import Any, Dict
from .registry import register_counties_bulk, list_counties

PILOT_COUNTIES: Dict[str, Dict[str, Any]] = {
    "cochise_az": {"county_name":"Cochise County","state":"Arizona","state_fips":"04","county_fips":"003","geoid":"04003","population":125447,"data_source_type":"arcgis","assessor_url":"https://www.cochise.az.gov/departments/assessor","gis_url":"https://gis-cochise.opendata.arcgis.com","parcel_source_url":"https://services6.arcgis.com/Yxem0VOcqSy8T6TE/arcgis/rest/services/Cad_Parcel_TaxInfo/FeatureServer/0","arcgis_layer_url":"https://services6.arcgis.com/Yxem0VOcqSy8T6TE/arcgis/rest/services/Cad_Parcel_TaxInfo/FeatureServer/0","source_vendor":"esri","scraper_type":"arcgis","verification_status":"source_verified","coverage_status":"tier_3","notes":"Official Cochise County Cad_Parcel_TaxInfo FeatureServer; layer updated weekly; ETL run pending"},
    "mohave_az": {"county_name":"Mohave County","state":"Arizona","state_fips":"04","county_fips":"015","geoid":"04015","population":217853,"data_source_type":"arcgis","assessor_url":"https://www.mohave.gov/departments/assessor","gis_url":"https://az-mohave.opendata.arcgis.com","parcel_source_url":"https://mcgis.mohave.gov/arcgis/rest/services/PARCELS/MapServer/14","arcgis_layer_url":"https://mcgis.mohave.gov/arcgis/rest/services/PARCELS/MapServer/14","source_vendor":"esri","scraper_type":"arcgis","verification_status":"source_verified","coverage_status":"tier_3","notes":"Official Mohave County parcel MapServer/14; source fields verified 2026-09-03; ETL run pending"},
    "el_paso_tx": {"county_name":"El Paso County","state":"Texas","state_fips":"48","county_fips":"141","geoid":"48141","population":865424,"data_source_type":"arcgis","assessor_url":"https://www.epcad.org","gis_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","parcel_source_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","arcgis_layer_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","source_vendor":"esri","scraper_type":"arcgis","verification_status":"source_verified","coverage_status":"tier_3","notes":"EPCAD direct ArcGIS FeatureServer; source verified 2026-09-03; ETL run pending"},
}

_STATE_NAMES={"01":"Alabama","02":"Alaska","04":"Arizona","05":"Arkansas","06":"California","08":"Colorado","09":"Connecticut","10":"Delaware","11":"District of Columbia","12":"Florida","13":"Georgia","15":"Hawaii","16":"Idaho","17":"Illinois","18":"Indiana","19":"Iowa","20":"Kansas","21":"Kentucky","22":"Louisiana","23":"Maine","24":"Maryland","25":"Massachusetts","26":"Michigan","27":"Minnesota","28":"Mississippi","29":"Missouri","30":"Montana","31":"Nebraska","32":"Nevada","33":"New Hampshire","34":"New Jersey","35":"New Mexico","36":"New York","37":"North Carolina","38":"North Dakota","39":"Ohio","40":"Oklahoma","41":"Oregon","42":"Pennsylvania","44":"Rhode Island","45":"South Carolina","46":"South Dakota","47":"Tennessee","48":"Texas","49":"Utah","50":"Vermont","51":"Virginia","53":"Washington","54":"West Virginia","55":"Wisconsin","56":"Wyoming"}
_PRESERVE_KEYS=("population","data_source_type","assessor_url","gis_url","parcel_source_url","tax_source_url","delinquent_tax_source_url","zoning_source_url","source_vendor","scraper_type","verification_status","coverage_status","last_successful_run","last_record_count","last_published_count","data_freshness","field_mapping","notes","arcgis_layer_url","discovery_source","discovery_score","source_quality","source_quality_score","useful_field_count","missing_useful_fields","field_count","last_validated_at","validation_status","validation_errors","validation_warnings","validation_source_fields_checked","validation_sample_checked")
_PILOT_AUTHORITATIVE_KEYS=("data_source_type","assessor_url","gis_url","parcel_source_url","tax_source_url","delinquent_tax_source_url","zoning_source_url","source_vendor","scraper_type","verification_status","coverage_status","notes","arcgis_layer_url")


def discover_national_counties()->Dict[str,Dict[str,Any]]:
    url="https://api.census.gov/data/2025/acs/acs5?get=NAME&for=county:*&in=state:*"
    try:
        with urllib.request.urlopen(url,timeout=30) as response: rows=json.loads(response.read().decode())
        header,*data=rows; idx={name:i for i,name in enumerate(header)}; out={}
        for row in data:
            sf=row[idx["state"]]; cf=row[idx["county"]]; name=row[idx["NAME"]]; state=_STATE_NAMES.get(sf,sf); clean=name.replace(" County","",1).strip(); slug="_".join("".join(ch.lower() if ch.isalnum() else " " for ch in clean).split()); out[f"{slug}_{sf}_{cf}"]={"county_name":name,"state":state,"state_fips":sf,"county_fips":cf,"geoid":sf+cf,"data_source_type":None,"verification_status":"not_started","coverage_status":"not_covered","notes":"Geography registered from Census; source discovery pending"}
        return out
    except Exception:return {}


def _merge_existing(meta: Dict[str, Any], existing_entry: Dict[str, Any], *, authoritative_keys: tuple[str, ...]=()) -> Dict[str, Any]:
    payload=dict(meta)
    authoritative=set(authoritative_keys)
    for key in _PRESERVE_KEYS:
        if key in authoritative:
            continue
        if existing_entry.get(key) not in (None,""):
            payload[key]=existing_entry[key]
    return payload


def ensure_national_counties()->Dict[str,Dict[str,Any]]:
    discovered=discover_national_counties()
    existing={c["county_id"]:c for c in list_counties()}
    combined=dict(existing); combined.update(discovered); combined.update(PILOT_COUNTIES)
    payloads=[]
    for cid,meta in combined.items():
        existing_entry=existing.get(cid) or {}
        authoritative=_PILOT_AUTHORITATIVE_KEYS if cid in PILOT_COUNTIES else ()
        payload=_merge_existing(meta,existing_entry,authoritative_keys=authoritative)
        payload["county_id"]=cid
        for key in ("county_name","state","state_fips","county_fips","geoid"):
            if not payload.get(key) and existing_entry.get(key): payload[key]=existing_entry[key]
        payloads.append(payload)
    register_counties_bulk(payloads)
    return combined


def ensure_pilot_counties():
    existing={c["county_id"]:c for c in list_counties()}
    payloads=[]
    for cid,meta in PILOT_COUNTIES.items():
        payload=_merge_existing(dict(meta,county_id=cid),existing.get(cid) or {},authoritative_keys=_PILOT_AUTHORITATIVE_KEYS)
        payloads.append(payload)
    register_counties_bulk(payloads)
