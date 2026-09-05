"""One conservative vacancy decision used by screening, scoring, and comp selection."""
from __future__ import annotations
import re
from normalization import boolean, number


def vacancy_decision(prop: dict, county_id: str = '', config: dict | None = None) -> tuple[bool, str]:
    improvement = number(prop.get('improvement_value'))
    flag = boolean(prop.get('has_improvements'))
    if flag is True or (improvement is not None and improvement > 0):
        return False, 'improved_property'
    if improvement is not None and improvement < 0 or 'invalid_improvement_value' in prop.get('_normalization_issues', []):
        return False, 'invalid_improvement_value'
    land_use = str(prop.get('land_use') or '').strip().casefold()
    if re.search(r'\b(?:sfr|house|home|dwelling|building|apartment|condominium|warehouse|improved)\b', land_use):
        return False, 'improved_land_use_classification'
    if re.search(r'\b(?:not|non|formerly|previously)[ -]+(?:vacant|unimproved)\b', land_use):
        return False, 'contradictory_vacancy_classification'
    if re.search(r'\b(?:vacant|unimproved)\b', land_use):
        return True, 'explicit_vacant_land_use'
    # An actual zero from an improvement-value field is evidence; a missing
    # field or a zero in a generic default is not. Normalization drops defaults.
    if improvement == 0:
        return True, 'source_zero_improvement_value'
    zoning = str(prop.get('zoning') or '').strip().casefold()
    if flag is False and (re.search(r'\bresidential\b', land_use) or re.search(r'\b(?:residential|res|r-?\d+)\b', zoning)):
        return True, 'explicit_no_improvements_residential'
    # Numeric code semantics vary between jurisdictions. Use them only when an
    # authority-reviewed codebook is attached to this exact county configuration.
    config = config or {}
    if config.get('vacancy_codebook_url') and config.get('county_id') == county_id:
        code = str(prop.get('use_code') or prop.get('land_use') or '').strip().upper()
        if code in {str(code).upper() for code in config.get('vacant_use_codes', [])}:
            return True, 'documented_vacant_use_code'
    return False, 'missing_vacancy_signal' if flag is None else 'no_supported_vacancy_classification'
