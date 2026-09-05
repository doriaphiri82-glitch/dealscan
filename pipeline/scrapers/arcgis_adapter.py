"""ArcGIS adapters use the same proven pagination contract as live validation."""
from __future__ import annotations
from typing import Any, Optional
from scrapers import arcgis
from scrapers.adapter import BaseScraperAdapter


class ArcGISFeatureServerAdapter(BaseScraperAdapter):
    def __init__(self) -> None:
        self.last_error: Optional[str] = None
        self.source_fields: list[str] = []
        self.resolved_fields: dict[str, Any] = {}
        self.query_diagnostics: dict = {}

    @staticmethod
    def _out_fields(cfg: dict) -> list[str]:
        configured = cfg.get('out_fields') or list((cfg.get('fields') or {}).values())
        return list(dict.fromkeys(str(field) for value in configured
                    for field in (value if isinstance(value, (list, tuple)) else [value]) if field))

    @staticmethod
    def _resolve_field_names(cfg: dict, actual_fields: Optional[list[str]]) -> None:
        cfg['fields'] = arcgis.resolve_field_mapping(cfg.get('fields') or {}, actual_fields)
        if cfg.get('out_fields'):
            lookup = {field.casefold(): field for field in actual_fields or []}
            cfg['out_fields'] = [lookup.get(str(value).casefold(), value) for value in cfg['out_fields']]

    def discover(self, cfg: dict) -> list[dict]:
        self.last_error = None
        self.query_diagnostics = {}
        layer = cfg.get('arcgis_layer_url')
        if not layer:
            self.last_error = 'missing arcgis_layer_url'
            return []
        records = []
        try:
            metadata = arcgis.layer_metadata(layer, live=True)
            self.source_fields = [field['name'] for field in metadata.get('fields', []) if field.get('name')]
            if not self.source_fields:
                raise RuntimeError('layer metadata contains no fields')
            self._resolve_field_names(cfg, self.source_fields)
            self.resolved_fields = dict(cfg.get('fields') or {})
            cfg['object_id_field'] = arcgis.object_id_field(metadata)
            if any(field not in self.source_fields for field in self._out_fields(cfg)):
                raise RuntimeError('configured fields no longer exist in source schema')
            for attrs in arcgis.query_layer(layer, cfg.get('where', '1=1'), self._out_fields(cfg),
                    max_records=int(cfg.get('max_records', 5000)), metadata=metadata, diagnostics=self.query_diagnostics):
                records.append(attrs)
        except Exception as exc:
            self.last_error = str(exc)[:200]
        return records

    def parse(self, raw: dict) -> list[dict]:
        return [raw]

    def validate(self, record: dict) -> bool:
        # No fallback to a differently named raw identifier after normalization.
        return bool(record.get('apn') and str(record['apn']).strip())

    def run(self, cfg: dict, max_records: int = 5000):
        result, normalized = super().run(cfg, max_records=max_records)
        result.metadata.update(source_url=cfg.get('arcgis_layer_url'), source_fields=self.source_fields,
                               resolved_fields=self.resolved_fields, partial_results=bool(self.last_error and normalized),
                               pagination=self.query_diagnostics)
        if self.last_error:
            result.errors.append(f'source_error: {self.last_error}')
        return result, normalized


class ArcGISMapServerAdapter(ArcGISFeatureServerAdapter):
    pass


class ArcGISHubAdapter(ArcGISFeatureServerAdapter):
    pass
