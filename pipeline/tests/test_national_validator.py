from validation.national_validator import validate_all_counties


def test_national_validation_returns_all_registered_counties():
    report = validate_all_counties()
    assert report["counts"]["total"] == len(report["results"])
    assert report["counts"]["total"] >= 3
    assert {"not_started", "invalid", "ready", "etl_verified"} >= set(report["counts"])


def test_national_validation_does_not_claim_etl_from_source_configuration():
    report = validate_all_counties()
    for row in report["results"]:
        if row["status"] == "ready":
            assert row["coverage_status"] not in {"tier_4", "tier_5"} or row["verification_status"] == "verified"
