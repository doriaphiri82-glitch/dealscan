import json
from pathlib import Path
import pytest
from urllib3.exceptions import ProtocolError
from scrapers import base


class Response:
    status_code=200
    encoding='utf-8'
    def __init__(self,body,headers=None,status=200):
        self.body=body; self.headers=headers or {}; self.closed=False; self.status_code=status
    def iter_content(self,**kw):
        yield self.body
    def close(self): self.closed=True


@pytest.fixture(autouse=True)
def transport(monkeypatch,tmp_path):
    monkeypatch.setattr(base,'CACHE_DIR',str(tmp_path/'cache'))
    monkeypatch.setattr(base,'_politeness_delay',lambda _:None)


@pytest.mark.parametrize('method',['GET','POST'])
def test_every_source_response_is_streamed_bounded_and_closed(monkeypatch,method):
    response=Response(b'{"value":"'+b'x'*100+b'"}')
    calls=[]
    monkeypatch.setattr(base._session,method.lower(),lambda *a,**kw:calls.append(kw) or response)
    result=base.fetch('https://county.example',ttl=0,respect_robots=False,as_json=True,max_bytes=20) if method=='GET' else base.post_json('https://county.example',{},max_bytes=20)
    assert not result.ok and response.closed
    assert calls[0]['stream'] is True and calls[0]['allow_redirects'] is False
    assert calls[0]['timeout']==(5,10)


@pytest.mark.parametrize('body',[b'{"APN":"one","APN":"two"}',b'{"value":NaN}',b'{"value":Infinity}',b'{"value":-Infinity}',b'{unfinished'])
def test_json_never_silently_overwrites_fields_or_accepts_nonfinite_tokens(monkeypatch,body):
    response=Response(body)
    monkeypatch.setattr(base._session,'post',lambda *a,**kw:response)
    result=base.post_json('https://county.example/query',{})
    assert not result.ok and response.closed


def test_text_and_json_caches_cannot_poison_each_other(monkeypatch):
    calls=[]
    def get(*a,**kw): calls.append(kw); return Response(b'{"value":1}')
    monkeypatch.setattr(base._session,'get',get)
    url='https://county.example/data'
    assert base.fetch(url,respect_robots=False).body=='{"value":1}'
    assert base.fetch(url,respect_robots=False,as_json=True).body=={'value':1}
    cached=base.fetch(url,respect_robots=False,as_json=True)
    assert cached.body=={'value':1} and cached.from_cache
    assert len(calls)==2


def test_oversized_cache_cannot_bypass_a_smaller_read_limit(monkeypatch):
    url='https://county.example/data'
    base._store_cache(url,{'value':'x'*500},'v2-json')
    monkeypatch.setattr(base._session,'get',lambda *a,**kw:Response(b'{"n":1}'))
    result=base.fetch(url,respect_robots=False,as_json=True,max_bytes=20)
    assert result.body=={'n':1} and not result.from_cache


def test_optional_cache_failure_is_observable_but_does_not_lose_a_successful_read(monkeypatch,tmp_path,caplog):
    blocker=tmp_path/'not-a-directory';blocker.write_text('fixture')
    monkeypatch.setattr(base,'CACHE_DIR',str(blocker))
    monkeypatch.setattr(base._session,'get',lambda *a,**kw:Response(b'{"n":1}'))
    result=base.fetch('https://county.example',as_json=True,respect_robots=False)
    assert result.ok and result.body=={'n':1}
    assert 'cache write unavailable' in caplog.text


def test_cache_replacement_failure_does_not_destroy_previous_complete_file(monkeypatch):
    url='https://county.example';base._store_cache(url,{'n':1},'v2-json')
    path=Path(base._cache_path(url,'v2-json'))
    before=path.read_bytes()
    monkeypatch.setattr(base.os,'replace',lambda *a:(_ for _ in ()).throw(OSError('unavailable')))
    base._store_cache(url,{'n':2},'v2-json')
    assert path.read_bytes()==before
    assert len(list(path.parent.iterdir()))==1
    assert path.stat().st_mode&0o077==0


def test_untrusted_hostname_cannot_escape_the_cache_directory():
    path=Path(base._cache_path('https://../../outside','v2-json'))
    assert path.is_relative_to(Path(base.CACHE_DIR))
    assert '..' not in path.relative_to(base.CACHE_DIR).parts


def test_stream_deadline_stops_a_slow_response(monkeypatch):
    class Slow(Response):
        def iter_content(self,**kw):
            yield b'{'
            clock[0]=100
            yield b'}'
    clock=[0]
    monkeypatch.setattr(base.time,'monotonic',lambda:clock[0])
    response=Slow(b'')
    monkeypatch.setattr(base._session,'get',lambda *a,**kw:response)
    result=base.fetch('https://county.example',ttl=0,respect_robots=False,as_json=True,timeout=1,retries=0)
    assert not result.ok and result.error=='TimeoutError' and response.closed


def test_read1_transport_errors_are_reported_without_raw_body_or_uncaught_exceptions(monkeypatch):
    class Broken:
        def read1(self,*a,**kw): raise ProtocolError('PRIVATE')
    response=Response(b''); response.raw=Broken()
    monkeypatch.setattr(base._session,'post',lambda *a,**kw:response)
    result=base.post_json('https://county.example',{},retries=0)
    assert not result.ok and result.error=='ProtocolError' and response.closed
    assert 'PRIVATE' not in result.error


@pytest.mark.parametrize('url',['file:///etc/passwd','https://user:secret@county.example','https://county.example:bad','https://county.example/\nprivate'])
def test_both_methods_reject_invalid_sources_before_requests(monkeypatch,url):
    def forbidden(*a,**kw): raise AssertionError('Network must not be called')
    monkeypatch.setattr(base._session,'get',forbidden);monkeypatch.setattr(base._session,'post',forbidden)
    assert not base.fetch(url,ttl=0,respect_robots=False).ok
    assert not base.post_json(url,{}).ok


@pytest.mark.parametrize('limit,ok',[(50,False),(10000,True)])
def test_actual_urllib3_gzip_decoding_is_bounded_by_expanded_bytes(monkeypatch,limit,ok):
    import gzip,io,requests
    from urllib3.response import HTTPResponse
    data=json.dumps({'value':'x'*1000}).encode()
    compressed=gzip.compress(data)
    response=requests.Response();response.status_code=200
    response.headers.update({'Content-Type':'application/json','Content-Encoding':'gzip','Content-Length':str(len(compressed))})
    response.raw=HTTPResponse(body=io.BytesIO(compressed),headers=response.headers,preload_content=False)
    monkeypatch.setattr(base._session,'get',lambda *a,**kw:response)
    result=base.fetch('https://county.example/data',ttl=0,respect_robots=False,as_json=True,max_bytes=limit)
    assert result.ok is ok
    if ok: assert result.body=={'value':'x'*1000}
