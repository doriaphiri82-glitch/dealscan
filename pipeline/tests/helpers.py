"""Ephemeral, deterministic transport/authorization fixtures for offline tests."""
from datetime import datetime, timezone


def layer_metadata(fields=('APN', 'ACRES')):
    return {'type': 'Feature Layer', 'capabilities': 'Query', 'objectIdField': 'OBJECTID', 'maxRecordCount': 1000,
            'fields': [{'name': name, 'type': 'esriFieldTypeString'} for name in fields] + [{'name': 'OBJECTID', 'type': 'esriFieldTypeOID'}],
            'advancedQueryCapabilities': {'supportsPagination': True, 'supportsOrderBy': True}}


def authorized_county(row):
    from config.source_config import county_config
    from validation.gates import source_fingerprint
    row = dict(row)
    row.setdefault('arcgis_layer_url', 'https://county.example/FeatureServer/0')
    row.setdefault('geoid', '99001')
    row.setdefault('field_mapping', {'apn': 'APN', 'lot_size_acres': 'ACRES'})
    row.update(authority_reviewed=True, authority_source_url=row['arcgis_layer_url'],
               authority_evidence_url='https://county.example/gis', source_county_geoid=row['geoid'],
               validation_status='valid', last_validated_at=datetime.now(timezone.utc).isoformat(),
               validation_source_fields_checked=True, validation_pagination_checked=True, validation_sample_checked=4,
               ingestion_authorized=True)
    fingerprint = source_fingerprint(county_config(row['county_id'], row))
    row.update(validated_source_fingerprint=fingerprint, authorized_source_fingerprint=fingerprint)
    return row
