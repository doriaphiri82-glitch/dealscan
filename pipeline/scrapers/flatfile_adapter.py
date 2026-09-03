"""
DealScan - Flat-file / bulk-download adapter.

Handles counties that publish delimited flat files, CSV, XLS/XLSX, or ZIP archives.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Any, Dict, List, Optional

from scrapers.base import fetch
from scrapers.adapter import BaseScraperAdapter, ScrapeResult


class FlatFileAdapter(BaseScraperAdapter):
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = cfg.get("parcel_source_url") or cfg.get("data_url")
        if not url:
            return []
        r = fetch(url, ttl=7 * 24 * 3600, raw=True)
        if not r.ok or not isinstance(r.body, bytes):
            return []
        text = ""
        try:
            with zipfile.ZipFile(io.BytesIO(r.body)) as zf:
                member = next((n for n in zf.namelist()
                               if n.lower().endswith((".txt", ".csv"))), None)
                if member:
                    text = zf.read(member).decode("utf-8", errors="replace")
        except Exception:
            text = r.body.decode("utf-8", errors="replace")
        if not text:
            return []
        rows = self._parse_delimited(text)
        return rows

    def _parse_delimited(self, text: str, delimiter: str = "~") -> List[Dict[str, Any]]:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return []
        first = [c.strip() for c in lines[0].split(delimiter)]
        has_header = any(any(ch.isalpha() for ch in cell) for cell in first) and len(first) > 3
        start = 1 if has_header else 0
        headers = first if has_header else [f"col{i}" for i in range(len(first))]
        rows = []
        for ln in lines[start:]:
            cells = [c.strip() for c in ln.split(delimiter)]
            while len(cells) < len(headers):
                cells.append("")
            rows.append(dict(zip(headers, cells[: len(headers)])))
        return rows

    def parse(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [raw]

    def validate(self, record: Dict[str, Any]) -> bool:
        apn = record.get("apn") or record.get("PARCEL_ID") or record.get("ACCOUNT")
        return bool(apn and str(apn).strip())


class CSVAdapter(BaseScraperAdapter):
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = cfg.get("parcel_source_url") or cfg.get("data_url")
        if not url:
            return []
        r = fetch(url, ttl=7 * 24 * 3600, raw=True)
        if not r.ok or not isinstance(r.body, bytes):
            return []
        text = r.body.decode("utf-8", errors="replace")
        return self._parse_csv(text)

    def _parse_csv(self, text: str) -> List[Dict[str, Any]]:
        try:
            f = io.StringIO(text)
            reader = csv.DictReader(f)
            return [dict(row) for row in reader if any(v for v in row.values())]
        except Exception:
            return []

    def parse(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [raw]

    def validate(self, record: Dict[str, Any]) -> bool:
        apn = record.get("apn") or record.get("PARCEL_ID") or record.get("ACCOUNT")
        return bool(apn and str(apn).strip())


class ExcelAdapter(BaseScraperAdapter):
    def discover(self, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = cfg.get("parcel_source_url") or cfg.get("data_url")
        if not url:
            return []
        r = fetch(url, ttl=7 * 24 * 3600, raw=True)
        if not r.ok or not isinstance(r.body, bytes):
            return []
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(r.body))
            return df.to_dict(orient="records")
        except Exception:
            return []

    def parse(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [raw]

    def validate(self, record: Dict[str, Any]) -> bool:
        apn = record.get("apn") or record.get("PARCEL_ID") or record.get("ACCOUNT")
        return bool(apn and str(apn).strip())
