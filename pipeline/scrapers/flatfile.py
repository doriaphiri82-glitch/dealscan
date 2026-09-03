"""
DealScan - Flat-file scraper for county bulk data exports.

Currently targets El Paso CAD (EPCAD) Open Government CAMA flat files:
  * https://epcad.org/OpenGovernment
  * Delimited flat files (.txt): Properties, Owners, Lands, Values, Deeds
  * Row delimiter: newline; Column delimiter: ~
  * Published specifically "for development use"

Usage is explicitly permitted by EPCAD.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scrapers.base import fetch

EPCAD_FIELD_MAP = {
    "apn": ("ACCOUNT", "ACCOUNTNO", "ACCT", "PARCEL", "ACCOUNT#"),
    "address": ("SITUSADDRESS", "SITUS_ADDR", "LOCADDRESS", "SITEADDRESS"),
    "lot_size_acres": ("ACREAGE", "ACRES", "LANDACRES"),
    "assessed_value": ("ASSESSEDVALUE", "ASSESSED_VALUE", "ASSESSVAL"),
    "market_value": ("TOTALVALUE", "MARKETVALUE", "MARKET_VALUE", "APPRVALUE"),
    "owner_name": ("OWNERNAME", "OWNER_NAME", "OWNER1"),
    "owner_address": ("OWNERMAILADDR", "OWNERADDRESS", "MAILADDR"),
    "owner_state": ("OWNERSTATE", "OWNER_STATE", "MAILSTATE"),
    "tax_amount": ("TAXAMOUNT", "TAX_AMT", "TAXES"),
    "land_use": ("LANDUSE", "LAND_USE", "PROPERTY_TYPE"),
    "zoning": ("ZONING", "ZONE"),
    "legal_description": ("LEGALDESC", "LEGAL_DESC", "LEGENDESC"),
    "latitude": ("LATITUDE", "LAT"),
    "longitude": ("LONGITUDE", "LON", "LNG"),
    "last_sale_price": ("SALEPRICE", "SALE_PRICE", "LASTSALEPRICE"),
    "last_sale_date": ("SALEDATE", "SALE_DATE", "LASTSALEDATE"),
    "total_sqft": ("TOTALSQFT", "TOTALAREA", "SQUARE_FOOTAGE"),
    "year_built": ("YEARBUILT", "YEAR_BUILT"),
}


def _pick(row: Dict[str, Any], aliases: tuple, default: Any = None) -> Any:
    for a in aliases:
        if a in row and row[a] is not None and str(row[a]).strip() != "":
            return row[a]
    return default


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("$", "").strip('"')
    if s in ("", "0", "-", "N/A"):
        return None
    if "sqft" in s.lower():
        try:
            return float(s.lower().replace("sqft", "").strip()) / 43560.0
        except ValueError:
            return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_flat_file(text: str) -> List[Dict[str, Any]]:
    """Parse a '~'-delimited flat file with a header row into dicts."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    rows: List[Dict[str, Any]] = []
    first = [c.strip() for c in lines[0].split("~")]
    has_header = any(any(ch.isalpha() for ch in cell) for cell in first) and len(
        first) > 3
    start = 1 if has_header else 0
    headers = first if has_header else [f"col{i}" for i in range(len(first))]
    for ln in lines[start:]:
        cells = [c.strip() for c in ln.split("~")]
        while len(cells) < len(headers):
            cells.append("")
        rows.append(dict(zip(headers, cells[: len(headers)])))
    return rows


