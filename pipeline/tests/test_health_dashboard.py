from monitoring.health import build_national_dashboard
from helpers import authorized_county


def test_dashboard_uses_registry_state_without_recent_run():
    payload = build_national_dashboard(
        {
            "counties": {
                "alpha_01_001": authorized_county({
                    "county_id": "alpha_01_001",
                    "county_name": "Alpha County",
                    "state": "Alabama",
                    "verification_status": "verified",
                    "coverage_status": "tier_5",
                    "last_record_count": 17,
                    "persisted_count": 17,
                    "last_run_status": "ok",
                    "last_published_count": 17,
                    "last_successful_run": "2026-09-04T10:00:00+00:00",
                    "data_freshness": "2026-09-04T10:00:00+00:00",
                }),
                "beta_01_003": {**authorized_county({
                    "county_id": "beta_01_003",
                    "county_name": "Beta County",
                    "state": "Alabama",
                    "validation_status": "valid",
                    "verification_status": "source_verified",
                    "coverage_status": "tier_3",
                    "last_record_count": 0,
                }), "ingestion_authorized": False},
            }
        },
        [],
    )

    counties = {row["county_id"]: row for row in payload["counties"]}
    alpha = counties["alpha_01_001"]
    beta = counties["beta_01_003"]

    assert alpha["status"] == "active"
    assert alpha["tier"] == "tier_6"
    assert alpha["records"] == 17
    assert alpha["published"] == 17
    assert alpha["last_run"] == "2026-09-04T10:00:00+00:00"
    assert beta["tier"] == "tier_2"
    assert beta["status"] == "not_implemented"


def test_registry_published_count_is_used_when_explicitly_persisted():
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
                    "last_published_count": 4,
                }
            }
        },
        [],
    )
    assert payload["counties"][0]["published"] == 4


def test_legacy_registry_without_published_count_does_not_infer_publication():
    payload = build_national_dashboard(
        {
            "counties": {
                "legacy_01_001": {
                    "county_id": "legacy_01_001",
                    "county_name": "Legacy County",
                    "state": "Alabama",
                    "verification_status": "verified",
                    "coverage_status": "tier_5",
                    "last_record_count": 17,
                }
            }
        },
        [],
    )
    assert payload["counties"][0]["records"] == 0  # found is not stored
    assert payload["counties"][0]["published"] == 0


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
    assert county["tier"] == "tier_4"  # stored is not financially qualified
    assert county["records"] == 20
    assert county["published"] == 0
    assert county["last_run"] == "2026-09-04T12:00:00+00:00"


def test_remote_empty_runtime_does_not_resurrect_a_stale_local_run():
    payload=build_national_dashboard({'meta':{'runtime_source':'supabase'},'counties':{'fixture':{'county_id':'fixture'}}},
        [{'county_id':'fixture','status':'ok','at':'2026-09-05T00:00:00Z','counts':{'stored':500,'published':5}}])
    assert payload['counties'][0]['records']==0
    assert payload['counties'][0]['published']==0
