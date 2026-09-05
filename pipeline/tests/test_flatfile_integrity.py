import io
import zipfile
import pytest
from scrapers import base, flatfile_adapter as files


def test_csv_preserves_quoted_values_bom_and_record_bound(monkeypatch):
    calls=[]
    def fetch(url,**kw):
        calls.append(kw)
        return base.FetchResult(True,200,b'\xef\xbb\xbfAPN,ADDRESS\n001,"10 First, Avenue"\n002,Second\n')
    monkeypatch.setattr(files,'fetch',fetch)
    rows=files.CSVAdapter().discover({'data_url':'https://county.example/data.csv','max_records':1})
    assert rows==[{'APN':'001','ADDRESS':'10 First, Avenue'}]
    assert calls[0]['max_bytes']==files.MAX_DOWNLOAD_BYTES and calls[0]['ttl']==0


@pytest.mark.parametrize('body',[b'',b'<html>Access denied</html>',b'APN,APN\n1,2',b'APN,AREA\n1,2,3',b'APN,AREA\n1',b'APN,AREA\n"unfinished',b'APN\n\xff'])
def test_invalid_source_is_an_error_not_an_empty_success(monkeypatch,body):
    monkeypatch.setattr(files,'fetch',lambda *a,**kw:base.FetchResult(True,200,body))
    result, rows=files.CSVAdapter().run({'county_id':'fixture','data_url':'https://county.example/data'},1)
    assert result.errors and not rows


def test_download_failure_is_not_zero_success(monkeypatch):
    monkeypatch.setattr(files,'fetch',lambda *a,**kw:base.FetchResult(False,503,error='unavailable'))
    result,rows=files.CSVAdapter().run({'county_id':'fixture','data_url':'https://county.example/data'},2)
    assert result.errors==['discover_error: RuntimeError'] and rows==[]


def archive(members):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as target:
        for name,value in members.items(): target.writestr(name,value)
    return stream.getvalue()


def test_ambiguous_zip_requires_explicit_member(monkeypatch):
    body=archive({'a.csv':'APN\n001\n','b.csv':'APN\n002\n'})
    monkeypatch.setattr(files,'fetch',lambda *a,**kw:base.FetchResult(True,200,body))
    cfg={'data_url':'https://county.example/archive.zip'}
    with pytest.raises(ValueError,match='exactly one'): files.CSVAdapter().discover(cfg)
    assert files.CSVAdapter().discover({**cfg,'archive_member':'a.csv'})==[{'APN':'001'}]


def test_zip_expansion_is_bounded(monkeypatch):
    body=archive({'a.csv':'APN\n'+'0'*100000})
    monkeypatch.setattr(files,'fetch',lambda *a,**kw:base.FetchResult(True,200,body))
    with pytest.raises(ValueError,match='safety limits'): files.CSVAdapter().discover({'data_url':'https://county.example/archive.zip'})


def test_headerless_schema_is_never_guessed():
    adapter=files.FlatFileAdapter()
    with pytest.raises(ValueError,match='explicit field_names'): adapter._parse_delimited('001~1.5',has_header=False)
    assert adapter._parse_delimited('001~1.5',has_header=False,field_names=['APN','ACRES'])==[{'APN':'001','ACRES':'1.5'}]


def test_streaming_byte_limit_applies_even_without_content_length(monkeypatch):
    class Response:
        status_code=200; headers={}; closed=False
        def iter_content(self,**kw): yield b'123'; yield b'456'
        def close(self): self.closed=True
    response=Response()
    monkeypatch.setattr(base._session,'get',lambda *a,**kw:response)
    monkeypatch.setattr(base,'_politeness_delay',lambda _:None)
    result=base.fetch('https://county.example/data',ttl=0,respect_robots=False,raw=True,max_bytes=5)
    assert result.ok is False and response.closed is True


def test_robots_reads_have_a_deadline_and_do_not_authorize_an_error_response(monkeypatch):
    calls=[]
    class Response:
        status_code=503
        def close(self): pass
    monkeypatch.setattr(base._session,'get',lambda *a,**kw:calls.append(kw) or Response())
    assert base.robots_allows('https://county.example/data') is False
    assert calls[0]['timeout']==(5,10) and calls[0]['allow_redirects'] is False
