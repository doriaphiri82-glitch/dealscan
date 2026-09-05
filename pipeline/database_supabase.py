"""Supabase persistence adapter for DealScan using PostgREST."""
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import requests

class SupabaseDatabase:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None) -> None:
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.url or not self.key:
            raise RuntimeError("Supabase backend requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        self.base = f"{self.url}/rest/v1"
        self.headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        self.timeout = float(os.getenv("SUPABASE_DB_TIMEOUT", "30"))

    def _request(self, method: str, table: str, **kwargs: Any) -> requests.Response:
        headers = kwargs.pop("headers", None) or self.headers
        response = requests.request(method, f"{self.base}/{table}", headers=headers, timeout=self.timeout, **kwargs)
        if not response.ok:
            raise RuntimeError(f"Supabase {method} {table} failed ({response.status_code}): {response.text[:1000]}")
        return response

    def record_ingestion_run(self, county_id: str, status: str, counts: Dict[str, Any], error: str = "", source_url: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> int:
        status_map = {"ok": "completed", "degraded": "partial", "error": "failed", "skipped": "partial"}
        payload = {
            "county_id": county_id,
            "run_type": "scheduled" if os.getenv("GITHUB_ACTIONS") else "manual",
            "status": status_map.get(status, "failed"),
            "source_url": source_url,
            "records_seen": int(counts.get("discovered", 0) or 0),
            "records_normalized": int(counts.get("normalized", 0) or 0),
            "records_persisted": int(counts.get("stored", 0) or 0),
            "records_rejected": int(counts.get("rejected", 0) or 0),
            "error_message": error or None,
            "metadata": metadata or {},
        }
        rows = self._request("POST", "ingestion_runs", headers={**self.headers, "Prefer": "return=representation"}, json=payload).json()
        if not rows:
            raise RuntimeError("Supabase ingestion run insert returned no row")
        return int(rows[0]["id"])

    def record_ingestion_records(self, run_id: int, county_id: str, records: List[Dict[str, Any]]) -> int:
        """Persist compact per-record provenance/audit rows in bounded batches."""
        if not records:
            return 0
        inserted = 0
        for start in range(0, len(records), 250):
            batch = []
            for item in records[start:start + 250]:
                raw = item.get("raw_payload")
                normalized = item.get("normalized_payload") or {}
                batch.append({
                    "run_id": int(run_id),
                    "county_id": county_id,
                    "source_record_id": str(item.get("source_record_id") or normalized.get("apn") or "")[:500] or None,
                    "source_url": item.get("source_url"),
                    "raw_payload": raw if isinstance(raw, dict) else {"value": str(raw)[:5000]} if raw is not None else {},
                    "normalized_payload": normalized if isinstance(normalized, dict) else {},
                    "property_id": int(item["property_id"]) if item.get("property_id") is not None else None,
                    "status": str(item.get("status") or "normalized")[:100],
                    "rejection_reason": str(item.get("rejection_reason") or "")[:500] or None,
                })
            self._request("POST", "ingestion_records", json=batch)
            inserted += len(batch)
        return inserted

    def upsert_county(self, county: Dict[str, Any]) -> None:
        county_id = str(county.get("county_id") or "").strip()
        county_name = str(county.get("county_name") or "").strip()
        if not county_id or not county_name:
            raise ValueError("county metadata requires county_id and county_name")
        known = {"county_id","state","state_fips","county_fips","county_name","coverage_status","data_source_type","gis_url","parcel_source_url","arcgis_layer_url","source_vendor","scraper_type","field_mapping","verification_status","validation_status","data_freshness","discovery_attempted_at","last_successful_run","last_run_status","last_run_error","record_count","qualified_count","published_count","persisted_count","notes","extra"}
        payload = {k: county.get(k) for k in known if county.get(k) is not None}
        payload["county_id"] = county_id
        payload["county_name"] = county_name
        payload["field_mapping"] = county.get("field_mapping") or {}
        payload["extra"] = {k: v for k, v in county.items() if k not in known}
        self._request("POST", "counties", params={"on_conflict": "county_id"}, headers={**self.headers, "Prefer": "resolution=merge-duplicates"}, json=payload)

    def ensure_county(self, county: Dict[str, Any]) -> None:
        county_id = str(county.get("county_id") or "").strip()
        if not county_id:
            raise ValueError("county metadata requires county_id")
        rows = self._request("GET", "counties", params={"county_id": f"eq.{county_id}", "select": "county_id"}).json()
        if not rows:
            self.upsert_county(county)

    def save_property(self, data: Dict[str, Any]) -> int:
        county = data.get("_county_metadata")
        if county:
            self.upsert_county(county)
        else:
            self.ensure_county({"county_id": data["county_id"], "county_name": data.get("county_name")})
        payload = {"apn": data["apn"], "county_id": data["county_id"], "address": data.get("address"), "lot_size_acres": data.get("lot_size_acres"), "assessed_value": data.get("assessed_value"), "market_value": data.get("market_value"), "owner_name": data.get("owner_name"), "owner_address": data.get("owner_address"), "owner_state": data.get("owner_state"), "tax_amount": data.get("tax_amount"), "tax_delinquent_years": data.get("tax_delinquent_years", 0), "year_acquired": data.get("year_acquired"), "zoning": data.get("zoning"), "land_use": data.get("land_use"), "has_improvements": bool(data.get("has_improvements", False)), "legal_description": data.get("legal_description"), "latitude": data.get("latitude"), "longitude": data.get("longitude")}
        rows = self._request("POST", "properties", params={"on_conflict": "apn,county_id"}, headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}, json=payload).json()
        if not rows: raise RuntimeError("Supabase property upsert returned no row")
        return int(rows[0]["id"])

    def save_deal(self, data: Dict[str, Any]) -> int:
        pid = int(data["property_id"])
        existing = self._request("GET", "deals", params={"property_id": f"eq.{pid}", "select": "id", "order": "id.desc", "limit": "1"}).json()
        fields = ["deal_score","asking_price","estimated_arv_low","estimated_arv_high","estimated_costs","estimated_profit_low","estimated_profit_high","recommended_offer_low","recommended_offer_high","motivation_signals","motivation_score","market_velocity","competition_level","status","notes","source","source_url","source_vendor","source_quality","verification_status","data_freshness","valuation_basis","valuation_confidence"]
        payload = {k: data.get(k) for k in fields}
        if payload.get("verification_status") == "source_verified": payload["verification_status"] = "verified"
        if existing:
            did = int(existing[0]["id"]); self._request("PATCH", "deals", params={"id": f"eq.{did}"}, json=payload); return did
        payload["property_id"] = pid
        rows = self._request("POST", "deals", headers={**self.headers, "Prefer": "return=representation"}, json=payload).json()
        if not rows: raise RuntimeError("Supabase deal insert returned no row")
        return int(rows[0]["id"])

    def save_comps(self, deal_id: int, comps: List[dict]) -> int:
        self._request("DELETE", "comps", params={"deal_id": f"eq.{int(deal_id)}"})
        valid = []
        for comp in comps or []:
            try: valid.append({"deal_id": int(deal_id), "address": comp.get("address"), "sale_price": float(comp["sale_price"]), "sale_date": comp.get("sale_date"), "distance_miles": float(comp["distance_miles"]), "lot_size_acres": float(comp["lot_size_acres"]), "price_per_acre": float(comp["price_per_acre"])})
            except (KeyError, TypeError, ValueError): continue
        if valid: self._request("POST", "comps", json=valid)
        return len(valid)

    def get_deal_comps(self, deal_id: int) -> List[dict]:
        return self._request("GET", "comps", params={"deal_id": f"eq.{int(deal_id)}", "select": "address,sale_price,sale_date,distance_miles,lot_size_acres,price_per_acre", "order": "distance_miles.asc"}).json()

    def get_top_deals(self, limit: int = 10, min_score: int = 40, county_id: Optional[str] = None) -> List[dict]:
        params = {"status": "eq.discovered", "verification_status": "eq.verified", "deal_score": f"gte.{int(min_score)}", "select": "*,properties!inner(apn,county_id,address,lot_size_acres,owner_name,owner_state,tax_delinquent_years,zoning)", "order": "deal_score.desc", "limit": str(int(limit))}
        if county_id: params["properties.county_id"] = f"eq.{county_id}"
        rows = self._request("GET", "deals", params=params).json(); out = []
        for row in rows:
            prop = row.pop("properties", {}) or {}; row.update({k: prop.get(k) for k in ("apn","county_id","address","lot_size_acres","owner_name","owner_state","tax_delinquent_years","zoning")}); out.append(row)
        return out

    def get_subscribers(self, tier: Optional[str] = None) -> List[dict]:
        params = {"is_active": "eq.true", "select": "*"}
        if tier: params["tier"] = f"eq.{tier}"
        return self._request("GET", "subscribers", params=params).json()

    def add_waitlist_entry(self, email: str, source: str = "unknown") -> None:
        self._request("POST", "waitlist", headers={**self.headers, "Prefer": "resolution=ignore-duplicates"}, json={"email": email, "source": source})
