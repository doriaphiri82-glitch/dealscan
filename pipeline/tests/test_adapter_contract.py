import pytest
from scrapers.adapter import BaseScraperAdapter


class Adapter(BaseScraperAdapter):
    def __init__(self,rows): self.rows=rows;self.called=False
    def discover(self,cfg): self.called=True;return self.rows
    def parse(self,raw): return [raw]
    def validate(self,record): return bool(record.get('apn'))


@pytest.mark.parametrize('limit',[0,-1,True,'5',None,5001])
def test_invalid_bounds_do_not_call_the_source(limit):
    adapter=Adapter([])
    result,rows=adapter.run({'county_id':'fixture'},max_records=limit)
    assert not adapter.called and rows==[] and result.errors==['invalid_record_limit']


@pytest.mark.parametrize('collection',[None,{},'not a record list',1])
def test_invalid_discovery_shape_is_an_observable_failure(collection):
    result,rows=Adapter(collection).run({'county_id':'fixture'})
    assert rows==[] and result.errors==['invalid_source_collection']


def test_a_source_cannot_overrun_the_shared_adapter_limit():
    result,rows=Adapter([{'apn':'1'},{'apn':'2'}]).run({'county_id':'fixture'},max_records=1)
    assert rows==[] and result.discovered==2
    assert result.errors==['source_exceeded_record_limit']


@pytest.mark.parametrize('parsed',[None,'not a list',{'apn':'x'},[{'apn':'x'},{'apn':'y'}]])
def test_invalid_or_overexpanded_parse_is_rejected_once(parsed):
    class Broken(Adapter):
        def parse(self,raw):return parsed
    result,rows=Broken([{'apn':'source'}]).run({'county_id':'fixture'},max_records=1)
    assert rows==[] and result.rejected==1
    assert result.rejection_reasons=={'parse_error':1}
    assert len(result.metadata['audit_records'])==1


def test_bad_normalizer_cannot_crash_the_rejection_audit_path():
    class Broken(Adapter):
        def normalize(self,record,cfg):return None
    result,rows=Broken([{'unexpected':'PRIVATE'}]).run({'county_id':'fixture'})
    assert rows==[] and result.rejected==1
    assert result.rejection_reasons=={'normalize_error':1}
    assert result.metadata['audit_records'][0]['raw_payload']=={'unexpected':'PRIVATE'}
    assert 'PRIVATE' not in str(result.errors)


def test_a_truthy_nonboolean_validator_result_is_not_accepted():
    class Broken(Adapter):
        def validate(self,record):return 'false'
    result,rows=Broken([{'apn':'source'}]).run({'county_id':'fixture'})
    assert rows==[] and result.rejected==1
