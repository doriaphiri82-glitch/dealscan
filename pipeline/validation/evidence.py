"""Reproduce a private property from its source audit without exposing values."""
from __future__ import annotations
import hashlib
import json
from normalization import boolean, normalize, number, source_identity
from persistence import PROPERTY_FIELDS, json_safe, property_payload
from validation.gates import source_fingerprint, source_url
from validation.vacancy import vacancy_decision

NUMERIC_PROPERTIES = {'lot_size_acres','assessed_value','market_value','tax_amount',
                      'tax_delinquent_years','year_acquired','latitude','longitude'}


def verify_property_snapshot(prop: dict, record: dict, cfg: dict) -> dict:
    def require(condition, message):
        if not condition: raise ValueError(message)
    raw = record.get('raw_payload')
    canonical = record.get('raw_payload_canonical')
    require(isinstance(raw,dict) and bool(raw) and isinstance(canonical,str), 'Canonical source snapshot is missing')
    try: decoded = json.loads(canonical)
    except (ValueError,TypeError): raise ValueError('Canonical source snapshot is malformed') from None
    require(decoded==json_safe(raw), 'Canonical source snapshot differs from its JSON payload')
    require(hashlib.sha256(canonical.encode()).hexdigest()==prop.get('source_payload_hash'), 'Source payload changed after the selected run')
    fingerprint = source_fingerprint(cfg)
    require(isinstance(record.get('field_mapping'),dict) and bool(record['field_mapping']), 'Source field mapping is missing')
    require(source_fingerprint({**cfg,'fields':record['field_mapping']})==fingerprint, 'Audit mapping differs from authorized source mapping')
    require(prop.get('source_fingerprint')==fingerprint, 'Property source fingerprint differs from the run')
    require(record.get('source_url')==prop.get('source_url')==source_url(cfg), 'Source URLs do not agree')
    normalized = normalize(raw,{**cfg,'fields':record['field_mapping']})
    normalized['source_url'] = source_url(cfg)
    require(source_identity(raw,cfg,normalized)==record.get('source_record_id')==prop.get('source_record_id'), 'Source identity cannot be reproduced')
    snapshot = record.get('normalized_payload')
    require(isinstance(snapshot,dict), 'Normalized source snapshot is missing')
    require(all(snapshot.get(key)==value for key,value in normalized.items() if not key.startswith('_')), 'Normalized snapshot differs from raw source data')
    county_id = cfg.get('county_id')
    require(record.get('county_id')==prop.get('county_id')==county_id, 'Cross-county provenance mismatch')
    accepted, reason = vacancy_decision(normalized,county_id,cfg)
    require(accepted, 'Persisted property lacks supported vacancy evidence')
    expected = property_payload({**normalized,'county_id':county_id,'_raw_payload':raw,
        '_source_record_id':record['source_record_id'],'source_fingerprint':fingerprint,
        'vacancy_status':'qualified','vacancy_evidence':{'reason':reason,'field_mapping':record['field_mapping']}})
    for field in PROPERTY_FIELDS:
        # Observing an unchanged property may legitimately update last_seen_at.
        # Hash the exact saved representation above, not reserialized JSONB.
        if field in {'last_seen_at','source_payload_hash'}: continue
        actual, wanted = prop.get(field), expected.get(field)
        if wanted is None:
            same = actual is None
        elif field in NUMERIC_PROPERTIES:
            same = number(actual)==number(wanted)
        elif field=='has_improvements':
            same = boolean(actual)==wanted
        else:
            same = actual==wanted
        require(same, 'Persisted property field differs from source: '+field)
    return normalized
