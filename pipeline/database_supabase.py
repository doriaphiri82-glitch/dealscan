"""Supabase persistence adapter for DealScan.

Uses PostgREST over HTTPS so the pipeline does not require an additional SDK.
Enabled only when DEALSCAN_DB_BACKEND=supabase and service-role credentials exist.
"""
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
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        self.timeout = float(os.getenv("SUPABASE_DB_TIMEOUT", "30"))

    def _request(self, method: str, table: str, **kwargs: Any) -> requests.Response:
        response = requests.request(method, f"{self.base}/{table}", headers=self.headers, timeout=self.timeout, **kwargs)
        if not response.ok:
            detail = response.text[:1000]
            raise RuntimeError(f"Supabase {method} {table} failed ({response.status_code}): {detail}")
        return response

    def _ensure_county(self, county_id: str) -> None:
        rows = self._request("GET", "counties", params={"county_id": f"eq.{county_id}", "select": "county_id"}).json()
        if rows:
            return
        # This is only a referential placeholder. Statewide discovery should subsequently
        # reconcile the complete county metadata into this row.
        self._request("POST", "counties", json={"county_id": county_id, "county_name": county_id})

    def save_property(self, data: Dict[str, Any]) -> int:
        county_id = data["county_id"]
        self._ensure_county(county_id)
        payload = {
            "apn": data["apn"], "county_id": county_id, "address": data.get("address"),
            "lot_size_acres": data.get("lot_size_acres"), "assessed_value": data.get("assessed_value"),
            "market_value": data.get("market_value"), "owner_name": data.get("owner_name"),
            "owner_address": data.get("owner_address"), "owner_state": data.get("owner_state"),
            "tax_amount": data.get("tax_amount"), "tax_delinquent_years": data.get("tax_delinquent_years", 0),
            "year_acquired": data.get("year_acquired"), "zoning": data.get("zoning"),
            "land_use": data.get("land_use"), "has_improvements": bool(data.get("has_improvements", False)),
            "legal_description": data.get("legal_description"), "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
        rows = self._request("POST", "properties", params={"on_conflict": "apn,county_id"},
                             headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"},
                             json=payload).json()
        if not rows:
            raise RuntimeError("Supabase property upsert returned no row")
        return int(rows[0]["id"])

    def save_deal(self, data: Dict[str, Any]) -> int:
        pid = int(data["property_id"])
        existing = self._request("GET", "deals", params={"property_id": f"eq.{pid}", "select": "id", "order": "id.desc", "limit": "1"}).json()
        fields = ["deal_score", "asking_price", "estimated_arv_low", "estimated_arv_high", "estimated_costs",
                  "estimated_profit_low", "estimated_profit_high", "recommended_offer_low", "recommended_offer_high",
                  "motivation_signals", "motivation_score", "market_velocity", "competition_level", "status", "notes",
                  "source", "source_url", "source_vendor", "source_quality", "verification_status", "data_freshness",
                  "valuation_basis", "valuation_confidence"]
        payload = {k: data.get(k) for k in fields}
        payload["motivation_signals"] = data.get("motivation_signals", "")
        if existing:
            did = int(existing[0]["id"])
            self._request("PATCH", "deals", params={"id": f"eq.{did}"}, json=payload)
            return did
        payload["property_id"] = pid
        rows = self._request("POST", "deals", headers={**self.headers, "Prefer": "return=representation"}, json=payload).json()
        return int(rows[0]["id"])

    def save_comps(self, deal_id: int, comps: List[dict]) -> int:
        self._request("DELETE", "comps", params={"deal_id": f"eq.{int(deal_id)}"})
        valid = []
        for comp in comps or []:
            try:
                valid.append({"deal_id": int(deal_id), "address": comp.get("address"), "sale_price": float(comp["sale_price"]),
                              "sale_date": comp.get("sale_date"), "distance_miles": float(comp["distance_miles"]),
                              "lot_size_acres": float(comp["lot_size_acres"]), "price_per_acre": float(comp["price_per_acre"])})
            except (KeyError, TypeError, ValueError):
                continue
        if valid:
            self._request("POST", "comps", json=valid)
        return len(valid)

    def get_deal_comps(self, deal_id: int) -> List[dict]:
        return self._request("GET", "comps", params={"deal_id": f"eq.{int(deal_id)}", "select": "address,sale_price,sale_date,distance_miles,lot_size_acres,price_per_acre", "order": "distance_miles.asc"}).json()

    def get_top_deals(self, limit: int = 10, min_score: int = 40, county_id: Optional[str] = None) -> List[dict]:
        # The embedded property relation keeps the response compatible with SQLite callers.
        params = {"status": "eq.discovered", "deal_score": f"gte.{int(min_score)}", "select": "*,properties!inner(apn,county_id,address,lot_size_acres,owner_name,owner_state,tax_delinquent_years,zoning)", "order": "deal_score.desc", "limit": str(int(limit))}
        if county_id:
            params["properties.county_id"] = f"eq.{county_id}"
        rows = self._request("GET", "deals", params=params).json()
        out = []
        for row in rows:
            prop = row.pop("properties", {}) or {}
            row.update({k: prop.get(k) for k in ("apn", "county_id", "address", "lot_size_acres", "owner_name", "owner_state", "tax_delinquent_years", "zoning")})
            out.append(row)
        return out

    def get_subscribers(self, tier: Optional[str] = None) -> List[dict]:
        params = {"is_active": "eq.true", "select": "*"}
        if tier:
            params["tier"] = f"eq.{tier}"
        return self._request("GET", "subscribers", params=params).json()

    def add_waitlist_entry(self, email: str, source: str = "unknown") -> None:
        self._request("POST", "waitlist", headers={**self.headers, "Prefer": "resolution=ignore-duplicates"}, json={"email": email, "source": source})
