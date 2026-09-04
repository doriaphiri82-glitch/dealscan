"""DealScan - ArcGIS REST adapter."""
from __future__ import annotations
import json,re
from typing import Any,Dict,Iterator,List,Optional
from .base import fetch,post_json,probe,ProbeResult  # noqa: F401

def _to_float(v:Any)->Optional[float]:
    if v in (None,""," "): return None
    try:
        if isinstance(v,str):
            cleaned=v.strip().replace(",","").replace("$","").replace("USD","").strip()
            if cleaned.startswith("(") and cleaned.endswith(")"): cleaned="-"+cleaned[1:-1]
            cleaned=re.sub(r"[^0-9.\-]", "", cleaned)
            if cleaned in ("","-","."): return None
            return float(cleaned)
        return float(v)
    except (TypeError,ValueError): return None

def _to_int(v:Any)->int:
    f=_to_float(v); return int(f) if f is not None else 0

def discover_services(rest_root:str)->Optional[Dict[str,Any]]:
    r=fetch(rest_root.rstrip("/")+"/arcgis/rest/services?f=json",ttl=24*3600,as_json=True,respect_robots=False); return r.body if r.ok and isinstance(r.body,dict) else None

def find_layer(rest_root:str,folder:str,service:str,layer_name_keywords:List[str])->Optional[str]:
    base=rest_root.rstrip("/")+"/arcgis/rest/services"; r=fetch(f"{base}/{folder}/{service}?f=json",ttl=24*3600,as_json=True,respect_robots=False)
    if not r.ok or not isinstance(r.body,dict): return None
    layers=r.body.get("layers") or []
    for lyr in layers:
        if any(k in str(lyr.get("name") or "").lower() for k in layer_name_keywords): return f"{base}/{folder}/{service}/MapServer/{lyr.get('id')}"
    return f"{base}/{folder}/{service}/MapServer/{layers[0].get('id')}" if layers else None

def find_layer_via_hub(hub_root:str,keywords:List[str])->Optional[str]:
    r=fetch(hub_root.rstrip("/")+"/api/feed/dcat-us/1.1.json",ttl=24*3600,as_json=True,respect_robots=False)
    if not r.ok or not isinstance(r.body,dict): return None
    best=None
    for ds in r.body.get("dataset") or []:
        if not any(k in str(ds.get("title") or "").lower() for k in keywords): continue
        for dist in ds.get("distribution") or []:
            for key in ("accessURL","downloadURL"):
                u=str(dist.get(key) or "")
                if "/MapServer/" in u or "/FeatureServer/" in u:
                    cand=u.rstrip("/")
                    if cand.split("/")[-1].isdigit(): return cand
                    best=best or cand
    return best

def layer_fields(layer_url:str)->Optional[List[str]]:
    r=fetch(f"{layer_url}?f=json",ttl=24*3600,as_json=True,respect_robots=False); return [f.get("name") for f in r.body.get("fields") or [] if f.get("name")] if r.ok and isinstance(r.body,dict) else None

def query_layer(layer_url:str,where:str,out_fields:List[str],max_records:int=5000,page_size:int=1000)->Iterator[Dict[str,Any]]:
    offset=0; fields=",".join(out_fields) if out_fields else "*"; target=max(1,int(max_records)); size=max(1,min(int(page_size),target))
    while offset<target:
        count=min(size,target-offset); r=post_json(f"{layer_url}/query",{"where":where,"outFields":fields,"returnGeometry":"false","f":"json","resultOffset":offset,"resultRecordCount":count})
        if not r.ok: raise RuntimeError(f"ArcGIS query request failed: {r.error or 'unknown error'}")
        if not isinstance(r.body,dict): raise RuntimeError("ArcGIS query returned a non-object response")
        if r.body.get("error"): raise RuntimeError(f"ArcGIS query error: {r.body['error']}")
        feats=r.body.get("features") or []
        for feature in feats:
            attrs=feature.get("attributes") or {}
            if attrs: yield attrs
        got=len(feats); more=bool(r.body.get("exceededTransferLimit"))
        if not more:return
        offset += got if got else count

def map_attributes(attrs:Dict[str,Any],field_map:Dict[str,Any],county_id:str,defaults:Dict[str,Any])->Dict[str,Any]:
    def get(src_field:Any)->Any:
        if isinstance(src_field,(list,tuple)):
            values=[get(part) for part in src_field]; values=[str(v).strip() for v in values if v not in (None,"") and str(v).strip()]; return ", ".join(values) if values else None
        if not src_field:return None
        if "." in str(src_field):
            cur:Any=attrs
            for part in str(src_field).split("."):
                if isinstance(cur,dict):cur=cur.get(part)
                else:return None
            return cur
        return attrs.get(src_field)
    out=dict(defaults)
    for pipeline_field,src_field in field_map.items():out[pipeline_field]=get(src_field)
    for key in ("lot_size_acres","assessed_value","market_value","tax_amount","improvement_value","latitude","longitude"):out[key]=_to_float(out.get(key))
    for key in ("tax_delinquent_years","year_acquired"):out[key]=_to_int(out.get(key))
    out["county_id"]=county_id
    return out

VACANT_LAND_USE_CODES={"cochise_az":["0011","9700","0012","0013","0014","0001","0002","0003"],"mohave_az":["0011","9700","VAC","VACANT"],"el_paso_tx":["0011","9700","VAC","VACANT"],"hudson_co":["0011","9700","VAC","VACANT"],"socorro_nm":["0011","9700","VAC","VACANT"]}

def is_vacant_residential(prop:Dict[str,Any],county_id:str)->bool:
    lu=str(prop.get("land_use") or "").strip().lower(); zoning=str(prop.get("zoning") or "").strip().lower(); code=str(prop.get("use_code") or prop.get("land_use") or "").strip().upper(); imp=prop.get("has_improvements"); improvement_value=prop.get("improvement_value"); has_imp=imp is True or imp in (1,"1","Y","YES","Yes","true","True"); no_imp=imp is False or imp==0 or imp in ("0","N","NO","No","NONE","false","False")
    if improvement_value is not None:
        try:
            if float(improvement_value)>0:has_imp=True; no_imp=False
            elif float(improvement_value)==0:no_imp=True
        except (TypeError,ValueError):pass
    if has_imp:return "vacant" in lu or "unimproved" in lu
    if no_imp:
        if "residential" in lu or "res" in zoning or "residential" in zoning:return True
        if "vacant" in lu or "unimproved" in lu:return True
        return code in {str(x).upper() for x in VACANT_LAND_USE_CODES.get(county_id,[])}
    if "vacant" in lu or "unimproved" in lu or "vacant" in zoning:return True
    return code in {str(x).upper() for x in VACANT_LAND_USE_CODES.get(county_id,[])}

def export_snapshot(props:List[Dict[str,Any]],path:str)->str:
    os_dir=path.rsplit("/",1)[0] if "/" in path else "."; import os; os.makedirs(os_dir,exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:json.dump({"count":len(props),"properties":props},f,indent=1)
    return path
