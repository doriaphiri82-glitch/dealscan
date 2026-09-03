"""
DealScan - County registry and health tests.
"""
from __future__ import annotations

import json
import os

import pytest

from config.counties.registry import (
    _load_registry,
    _save_registry,
    register_county,
    get_county,
    list_counties,
    update_county,
    remove_county,
    county_summary,
)
from config.counties.national_registry import ensure_pilot_counties, PILOT_COUNTIES
from monitoring.health import build_county_health, coverage_tier_name


REGTEST_PATH = os.path.join(os.path.dirname(__file__), "test_registry.json")


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEALSCAN_TEST_REGISTRY", "1")
    import config.counties.registry as reg_mod
    monkeypatch.setattr(reg_mod, "REGISTRY_PATH", REGTEST_PATH, raising=False)


def test_register_and_get_county() -> None:
    register_county(
        county_id="test_aa",
        county_name="Test County",
        state="Arizona",
        state_fips="04",
        county_fips="999",
        geoid="04999",
        population=1000,
        scraper_type="arcgis",
        verification_status="verified",
        coverage_status="tier_4",
    )
    entry = get_county("test_aa")
    assert entry is not None
    assert entry["county_name"] == "Test County"
    assert entry["state"] == "Arizona"
    assert entry["coverage_status"] == "tier_4"


def test_pilot_counties_present() -> None:
    ensure_pilot_counties()
    for cid in PILOT_COUNTIES:
        entry = get_county(cid)
        assert entry is not None, f"missing pilot county {cid}"
        assert entry["state_fips"] == PILOT_COUNTIES[cid]["state_fips"]


def test_update_county() -> None:
    register_county(
        county_id="update_aa",
        county_name="Update County",
        state="Arizona",
        state_fips="04",
        county_fips="998",
        geoid="04998",
    )
    updated = update_county("update_aa", coverage_status="tier_5", population=5000)
    assert updated is not None
    assert updated["coverage_status"] == "tier_5"
    assert updated["population"] == 5000


def test_remove_county() -> None:
    register_county(
        county_id="remove_aa",
        county_name="Remove County",
        state="Arizona",
        state_fips="04",
        county_fips="997",
        geoid="04997",
    )
    assert get_county("remove_aa") is not None
    assert remove_county("remove_aa") is True
    assert get_county("remove_aa") is None


def test_county_summary_counts() -> None:
    ensure_pilot_counties()
    summary = county_summary()
    assert summary["total"] >= len(PILOT_COUNTIES)


def test_health_tier_mapping() -> None:
    entry = build_county_health({
        "county_id": "ok_aa",
        "status": "ok",
        "counts": {"found": 100, "saved": 10, "published": 2},
    })
    assert coverage_tier_name(entry.coverage_tier) == "Production Monitored"
    assert entry.records_stored == 10
    assert entry.records_published == 2
