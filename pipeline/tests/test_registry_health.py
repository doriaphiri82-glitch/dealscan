"""
DealScan - County registry and health tests.
"""
from __future__ import annotations

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
    mark_county_run,
)
from config.counties.national_registry import ensure_pilot_counties, PILOT_COUNTIES
from monitoring.health import build_county_health, coverage_tier_name, _registry_health

REGTEST_PATH = os.path.join(os.path.dirname(__file__), "test_registry.json")

@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEALSCAN_TEST_REGISTRY", "1")
    import config.counties.registry as reg_mod
    monkeypatch.setattr(reg_mod, "REGISTRY_PATH", REGTEST_PATH, raising=False)
    if os.path.exists(REGTEST_PATH): os.remove(REGTEST_PATH)
    yield
    if os.path.exists(REGTEST_PATH): os.remove(REGTEST_PATH)


def test_register_and_get_county() -> None:
    register_county(county_id="test_aa", county_name="Test County", state="Arizona", state_fips="04", county_fips="999", geoid="04999", population=1000, scraper_type="arcgis", verification_status="verified", coverage_status="tier_4")
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
    register_county(county_id="update_aa", county_name="Update County", state="Arizona", state_fips="04", county_fips="998", geoid="04998")
    updated = update_county("update_aa", coverage_status="tier_5", population=5000)
    assert updated is not None
    assert updated["coverage_status"] == "tier_5"
    assert updated["population"] == 5000


def test_remove_county() -> None:
    register_county(county_id="remove_aa", county_name="Remove County", state="Arizona", state_fips="04", county_fips="997", geoid="04997")
    assert get_county("remove_aa") is not None
    assert remove_county("remove_aa") is True
    assert get_county("remove_aa") is None


def test_county_summary_counts() -> None:
    ensure_pilot_counties()
    summary = county_summary()
    assert summary["total"] >= len(PILOT_COUNTIES)


def test_health_tier_mapping() -> None:
    entry = build_county_health({"county_id": "ok_aa", "status": "ok", "counts": {"found": 100, "saved": 10, "published": 2}})
    assert coverage_tier_name(entry.coverage_tier) == "Production Monitored"
    assert entry.records_stored == 10
    assert entry.records_published == 2


def test_empty_success_does_not_verify_county() -> None:
    register_county(county_id="empty_aa", county_name="Empty County", state="Arizona", state_fips="04", county_fips="996", geoid="04996", data_source_type="arcgis", coverage_status="tier_1")
    mark_county_run("empty_aa", record_count=0, persisted_count=0, status="ok")
    entry = get_county("empty_aa")
    assert entry["coverage_status"] == "tier_1"
    assert entry["verification_status"] == "discovered_not_verified"
    assert entry.get("last_successful_run") is None
    assert entry.get("last_published_count") == 0


def test_degraded_persistence_does_not_verify_county() -> None:
    register_county(county_id="degraded_aa", county_name="Degraded County", state="Arizona", state_fips="04", county_fips="995", geoid="04995", data_source_type="arcgis", coverage_status="tier_1")
    mark_county_run("degraded_aa", record_count=100, persisted_count=50, qualified_count=5, published_count=5, status="degraded", error="partial source failure")
    entry = get_county("degraded_aa")
    assert entry["coverage_status"] == "tier_1"
    assert entry["verification_status"] == "discovered_not_verified"
    assert entry.get("last_successful_run") is None
    assert entry.get("last_published_count") == 5


def test_registry_health_never_infers_published_from_stored_records() -> None:
    health = _registry_health({
        "county_id": "truth_aa",
        "verification_status": "verified",
        "coverage_status": "tier_5",
        "last_record_count": 100,
        "last_published_count": 7,
    })
    assert health.records_stored == 100
    assert health.records_published == 7


def test_registry_health_defaults_unknown_published_count_to_zero() -> None:
    health = _registry_health({
        "county_id": "legacy_aa",
        "verification_status": "verified",
        "coverage_status": "tier_5",
        "last_record_count": 100,
    })
    assert health.records_stored == 100
    assert health.records_published == 0