def map_epcad_property(raw: Dict[str, Any], county_id: str,
                       defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Map an EPCAD CAMA row to the pipeline Property shape."""
    prop = {
        "apn": _pick(raw, EPCAD_FIELD_MAP["apn"]),
        "address": _pick(raw, EPCAD_FIELD_MAP["address"]),
        "lot_size_acres": _to_float(_pick(raw, EPCAD_FIELD_MAP["lot_size_acres"])),
        "assessed_value": _to_float(_pick(raw, EPCAD_FIELD_MAP["assessed_value"])),
        "market_value": _to_float(_pick(raw, EPCAD_FIELD_MAP["market_value"])),
        "owner_name": _pick(raw, EPCAD_FIELD_MAP["owner_name"]),
        "owner_address": _pick(raw, EPCAD_FIELD_MAP["owner_address"]),
        "owner_state": _pick(raw, EPCAD_FIELD_MAP["owner_state"]),
        "tax_amount": _to_float(_pick(raw, EPCAD_FIELD_MAP["tax_amount"])),
        "land_use": _pick(raw, EPCAD_FIELD_MAP["land_use"]),
        "zoning": _pick(raw, EPCAD_FIELD_MAP["zoning"]),
        "legal_description": _pick(raw, EPCAD_FIELD_MAP["legal_description"]),
        "latitude": _to_float(_pick(raw, EPCAD_FIELD_MAP["latitude"])),
        "longitude": _to_float(_pick(raw, EPCAD_FIELD_MAP["longitude"])),
        "last_sale_price": _to_float(_pick(raw, EPCAD_FIELD_MAP["last_sale_price"])),
        "last_sale_date": _pick(raw, EPCAD_FIELD_MAP["last_sale_date"]),
        "year_acquired": 0,
        "tax_delinquent_years": 0,
        "has_improvements": False,
        "county_id": county_id,
        **defaults,
    }
    return prop


def discover_downloads(open_gov_url: str) -> Dict[str, str]:
    """Fetch the OpenGovernment page and collect flat-file download URLs."""
    r = fetch(open_gov_url, ttl=24 * 3600)
    if not r.ok or not isinstance(r.body, str):
        return {}
    import re
    from urllib.parse import urljoin
    links: Dict[str, str] = {}
    for m in re.finditer(r'href=["\']([^"\']+)["\']', r.body):
        raw = m.group(1)
        low = raw.lower()
        if not any(ext in low for ext in (".txt", ".zip", ".csv")):
            continue
        url = urljoin(open_gov_url, raw)
        for key in ("properties", "owners", "lands", "values", "deeds",
                    "schema"):
            if key in low:
                links.setdefault(key, url)
                break
    return links


def discover_links_sample(open_gov_url: str, limit: int = 15) -> List[str]:
    """Diagnostic: return sample hrefs from the page (probe debugging)."""
    r = fetch(open_gov_url, ttl=24 * 3600)
    if not r.ok or not isinstance(r.body, str):
        return []
    import re
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', r.body)
    return [h[:120] for h in hrefs[:limit]]


def fetch_el_paso_properties(county_id: str = "el_paso_tx",
                             max_records: int = 50000) -> List[Dict[str, Any]]:
    """Download and parse EPCAD Properties; return normalized Property dicts."""
    open_gov = "https://epcad.org/OpenGovernment"
    downloads = discover_downloads(open_gov)
    print(f"[debug] epcad downloads: {downloads}")
    props_url = downloads.get("properties")
    if not props_url:
        return []
    r = fetch(props_url, ttl=7 * 24 * 3600, raw=True)  # cache data 7 days
    print(f"[debug] epcad properties fetch ok={r.ok} status={r.status} "
          f"error={r.error[:80] if r.error else ''}")
    if not r.ok or not isinstance(r.body, bytes):
        return []
    # The dump is a ZIP archive containing a ~-delimited .txt file
    import io
    import zipfile
    text: str = ""
    try:
        with zipfile.ZipFile(io.BytesIO(r.body)) as zf:
            member = next((n for n in zf.namelist()
                           if n.lower().endswith((".txt", ".csv"))), None)
            if member is None:
                print(f"[debug] epcad zip members: {zf.namelist()[:10]}")
                return []
            raw_bytes = zf.read(member)
            text = raw_bytes.decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        text = r.body.decode("utf-8", errors="replace")
    # The Properties file has NO header row; EPCAD publishes a Schema
    # Summary documenting the column order. Fetch + log it for mapping.
    schema_url = downloads.get("schema")
    if schema_url:
        sr = fetch(schema_url, ttl=7 * 24 * 3600, raw=True)
        if sr.ok and isinstance(sr.body, bytes):
            stext = sr.body.decode("utf-8", errors="replace")
            # Print the complete [Properties] section (column order)
            lines = stext.splitlines()
            try:
                start = next(i for i, ln in enumerate(lines)
                             if ln.strip().lower() == "[properties]")
                end = next((i for i in range(start + 1, len(lines))
                            if lines[i].strip().startswith("[")), len(lines))
                print(f"[debug] epcad [Properties] schema: "
                      f"{end - start - 1} columns")
                for ln in lines[start + 1:end]:
                    if ln.strip():
                        print(f"[debug] epcad schema| {ln.strip()[:120]}")
            except StopIteration:
                print(f"[debug] epcad: no [Properties] section in schema")
        else:
            print(f"[debug] epcad schema fetch failed: "
                  f"ok={sr.ok} err={sr.error[:80] if sr.error else ''}")
    raw_lines = text.splitlines()
    print(f"[debug] epcad first lines (no header expected):")
    for ln in raw_lines[:2]:
        cells = ln.split("~")
        print(f"[debug] epcad line: {len(cells)} cells | {cells[:14]}")
    rows = parse_flat_file(text)
    print(f"[debug] epcad parsed {len(rows)} rows; "
          f"headers sample: {list(rows[0].keys())[:20] if rows else 'none'}")
    out = []
    for row in rows:
        prop = map_epcad_property(row, county_id, {"county_state": "Texas"})
        if prop.get("apn"):
            out.append(prop)
        if len(out) >= max_records:
            break
    return out