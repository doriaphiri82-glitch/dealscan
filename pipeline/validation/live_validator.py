"""Uncached metadata, schema, records, API behavior and pagination validation."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from config.counties.registry import list_counties, update_county, mark_county_validation
from config.source_config import county_config
from normalization import normalize, sale_date
from scrapers import arcgis
from validation.etl_validator import validate_county_config
from validation.gates import source_fingerprint


def _config(county: dict) -> dict:
    return county_config(county['county_id'], county)


def _resolve_layer(cfg: dict) -> str:
    # A newly resolved layer must be registered and reviewed; never silently
    # substitute another URL during the validation-to-ETL handoff.
    return str(cfg.get('arcgis_layer_url') or '').rstrip('/')


def _resolve_mapping_to_source_case(fields: dict, source_fields: list[str]) -> dict:
    return arcgis.resolve_field_mapping(fields, source_fields)


def validate_county_live(county: dict) -> dict:
    cid = county['county_id']
    cfg = _config(county)
    layer = _resolve_layer(cfg)
    # Invalidate any prior authorization before making a new network request.
    mark_county_validation(cid, status='validating')
    if not layer:
        errors = ['no resolvable ArcGIS parcel layer']
        mark_county_validation(cid, status='unreachable', errors=errors)
        return {'county_id': cid, 'status': 'unreachable', 'errors': errors, 'warnings': []}
    try:
        metadata = arcgis.layer_metadata(layer, live=True)
        if metadata.get('type') != 'Feature Layer' or 'Query' not in str(metadata.get('capabilities', '')):
            raise RuntimeError('source is not a queryable feature layer')
        fields = [field['name'] for field in metadata.get('fields', []) if field.get('name')]
        if not fields:
            raise RuntimeError('layer metadata returned no fields')
        cfg['arcgis_layer_url'] = layer
        cfg['object_id_field'] = cfg['source_object_id_field'] = arcgis.object_id_field(metadata)
        cfg['fields'] = _resolve_mapping_to_source_case(cfg.get('fields') or {}, fields)
        report = validate_county_config(cid, cfg, source_fields=fields)
        if not report['valid']:
            mark_county_validation(cid, status='invalid', errors=report['errors'], source_fields_checked=True)
            return {'county_id': cid, 'status': 'invalid', 'layer': layer, **report}
        out_fields = []
        for value in cfg['fields'].values():
            out_fields.extend(value if isinstance(value, (list, tuple)) else [value])
        count = arcgis.query_count(layer, cfg.get('where', '1=1'))
        diagnostics = {}
        sample = list(arcgis.query_layer(layer, cfg.get('where', '1=1'), list(dict.fromkeys(out_fields)),
                      max_records=min(count, 5), page_size=2, metadata=metadata, diagnostics=diagnostics))
        report = validate_county_config(cid, cfg, source_fields=fields, sample_records=sample)
        if not sample:
            report['errors'].append('live layer returned no sample records')
        expected = min(count, 5)
        if len(sample) != expected:
            report['errors'].append('sample pagination returned fewer records than the source count')
        if count > 2 and diagnostics.get('pages', 0) < 2:
            report['errors'].append('source pagination was not demonstrated')
        if sample and not any(normalize(row, cfg).get('lot_size_acres') for row in sample):
            report['errors'].append('sample has no usable acreage with known units')
        modified = sale_date((metadata.get('editingInfo') or {}).get('lastEditDate'))
        if modified and modified > datetime.now(timezone.utc) + timedelta(days=1):
            report['errors'].append('source freshness timestamp is in the future')
        if not modified:
            report['warnings'].append('source data freshness is unavailable; validation time is not data freshness')
        valid = not report['errors']
        status = 'valid' if valid else 'invalid'
        update_county(cid, arcgis_layer_url=layer, parcel_source_url=layer, field_mapping=cfg['fields'],
                      source_record_count=count, source_max_record_count=metadata.get('maxRecordCount'),
                      source_object_id_field=arcgis.object_id_field(metadata),object_id_field=arcgis.object_id_field(metadata),
                      data_freshness=modified.isoformat() if modified else None,
                      verification_status='source_verified' if valid else 'discovered_not_verified')
        mark_county_validation(cid, status=status, errors=report['errors'], warnings=report['warnings'],
                               source_fields_checked=True, sample_checked=len(sample),
                               pagination_checked=valid, fingerprint=source_fingerprint(cfg))
        return {'county_id': cid, 'status': status, 'layer': layer, 'field_count': len(fields),
                'sample_count': len(sample), 'record_count': count, 'pagination': diagnostics,
                'errors': report['errors'], 'warnings': report['warnings'], 'ingestion_authorized': False}
    except Exception as exc:
        # Only structural diagnostics, no source record values/owner data.
        error = str(exc)[:250]
        mark_county_validation(cid, status='unreachable', errors=[error])
        return {'county_id': cid, 'status': 'unreachable', 'layer': layer, 'errors': [error], 'warnings': []}


def validate_live_batch(limit: int = 25, include_validated: bool = False, county_id: str | None = None) -> dict:
    counties = [c for c in list_counties() if c.get('arcgis_layer_url') or c.get('parcel_source_url') or c.get('gis_url')]
    if county_id is not None: counties = [county for county in counties if county['county_id'] == county_id]
    counties.sort(key=lambda c: (bool(c.get('last_validated_at')), c.get('last_validated_at') or '', c['county_id']))
    # Always revisit oldest validation first; successful sources cannot stay
    # authorized forever. include_validated is retained for CLI compatibility.
    results = [validate_county_live(c) for c in counties[:max(0, min(int(limit), 100))]]
    return {'attempted': len(results), 'valid': sum(r['status'] == 'valid' for r in results),
            'invalid': sum(r['status'] == 'invalid' for r in results),
            'unreachable': sum(r['status'] == 'unreachable' for r in results), 'results': results}
