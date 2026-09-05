"""DealScan source discovery.

Discovers configured sources, curated statewide portals, and public ArcGIS
parcel layers. Discovery is never treated as verification until extraction
succeeds.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode
from scrapers.base import fetch, probe
from discovery.statewide_sources import statewide_sources_for_state

@dataclass
class SourceCandidate:
    url: str
    source_type: str
    confidence: float
    notes: str = ""

def discover_arcgis_sources(county_cfg: Dict[str, Any]) -> List[SourceCandidate]:
    out=[]; root=county_cfg.get("arcgis_root")
    if root:
        root=root.rstrip("/")
        if "opendata.arcgis.com" in root: out.append(SourceCandidate(f"{root}/api/feed/dcat-us/1.1.json","arcgis_hub",.9,"ArcGIS Hub DCAT feed"))
        elif "/FeatureServer/" in root or "/MapServer/" in root: out.append(SourceCandidate(root,"arcgis_layer",1.0,"Configured ArcGIS layer"))
        else: out.append(SourceCandidate(f"{root}/arcgis/rest/services?f=json","arcgis_rest",.8,"ArcGIS REST services directory"))
    if county_cfg.get("arcgis_layer_url"): out.append(SourceCandidate(county_cfg["arcgis_layer_url"].rstrip("/"),"arcgis_layer",1.0,"Explicit layer URL"))
    return out

def discover_statewide_sources(state: str) -> List[SourceCandidate]:
    """Return curated statewide portals as discovery candidates, never verified sources."""
    return [
        SourceCandidate(
            source.url,
            source.source_type,
            0.85,
            f"{source.name}: statewide discovery hint; county extraction and ETL verification required",
        )
        for source in statewide_sources_for_state(state)
    ]

def enumerate_statewide_counties(state: str) -> List[Dict[str, Any]]:
    """Enumerate county keys exposed directly by a statewide ArcGIS parcel layer.

    This creates discovery candidates only. It does not register a county as
    verified and deliberately returns the raw statewide identifiers so the
    national registry can reconcile them with Census-backed county geography.
    """
    out: List[Dict[str, Any]] = []
    seen = set()
    for source in statewide_sources_for_state(state):
        if source.source_type != "arcgis_layer" or not source.county_fips_field:
            continue
        fields = [source.county_fips_field]
        if source.county_name_field:
            fields.insert(0, source.county_name_field)
        params = {
            "where": "1=1",
            "outFields": ",".join(fields),
            "returnGeometry": "false",
            "returnDistinctValues": "true",
            "orderByFields": source.county_fips_field,
            "f": "json",
        }
        url = source.url.rstrip("/") + "?" + urlencode(params)
        response = fetch(url, ttl=6 * 3600, as_json=True, respect_robots=False)
        if not response.ok or not isinstance(response.body, dict):
            continue
        for feature in response.body.get("features") or []:
            attrs = feature.get("attributes") or {}
            raw_fips = attrs.get(source.county_fips_field)
            if raw_fips in (None, ""):
                continue
            county_fips = str(raw_fips).strip()
            if county_fips.isdigit():
                county_fips = county_fips.zfill(3)
            county_name = attrs.get(source.county_name_field) if source.county_name_field else None
            key = (state.lower(), county_fips)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "state": state,
                "county_fips": county_fips,
                "county_name": str(county_name).strip() if county_name else None,
                "county_key": f"{state}:{county_fips}",
                "source_url": source.url,
                "source_type": source.source_type,
                "discovery_status": "DISCOVERED_NOT_VERIFIED",
                "verified": False,
            })
    return out

def discover_flatfile_sources(county_cfg: Dict[str, Any]) -> List[SourceCandidate]:
    return [SourceCandidate(county_cfg[k],"flatfile",.7,f"Configured {k}") for k in ("parcel_source_url","open_gov_url","data_url") if county_cfg.get(k)]

def discover_sources(county_cfg: Dict[str, Any]) -> List[SourceCandidate]:
    seen=set(); out=[]
    for c in sorted(discover_arcgis_sources(county_cfg)+discover_flatfile_sources(county_cfg),key=lambda x:x.confidence,reverse=True):
        if c.url not in seen: seen.add(c.url); out.append(c)
    return out

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+"," ",s.lower()).strip()

def _pick(fields: List[Dict[str,Any]], patterns: List[str]) -> Optional[str]:
    for p in patterns:
        rx=re.compile(p,re.I)
        for f in fields:
            if rx.search(str(f.get("name") or "")) or rx.search(str(f.get("alias") or "")): return str(f.get("name"))
    return None

def _field_map(meta: Dict[str,Any]) -> Dict[str,str]:
    fields=meta.get("fields") or []
    pairs={
      "apn":[r"(^|_)apn($|_)",r"parcel.?id",r"parcel.?number",r"property.?id",r"prop.?id",r"tax.?pin",r"account.?number",r"account($|_)",r"geo.?id"],
      "address":[r"situs",r"site.?address",r"property.?address",r"street.?address",r"address"],
      "lot_size_acres":[r"acre",r"land.?area",r"lot.?size",r"parcel.?area"],
      "assessed_value":[r"assess.*value",r"assessed",r"assessment"],
      "market_value":[r"market.*value",r"full.?cash",r"appraised.*value",r"tax.?value"],
      "owner_name":[r"owner.*name",r"owner",r"taxpayer"],
      "owner_address":[r"owner.*address",r"mail.*address",r"mailing"],
      "owner_state":[r"owner.*state",r"mail.*state"],
      "tax_amount":[r"tax.*amount",r"taxes"],
      "tax_delinquent_years":[r"delinq",r"delinquent"],
      "year_acquired":[r"sale.?year",r"year.?acq",r"acq.*year"],
      "zoning":[r"zoning",r"zone"],
      "land_use":[r"land.?use",r"use.?code",r"property.?class",r"class.?code"],
      "has_improvements":[r"improvement",r"imprv"],
      "legal_description":[r"legal",r"description"],
      "latitude":[r"latitude",r"lat($|_)"] ,
      "longitude":[r"longitude",r"long($|_)"]}
    return {dest:f for dest,ps in pairs.items() if (f:=_pick(fields,ps))}

def _source_quality(field_map: Dict[str,str], meta: Dict[str,Any]) -> Dict[str,Any]:
    """Classify discovered parcel sources without confusing discovery with verification."""
    required = ("apn",)
    useful = ("address","lot_size_acres","assessed_value","market_value","land_use","zoning","has_improvements")
    id_ok = all(k in field_map for k in required)
    useful_count = sum(k in field_map for k in useful)
    score = (50 if id_ok else 0) + round(50 * useful_count / len(useful))
    if not id_ok and (meta.get("objectIdField") or meta.get("geometryType")):
        score = max(score, 25)
    tier = "strong" if score >= 80 else "usable" if score >= 55 else "partial"
    return {"source_quality":tier,"source_quality_score":score,"useful_field_count":useful_count,"missing_useful_fields":[k for k in useful if k not in field_map]}

def discover_arcgis_county_config(county_id: str, county_name: str, state: str) -> Optional[Dict[str,Any]]:
    """Discover a public ArcGIS parcel layer for one county on demand."""
    county=_norm(county_name.replace(" County","")); st=_norm(state)
    q=f'("{county}" OR "{county_name}") AND (parcel OR parcels) AND ("{state}" OR {st})'
    url="https://www.arcgis.com/sharing/rest/search?f=json&num=100&q="+quote_plus(q)
    r=fetch(url,ttl=6*3600,as_json=True,respect_robots=False)
    if not r.ok or not isinstance(r.body,dict): return None
    ranked=[]
    for item in r.body.get("results") or []:
        typ=str(item.get("type") or "").lower()
        if typ not in ("feature service","map service","feature layer") or not item.get("url"): continue
        title=_norm(str(item.get("title") or "")); desc=_norm(str(item.get("snippet") or "")); score=0
        if county in title: score+=6
        if county in desc: score+=2
        if st in title: score+=3
        if "parcel" in title: score+=4
        if "assessor" in title or "property" in title: score+=1
        parcel_semantics=any(term in f"{title} {desc}" for term in ("parcel","property","assessor","tax parcel","cadastral"))
        if not parcel_semantics: continue
        ranked.append((score,item))
    for score,item in sorted(ranked,key=lambda x:x[0],reverse=True)[:10]:
        root=str(item["url"]).rstrip("/"); meta=fetch(root+"?f=json",ttl=6*3600,as_json=True,respect_robots=False)
        if not meta.ok or not isinstance(meta.body,dict): continue
        candidates=[]
        if meta.body.get("fields"): candidates=[(root,meta.body)]
        else:
            for lyr in meta.body.get("layers") or []:
                name=_norm(str(lyr.get("name") or ""))
                if any(k in name for k in ("parcel","property","tax","assess")):
                    u=f"{root}/{lyr.get('id')}"; lm=fetch(u+"?f=json",ttl=6*3600,as_json=True,respect_robots=False)
                    if lm.ok and isinstance(lm.body,dict): candidates.append((u,lm.body))
        for layer,lm in candidates:
            fm=_field_map(lm); quality=_source_quality(fm,lm)
            if score < 6 or quality["source_quality_score"] < 55: continue
            if "apn" not in fm: continue
            modified=item.get("modified") or lm.get("lastEditDate") or lm.get("editingInfo",{}).get("lastEditDate")
            return {"name":f"{county_name}, {state}","data_mode":"arcgis","arcgis_layer_url":layer,"arcgis_root":root,"fields":fm,"defaults":{"county_state":state},"where":"1=1","verified":False,"discovery_source":"arcgis_online","discovery_score":score,"source_last_modified":modified,"status":"DISCOVERED_NOT_VERIFIED",**quality}
    return None

def probe_county_sources(county_id: str, cfg: Dict[str,Any]) -> List[Dict[str,Any]]:
    results=[]
    for c in discover_sources(cfg):
        try:
            r=probe(c.url,county_id,c.source_type,expect="arcgis" if "arcgis" in c.source_type else "http")
            results.append({"county_id":county_id,"source_type":c.source_type,"url":c.url,"reachable":r.reachable,"status":r.status,"detail":r.detail,"error":r.error,"verified":r.verified,"confidence":c.confidence,"notes":c.notes})
        except Exception as exc:
            results.append({"county_id":county_id,"source_type":c.source_type,"url":c.url,"reachable":False,"status":0,"detail":"","error":str(exc)[:200],"verified":False,"confidence":c.confidence,"notes":c.notes})
    return results