"""
DealScan - Field Mapping System

Provides robust field mapping with:
- Source schema inspection
- Likely field identification
- Canonical schema mapping
- Mapping validation
- Confidence scoring
- Ambiguity rejection
- Manual override support
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Canonical DealScan property fields
CANONICAL_FIELDS = [
    "parcel_id",
    "county",
    "state",
    "county_fips",
    "owner_name",
    "owner_address",
    "property_address",
    "acreage",
    "land_use",
    "zoning",
    "assessed_value",
    "market_value",
    "land_value",
    "improvement_value",
    "tax_amount",
    "delinquent_tax_years",
    "last_sale_price",
    "last_sale_date",
    "year_built",
    "latitude",
    "longitude",
    "legal_description",
    "source_url",
    "source_updated_at",
    "scraped_at",
]

# Common alias patterns for canonical fields
FIELD_ALIASES: Dict[str, List[str]] = {
    "parcel_id": [
        "apn", "parcel_number", "parcel_id", "parcelid", "parcel_no",
        "account_number", "accountno", "acct", "property_id", "propertyid",
        "geoid", "situs_apn", "taxpin", "pin", "pid", "foli"
    ],
    "property_address": [
        "address", "situs_address", "situs_addr", "prop_address",
        "property_address", "location_address", "site_address"
    ],
    "acreage": [
        "acres", "acreage", "land_acres", "total_acres", "lot_size",
        "lot_size_acres", "land_size", "parcel_size", "sq_ft", "sqft",
        "square_feet", "area"
    ],
    "assessed_value": [
        "assessed_value", "limited_value", "appraised_value",
        "assessed_land_value", "assessed_improvement_value", "total_assessed"
    ],
    "market_value": [
        "market_value", "full_cash_value", "fcv", "total_market_value",
        "appraised_market_value", "fair_market_value"
    ],
    "land_value": [
        "land_value", "land_market_value", "assessed_land",
        "land_appraised_value", "lot_value"
    ],
    "improvement_value": [
        "improvement_value", "imprv_value", "building_value",
        "improvement_market_value", "assessed_improvement", "bldg_value"
    ],
    "owner_name": [
        "owner_name", "owner", "owner_name1", "owner_name2",
        "taxpayer_name", "current_owner", "grantee"
    ],
    "owner_address": [
        "owner_address", "mailing_address", "owner_mail_addr",
        "address1", "addr1", "mail_addr", "owner_addr"
    ],
    "tax_amount": [
        "tax_amount", "tax_amt", "taxes", "total_tax",
        "property_tax", "annual_tax", "tax_due"
    ],
    "delinquent_tax_years": [
        "tax_delinquent_years", "delinquent_years", "tax_delinq",
        "delinquent_tax", "years_delinquent"
    ],
    "last_sale_price": [
        "sale_price", "last_sale_price", "saleamount", "deed_amount",
        "consideration", "transfer_amount"
    ],
    "last_sale_date": [
        "sale_date", "last_sale_date", "deed_date", "transfer_date",
        "sale_year", "date_sold", "recorded_date"
    ],
    "year_built": [
        "year_built", "built_year", "construction_year", "yr_built"
    ],
    "latitude": ["latitude", "lat", "ycoord", "y_coord", "lat_deg"],
    "longitude": ["longitude", "lon", "lng", "xcoord", "x_coord", "long_deg"],
    "legal_description": [
        "legal_description", "legal_desc", "legal_text", "description",
        "legal", "full_legal", "plat"
    ],
    "land_use": [
        "land_use", "use_code", "property_type", "land_use_code",
        "use_type", "classification"
    ],
    "zoning": ["zoning", "zone", "zoning_code", "land_use_code"],
}


@dataclass
class FieldMappingResult:
    canonical_field: str
    source_field: Optional[str]
    confidence: float
    method: str
    ambiguous: bool = False
    alternatives: List[str] = field(default_factory=list)
    notes: str = ""


class FieldMapper:
    def __init__(self, aliases: Optional[Dict[str, List[str]]] = None) -> None:
        self.aliases = aliases or FIELD_ALIASES
        self._canonical_to_aliases: Dict[str, List[str]] = {}
        for canonical, alias_list in self.aliases.items():
            self._canonical_to_aliases[canonical] = [
                a.lower() for a in alias_list
            ]

    def inspect_schema(self, fields: List[str]) -> Dict[str, Any]:
        field_names = [f.strip() for f in fields if f and str(f).strip()]
        normalized = {f.lower(): f for f in field_names}
        return {
            "raw_count": len(field_names),
            "field_names": field_names,
            "normalized_lower": list(normalized.keys()),
            "normalized_map": normalized,
        }

    def _score_alias_match(self, source_field: str, canonical: str) -> float:
        sf = source_field.lower().strip()
        aliases = self._canonical_to_aliases.get(canonical, [])
        if sf in aliases:
            return 1.0
        for alias in aliases:
            if alias in sf or sf in alias:
                return 0.85
            if self._levenshtein_ratio(sf, alias) > 0.8:
                return 0.75
        return 0.0

    def _levenshtein_ratio(self, s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0
        d = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        for i in range(len1 + 1):
            d[i][0] = i
        for j in range(len2 + 1):
            d[0][j] = j
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                d[i][j] = min(
                    d[i - 1][j] + 1,
                    d[i][j - 1] + 1,
                    d[i - 1][j - 1] + cost,
                )
        distance = d[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - distance / max_len if max_len > 0 else 0.0

    def map_fields(
        self,
        source_fields: List[str],
        existing_map: Optional[Dict[str, str]] = None,
        min_confidence: float = 0.6,
    ) -> Tuple[Dict[str, str], List[FieldMappingResult]]:
        schema = self.inspect_schema(source_fields)
        normalized_map = schema["normalized_map"]
        mapping: Dict[str, str] = {}
        results: List[FieldMappingResult] = []
        unmapped_source = set(normalized_map.values())

        for canonical in CANONICAL_FIELDS:
            if existing_map and canonical in existing_map:
                mapping[canonical] = existing_map[canonical]
                unmapped_source.discard(existing_map[canonical])
                results.append(FieldMappingResult(
                    canonical_field=canonical,
                    source_field=existing_map[canonical],
                    confidence=1.0,
                    method="manual_override",
                ))
                continue

            candidates = []
            for src_lower, src_original in normalized_map.items():
                score = self._score_alias_match(src_lower, canonical)
                if score >= min_confidence:
                    candidates.append((score, src_original))

            candidates.sort(reverse=True)
            if not candidates:
                results.append(FieldMappingResult(
                    canonical_field=canonical,
                    source_field=None,
                    confidence=0.0,
                    method="not_found",
                ))
                continue

            best_score, best_source = candidates[0]
            alternatives = [c[1] for c in candidates[1:] if c[0] >= min_confidence]
            ambiguous = len(alternatives) > 0 and best_score < 0.95

            if ambiguous and best_score < 0.8:
                results.append(FieldMappingResult(
                    canonical_field=canonical,
                    source_field=None,
                    confidence=best_score,
                    method="ambiguous_rejected",
                    ambiguous=True,
                    alternatives=alternatives,
                    notes=(
                        f"Ambiguous mapping for {canonical}: "
                        f"{best_source} ({best_score:.0%}) vs "
                        f"{', '.join(alternatives[:3])}"
                    ),
                ))
                continue

            mapping[canonical] = best_source
            unmapped_source.discard(best_source)
            results.append(FieldMappingResult(
                canonical_field=canonical,
                source_field=best_source,
                confidence=best_score,
                method="alias_match" if best_score < 1.0 else "exact_match",
                ambiguous=ambiguous,
                alternatives=alternatives,
            ))

        return mapping, results

    def validate_mapping(
        self,
        mapping: Dict[str, str],
        sample_records: List[Dict[str, Any]],
        required_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        required = required_fields or [
            "parcel_id", "property_address", "acreage",
            "market_value", "owner_name"
        ]
        validation: Dict[str, Any] = {
            "valid": True,
            "required_found": [],
            "required_missing": [],
            "field_issues": [],
            "sample_validation": [],
        }

        for field in required:
            if field in mapping and mapping[field]:
                validation["required_found"].append(field)
            else:
                validation["required_missing"].append(field)
                validation["valid"] = False

        for record in sample_records[:5]:
            record_issues = []
            if "parcel_id" in mapping:
                val = record.get(mapping["parcel_id"])
                if not val or str(val).strip() in ("", "0", "-1"):
                    record_issues.append("parcel_id missing or invalid")
            if "acreage" in mapping:
                val = record.get(mapping["acreage"])
                if val is not None and str(val).strip():
                    try:
                        float(str(val).replace(",", "").replace("$", ""))
                    except (TypeError, ValueError):
                        record_issues.append("acreage not numeric")
            if "market_value" in mapping:
                val = record.get(mapping["market_value"])
                if val is not None and str(val).strip():
                    try:
                        float(str(val).replace(",", "").replace("$", ""))
                    except (TypeError, ValueError):
                        record_issues.append("market_value not numeric")
            validation["sample_validation"].append({
                "record": str(record)[:120],
                "issues": record_issues,
                "valid": len(record_issues) == 0,
            })
            if record_issues:
                validation["field_issues"].extend(record_issues)

        if validation["field_issues"]:
            validation["valid"] = False
        return validation

    def export_mapping(self, mapping: Dict[str, str]) -> str:
        return json.dumps(mapping, indent=2)

    def import_mapping(self, json_str: str) -> Dict[str, str]:
        data = json.loads(json_str)
        return {str(k): str(v) for k, v in data.items() if k and v}
