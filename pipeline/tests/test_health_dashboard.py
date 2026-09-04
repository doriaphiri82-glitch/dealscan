from monitoring.health import build_national_dashboard


def test_dashboard_uses_registry_state_without_recent_run():
    payload = build_national_dashboard(
        {
            "counties": {
                "alpha_01_001": {
                    "county_id": "alpha_01_001",
                    "county_name": "Alpha County",
                    "state": "Alabama",
                    "verification_status": "verified",
                    "coverage_status": "tier_5",
                    "last_record_count": 17,
                    "last_successful_run": "2026-09-04T10:00:00+00:00",
                    "data_freshness": "2026-09-04T10:00:00+00:00",
                },
                "beta_01_003": {
                    "county_id": "beta_01_003",
                    "county_name": "Beta County",
                    "state": "Alabama",
                    "validation_status": "valid",
                    "verification_status": "source_verified",
                    "coverage_status": "tier_3",
                    "last_record_count": 0,
                },
            }
        },
        [],
    )

    counties = {row["county_id"]: row for row in payload["counties"]}
    alpha = counties["alpha_01_001"]
    beta = counties["beta_01_003"]

    assert alpha["status"] == "active"
    assert alpha["tier"] == "tier_5"
    assert alpha["records"] == 17
    assert alpha["published"] == 17
    assert alpha["last_run"] == "2026-09-04T10:00:00+00:00"
    assert beta["tier"] == "tier_2"
    assert beta["status"] == "not_implemented"


def test_recent_run_remains_authoritative_over_registry_fallback():
    payload = build_national_dashboard(
        {
            "counties": {
                "alpha_01_001": {
                    "county_id": "alpha_01_001",
                    "county_name": "Alpha County",
                    "state": "Alabama",
                    "verification_status": "verified",
                    "coverage_status": "tier_5",
                    "last_record_count": 100,
                }
            }
        },
        [
            {
                "county_id": "alpha_01_001",
                "status": "degraded",
                "at": "2026-09-04T12:00:00+00:00",
                "counts": {"found": 100, "saved": 20, "published": 0, "rejected": 80},
            }
        ],
    )

    county = payload["counties"][0]
    assert county["status"] == "degraded"
    assert county["tier"] == "tier_5"
    assert county["records"] == 20
    assert county["published"] == 0
    assert county["last_run"] == "2026-09-04T12:00:00+00:00"
