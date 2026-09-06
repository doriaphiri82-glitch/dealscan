from datetime import datetime, timezone
import pytest
from normalization import normalize, number, sale_date
from scrapers.arcgis import is_vacant_residential
from validation.vacancy import vacancy_decision


def test_missing_data_and_financial_defaults_remain_unknown():
    result = normalize({'APN': 'fixture'}, {'fields': {'apn': 'APN'}, 'defaults': {'has_improvements': False, 'market_value': 100000, 'land_use': 'VACANT'}})
    assert result['has_improvements'] is None and result['market_value'] is None
    assert result['year_acquired'] is None and result['tax_delinquent_years'] is None
    assert not is_vacant_residential(result, '')


@pytest.mark.parametrize('value', [float('inf'), float('-inf'), float('nan'), 'NaN', True, 'oops'])
def test_nonfinite_and_invalid_numbers_are_not_money(value):
    assert number(value) is None


def test_real_numeric_formatting_and_area_units_are_respected():
    result = normalize({'AREA': '43,560', 'UNIT': 'SF', 'VALUE': '$1,250.00'}, {'fields': {'lot_size_acres': 'AREA', 'lot_size_unit': 'UNIT', 'market_value': 'VALUE'}})
    assert result['lot_size_acres'] == 1 and result['market_value'] == 1250
    unknown = normalize({'AREA': 43560}, {'fields': {'lot_size_acres': 'AREA'}})
    assert unknown['lot_size_acres'] is None and 'unknown_area_units' in unknown['_normalization_issues']


def test_projected_coordinates_cannot_become_latitude_longitude():
    result = normalize({'latitude': 6328, 'longitude': 457953}, {})
    assert result['latitude'] is None and result['longitude'] is None
    assert 'invalid_coordinates' in result['_normalization_issues']


def test_arcgis_millisecond_dates_parse_without_inventing_dates_from_years():
    dt = datetime(2025, 5, 2, tzinfo=timezone.utc)
    assert sale_date(dt.timestamp() * 1000) == dt
    assert sale_date('2025') is None
    assert sale_date('not-a-date') is None


@pytest.mark.parametrize('property', [
    {'land_use': 'Vacant land', 'has_improvements': True},
    {'land_use': 'Unimproved', 'improvement_value': 1000},
    {'land_use': 'Not vacant'}, {'land_use': 'non-vacant'},
    {'zoning': 'Vacant residential'}, {'improvement_value': -1},
])
def test_conflicting_and_insufficient_vacancy_signals_fail_closed(property):
    assert not vacancy_decision(property)[0]


def test_zero_improvement_from_the_source_is_distinct_from_missing():
    assert vacancy_decision({'improvement_value': 0})[0]
    assert not vacancy_decision({'improvement_value': None})[0]
