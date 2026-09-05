import pytest
from helpers import layer_metadata
from scrapers import arcgis
from scrapers.arcgis_adapter import ArcGISFeatureServerAdapter
from scrapers.base import FetchResult


def page(ids, more=True):
    return FetchResult(ok=True, body={'features': [{'attributes': {'OBJECTID': i, 'APN': str(i)}} for i in ids], 'exceededTransferLimit': more})


def test_service_caps_and_short_transfer_limited_pages_do_not_truncate(monkeypatch):
    meta = {**layer_metadata(), 'maxRecordCount': 2}
    pages = iter([page([1]), page([2, 3]), page([4], False)])
    calls = []
    def query(url, payload):
        calls.append(payload); return next(pages)
    monkeypatch.setattr(arcgis, 'post_json', query)
    rows = list(arcgis.query_layer('https://county.example/0', '1=1', ['APN'], max_records=10, metadata=meta))
    assert [row['OBJECTID'] for row in rows] == [1, 2, 3, 4]
    assert [call['resultOffset'] for call in calls] == [0, 1, 3]
    assert all(call['resultRecordCount'] == 2 and call['orderByFields'] == 'OBJECTID ASC' for call in calls)


def test_repeated_pages_fail_visibly_instead_of_duplicate_ingestion(monkeypatch):
    monkeypatch.setattr(arcgis, 'post_json', lambda *a: page([1, 2]))
    with pytest.raises(RuntimeError, match='repeated'):
        list(arcgis.query_layer('https://county.example/0', '1=1', ['APN'], max_records=4, page_size=2, metadata=layer_metadata()))


def test_source_ignoring_record_bound_is_rejected(monkeypatch):
    monkeypatch.setattr(arcgis, 'post_json', lambda *a: page([1, 2, 3]))
    with pytest.raises(RuntimeError, match='record limit'):
        list(arcgis.query_layer('https://county.example/0', '1=1', ['APN'], max_records=2, metadata=layer_metadata()))


def test_caller_record_bound_is_obeyed(monkeypatch):
    pages = iter([page([1, 2]), page([3])]); calls = []
    def query(url, payload): calls.append(payload); return next(pages)
    monkeypatch.setattr(arcgis, 'post_json', query)
    assert len(list(arcgis.query_layer('https://county.example/0', '1=1', ['APN'], max_records=3, page_size=2, metadata=layer_metadata()))) == 3
    assert calls[-1]['resultRecordCount'] == 1


def test_partial_failure_retains_valid_records_and_surfaces_error(monkeypatch):
    monkeypatch.setattr(arcgis, 'layer_metadata', lambda *a, **k: {**layer_metadata(['APN']), 'maxRecordCount': 1})
    pages = iter([page([1]), FetchResult(ok=False, error='timeout')])
    monkeypatch.setattr(arcgis, 'post_json', lambda *a: next(pages))
    result, rows = ArcGISFeatureServerAdapter().run({'county_id': 'fixture', 'arcgis_layer_url': 'https://county.example/0', 'fields': {'apn': 'APN'}}, max_records=5)
    assert len(rows) == 1 and rows[0]['_source_record_id'] == '1'
    assert result.metadata['partial_results'] is True and result.errors


def test_non_paginatable_services_are_quarantined(monkeypatch):
    meta = layer_metadata(); meta['advancedQueryCapabilities']['supportsPagination'] = False
    with pytest.raises(RuntimeError, match='ordered pagination'):
        list(arcgis.query_layer('https://county.example/0', '1=1', ['APN'], metadata=meta))
