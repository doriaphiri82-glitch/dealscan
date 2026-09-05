"""Bounded flat-file readers. Transport/parse failures are not empty successes.

Headerless files, non-UTF8 encodings and multi-member ZIP selection require
explicit source configuration. These readers do not authorize a source for ETL.
"""
from __future__ import annotations
import csv
import io
import zipfile
from scrapers.base import fetch
from scrapers.adapter import BaseScraperAdapter

MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024


def _download(cfg):
    url = cfg.get('data_url') or cfg.get('parcel_source_url')
    if not url: raise ValueError('Flat file source URL is required')
    result = fetch(url,ttl=0,raw=True,max_bytes=MAX_DOWNLOAD_BYTES)
    if not result.ok or not isinstance(result.body,bytes): raise RuntimeError('Flat file download failed')
    if not result.body: raise ValueError('Flat file download is empty')
    if len(result.body)>MAX_DOWNLOAD_BYTES: raise ValueError('Flat file download exceeds limit')
    return result.body


def _rows(text,delimiter=',',*,limit=5000,has_header=True,field_names=None):
    if len(delimiter)!=1 or delimiter in '\r\n"': raise ValueError('Invalid delimiter')
    if not 1<=limit<=5000: raise ValueError('Flat file record cap must be 1–5000')
    reader = csv.reader(io.StringIO(text,newline=''),delimiter=delimiter,strict=True)
    if has_header:
        try: headers=[value.strip() for value in next(reader)]
        except StopIteration: raise ValueError('Flat file has no header') from None
    else:
        if not isinstance(field_names,list) or not field_names: raise ValueError('Headerless files require explicit field_names')
        headers=[str(value).strip() for value in field_names]
    if not headers or any(not header for header in headers) or len({header.casefold() for header in headers})!=len(headers):
        raise ValueError('Flat file has empty or duplicate headers')
    if headers[0].lstrip().startswith(('<','{','[')): raise ValueError('Source is not delimited data')
    rows=[]
    for values in reader:
        if not values or not any(value.strip() for value in values): continue
        if len(values)!=len(headers): raise ValueError('Flat file row width differs from its schema')
        rows.append(dict(zip(headers,(value.strip() for value in values))))
        if len(rows)>=limit: break
    return rows


def _text(body,cfg):
    if body.startswith(b'PK'):
        # Bad ZIPs are errors, not text decoded with replacement characters.
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            candidates=[item for item in archive.infolist() if not item.is_dir() and item.filename.lower().endswith(('.csv','.txt','.tsv'))]
            member=cfg.get('archive_member')
            if member: candidates=[item for item in candidates if item.filename==member]
            if len(candidates)!=1: raise ValueError('Select exactly one delimited archive member')
            item=candidates[0]
            if item.flag_bits&1 or item.file_size>MAX_EXPANDED_BYTES or item.file_size/max(item.compress_size,1)>200:
                raise ValueError('Archive member exceeds extraction safety limits')
            with archive.open(item) as source: body=source.read(MAX_EXPANDED_BYTES+1)
            if len(body)>MAX_EXPANDED_BYTES: raise ValueError('Archive member exceeds expanded limit')
    return body.decode(cfg.get('encoding') or 'utf-8-sig',errors='strict')


class FlatFileAdapter(BaseScraperAdapter):
    delimiter='~'

    def discover(self,cfg):
        text=_text(_download(cfg),cfg)
        return _rows(text,cfg.get('delimiter') or self.delimiter,limit=cfg.get('max_records',5000),
                     has_header=cfg.get('has_header',True),field_names=cfg.get('field_names'))

    def _parse_delimited(self,text,delimiter='~',**kwargs):
        return _rows(text,delimiter,**kwargs)

    def parse(self,raw): return [raw]

    def validate(self,record): return bool(str(record.get('apn') or '').strip())


class CSVAdapter(FlatFileAdapter):
    delimiter=','

    def _parse_csv(self,text,**kwargs): return _rows(text,',',**kwargs)


class ExcelAdapter(FlatFileAdapter):
    def discover(self,cfg):
        import pandas as pd
        body=_download(cfg)
        # XLSX is a ZIP container; bound it before handing it to an XML engine.
        if body.startswith(b'PK'):
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                members=archive.infolist()
                if sum(item.file_size for item in members)>MAX_EXPANDED_BYTES or any(item.file_size/max(item.compress_size,1)>200 for item in members):
                    raise ValueError('Workbook exceeds expanded size limit')
        limit=cfg.get('max_records',5000)
        if not 1<=limit<=5000: raise ValueError('Workbook record cap must be 1–5000')
        # Missing optional Excel engines are explicit failures, never zero rows.
        frame=pd.read_excel(io.BytesIO(body),sheet_name=cfg.get('sheet_name',0),nrows=limit,dtype=str,keep_default_na=False)
        if not isinstance(frame,pd.DataFrame): raise ValueError('Select a single workbook sheet')
        return frame.to_dict(orient='records')
