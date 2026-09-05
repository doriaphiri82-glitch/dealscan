"""Source-faithful scalar conversion shared by all adapters and persistence."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any, Optional

NUMERIC_FIELDS = (
    'lot_size_acres', 'assessed_value', 'market_value', 'tax_amount',
    'latitude', 'longitude', 'improvement_value', 'last_sale_price',
    'asking_price', 'estimated_costs',
)
CANONICAL_FIELDS = set(NUMERIC_FIELDS) | {
    'apn', 'address', 'county_id', 'county_state', 'owner_name', 'owner_address',
    'owner_state', 'tax_delinquent_years', 'year_acquired', 'zoning', 'land_use',
    'use_code', 'has_improvements', 'legal_description', 'last_sale_date',
    'source_record_id', 'lot_size_unit', 'sale_qualified', 'vacant_at_sale',
    'asking_price_source_url', 'costs_source_url', 'costs_complete',
    'has_road_access', 'utilities_nearby', 'is_buildable',
}


def number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(str(value).strip().replace(',', '').removeprefix('$'))
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError, OverflowError):
        return None


def boolean(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().casefold()
    if text in {'true', 'yes', 'y', '1'}:
        return True
    if text in {'false', 'no', 'n', '0'}:
        return False
    return None


def integer(value: Any) -> Optional[int]:
    parsed = number(value)
    return int(parsed) if parsed is not None and parsed >= 0 and parsed.is_integer() else None


def sale_date(value: Any) -> Optional[datetime]:
    """Parse complete dates or ArcGIS epoch milliseconds. Never invent a day."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value) or abs(value) < 100_000_000_000:
            return None
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value or '').strip()
    if re.fullmatch(r'-?\d{12,14}', text):
        return sale_date(int(text))
    if len(text) < 8:
        return None
    try:
        result = datetime.fromisoformat(text.replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except ValueError:
        for fmt in ('%m/%d/%Y', '%Y/%m/%d', '%m/%d/%y'):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def source_value(record: dict, source: Any) -> Any:
    if isinstance(source, (list, tuple)):
        values = [source_value(record, item) for item in source]
        values = [str(value).strip() for value in values if value is not None and str(value).strip()]
        return ', '.join(values) if values else None
    current: Any = record
    for part in str(source or '').split('.'):
        if not isinstance(current, dict) or not part:
            return None
        key = next((key for key in current if str(key).casefold() == part.casefold()), None)
        current = current.get(key)
    return current


def source_identity(record: dict, cfg: dict, normalized: dict) -> str | None:
    fields = (cfg.get('object_id_field') or cfg.get('source_object_id_field'),
              'OBJECTID_1', 'OBJECTID', (cfg.get('fields') or {}).get('source_record_id'), 'source_record_id', 'id')
    for field in fields:
        value = source_value(record, field)
        if value not in (None, ''): return str(value)
    return str(normalized['apn']) if normalized.get('apn') else None


def normalize(record: dict, cfg: dict) -> dict:
    mapping = cfg.get('fields') or {}
    # Canonical passthrough supports already-parsed flat files, not arbitrary raw
    # source keys. Full source records live only in the private raw audit payload.
    result = {key: value for key, value in record.items() if key in CANONICAL_FIELDS}
    sources = {}
    for canonical, source in mapping.items():
        result[canonical] = source_value(record, source)
        sources[canonical] = source
    # Defaults are metadata only. A default must not create a financial/vacancy fact.
    defaults = cfg.get('defaults') or {}
    if defaults.get('county_state'):
        result['county_state'] = defaults['county_state']
    result['county_id'] = cfg.get('county_id') or result.get('county_id')
    issues = []
    for key in NUMERIC_FIELDS:
        raw = result.get(key)
        result[key] = number(raw)
        if raw not in (None, '', ' ') and result[key] is None:
            issues.append(f'invalid_{key}')
    acres = result.get('lot_size_acres')
    if acres is not None:
        field = str(mapping.get('lot_size_acres') or 'lot_size_acres').lower()
        unit = str(result.get('lot_size_unit') or cfg.get('acreage_units') or ('acres' if 'acre' in field else '')).strip().lower()
        if unit in {'sf', 'sqft', 'sq ft', 'square feet'}:
            result['lot_size_acres'] = acres / 43560
        elif unit not in {'ac', 'acres', 'acre', 'ac.'}:
            result['lot_size_acres'] = None
            issues.append('unknown_area_units')
        if acres <= 0:
            result['lot_size_acres'] = None
            issues.append('invalid_lot_size_acres')
    for key in ('tax_delinquent_years', 'year_acquired'):
        result[key] = integer(result.get(key))
    year = result.get('year_acquired')
    if year is not None and not 1800 <= year <= datetime.now(timezone.utc).year:
        result['year_acquired'] = None
        issues.append('invalid_year_acquired')
    for key in ('has_improvements', 'sale_qualified', 'vacant_at_sale', 'costs_complete', 'has_road_access', 'utilities_nearby', 'is_buildable'):
        result[key] = boolean(result.get(key))
    improvement = result.get('improvement_value')
    if improvement is not None:
        if improvement < 0:
            result['improvement_value'] = None
            issues.append('invalid_improvement_value')
        elif result.get('has_improvements') is None:
            result['has_improvements'] = improvement > 0
    lat, lon = result.get('latitude'), result.get('longitude')
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        if lat is not None or lon is not None:
            issues.append('invalid_coordinates')
        result['latitude'] = result['longitude'] = None
    if result.get('last_sale_date') is not None:
        parsed = sale_date(result['last_sale_date'])
        # Retain incomplete dates as source text, but they cannot qualify as comps.
        result['last_sale_date'] = parsed.isoformat() if parsed else str(result['last_sale_date'])
    if result.get('apn') is not None:
        result['apn'] = str(result['apn']).strip()
    result['_field_sources'] = sources
    result['_normalization_issues'] = sorted(set(issues))
    return result
