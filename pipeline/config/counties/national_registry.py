"""National county registry with a complete Census-backed geography universe."""
from __future__ import annotations
import json, urllib.parse, urllib.request
from typing import Any, Dict
from .registry import register_county

PILOT_COUNTIES: Dict[str, Dict[str, Any]] = {
    "cochise_az": {"county_name":"Cochise County","state":"Arizona","state_fips":"04","county_fips":"003","geoid":"04003","population":125447,"data_source_type":"arcgis","assessor_url":"https://www.cochise.az.gov/departments/assessor","gis_url":"https://gis-cochise.opendata.arcgis.com","parcel_source_url":"https://gis-cochise.opendata.arcgis.com/datasets/Cad_Parcel_TaxInfo","source_vendor":"esri","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_4","notes":"ArcGIS Hub -> Cad_Parcel_TaxInfo"},
    "mohave_az": {"county_name":"Mohave County","state":"Arizona","state_fips":"04","county_fips":"015","geoid":"04015","population":217853,"data_source_type":"arcgis","assessor_url":"https://www.mohave.gov/departments/assessor","gis_url":"https://az-mohave.opendata.arcgis.com","parcel_source_url":"https://mohave.maps.arcgis.com","source_vendor":"esri","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_4","notes":"ArcGIS Hub -> Mohave MapServer/38"},
    "el_paso_tx": {"county_name":"El Paso County","state":"Texas","state_fips":"48","county_fips":"141","geoid":"48141","population":865424,"data_source_type":"arcgis","assessor_url":"https://www.epcad.org","gis_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","parcel_source_url":"https://services2.arcgis.com/fKvlzLJczghwPYHS/ArcGIS/rest/services/ElPasoCADWebService/FeatureServer/0","source_vendor":"esri","scraper_type":"arcgis","verification_status":"verified","coverage_status":"tier_4","notes":"EPCAD direct ArcGIS FeatureServer"},
}


def discover_national_counties() -> Dict[str, Dict[str, Any]]:
    """Fetch the authoritative Census county-equivalent universe at runtime.

    This makes the registry national rather than a hand-maintained seed list.
    Network failure is non-fatal: existing local entries remain available.
    """
    url="https://api.census.gov/data/2025/acs/acs5?get=NAME&for=county:*&in=state:*"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            rows=json.loads(response.read().decode("utf-8"))
        header, *data=rows; idx={name:i for i,name in enumerate(header)}
        out={}
        for row in data:
            state_fips=row[idx["state"]]; county_fips=row[idx["county"]]
            name=row[idx["NAME"]]; geoid=state_fips+county_fips
            clean=name.replace(" County","",1).strip()
            slug="_".join("".join(ch.lower() if ch.isalnum() else " " for ch in clean).split())
            state_name=_STATE_NAMES.get(state_fips,state_fips)
            cid=f"{slug}_{state_name.lower().replace(' ','_')[:2]}"
            out[cid]={"county_name":name,"state":state_name,"state_fips":state_fips,"county_fips":county_fips,"geoid":geoid,"data_source_type":None,"verification_status":"not_started","coverage_status":"not_covered","notes":"Geography registered from Census; source discovery pending"}
        return out
    except Exception:
        return {}

_STATE_NAMES={"01":"Alabama","02":"Alaska","04":"Arizona","05":"Arkansas","06":"California","08":"Colorado","09":"Connecticut","10":"Delaware","11":"District of Columbia","12":"Florida","13":"Georgia","15":"Hawaii","16":"Idaho","17":"Illinois","18":"Indiana","19":"Iowa","20":"Kansas","21":"Kentucky","22":"Louisiana","23":"Maine","24":"Maryland","25":"Massachusetts","26":"Michigan","27":"Minnesota","28":"Mississippi","29":"Missouri","30":"Montana","31":"Nebraska","32":"Nevada","33":"New Hampshire","34":"New Jersey","35":"New Mexico","36":"New York","37":"North Carolina","38":"North Dakota","39":"Ohio","40":"Oklahoma","41":"Oregon","42":"Pennsylvania","44":"Rhode Island","45":"South Carolina","46":"South Dakota","47":"Tennessee","48":"Texas","49":"Utah","50":"Vermont","51":"Virginia","53":"Washington","54":"West Virginia","55":"Wisconsin","56":"Wyoming"}


def ensure_national_counties()->Dict[str,Dict[str,Any]]:
    """Populate registry with every Census county-equivalent without marking it covered."""
    discovered=discover_national_counties()
    combined=dict(discovered); combined.update(PILOT_COUNTIES)
    for county_id,meta in combined.items():
        register_county(county_id=county_id,county_name=meta["county_name"],state=meta["state"],state_fips=meta["state_fips"],county_fips=meta["county_fips"],geoid=meta["geoid"],population=meta.get("population"),data_source_type=meta.get("data_source_type"),assessor_url=meta.get("assessor_url"),gis_url=meta.get("gis_url"),parcel_source_url=meta.get("parcel_source_url"),source_vendor=meta.get("source_vendor"),scraper_type=meta.get("scraper_type"),verification_status=meta.get("verification_status","not_started"),coverage_status=meta.get("coverage_status","not_covered"),notes=meta.get("notes",""))
    return combined

def ensure_pilot_counties():
    for county_id,meta in PILOT_COUNTIES.items():
        register_county(county_id=county_id,county_name=meta["county_name"],state=meta["state"],state_fips=meta["state_fips"],county_fips=meta["county_fips"],geoid=meta["geoid"],population=meta.get("population"),data_source_type=meta.get("data_source_type"),assessor_url=meta.get("assessor_url"),gis_url=meta.get("gis_url"),parcel_source_url=meta.get("parcel_source_url"),source_vendor=meta.get("source_vendor"),scraper_type=meta.get("scraper_type"),verification_status=meta.get("verification_status","not_started"),coverage_status=meta.get("coverage_status","tier_0"),notes=meta.get("notes",""))
