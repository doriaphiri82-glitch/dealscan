import runners


def test_vacancy_rejection_is_counted_once():
    metrics = runners.RunMetrics("test_county")
    metrics.record_vacancy_rejection("improved_property")
    assert metrics.rejected == 0
    assert metrics.vacancy_rejection_reasons == {"improved_property": 1}
    assert metrics.rejection_reasons == {"improved_property": 1}


def test_vacancy_rejection_does_not_duplicate_scraper_rejections():
    metrics = runners.RunMetrics("test_county")
    metrics.rejected = 3
    metrics.record_rejection("missing_apn")
    metrics.record_vacancy_rejection("missing_vacancy_signal")
    assert metrics.rejected == 4
    assert metrics.rejection_reasons == {
        "missing_apn": 1,
        "missing_vacancy_signal": 1,
    }
