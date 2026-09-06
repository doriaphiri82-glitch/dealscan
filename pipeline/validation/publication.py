"""Verify persisted financial calculations against persisted source records."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from normalization import boolean, normalize, number, sale_date, source_identity, source_value
from persistence import COMP_FIELDS, json_safe
from validation.gates import authorization_error, source_fingerprint
from validation.vacancy import vacancy_decision
from validation.evidence import verify_property_snapshot
import hashlib
import json
from scoring.deal_scorer import MODEL_VERSION, _distance_miles, score_and_enrich_deal


def validate_comp_payloads(comps: list[dict]) -> list[dict]:
    if not isinstance(comps, list) or len(comps) > 100:
        raise ValueError('Invalid comparable collection')
    out, seen = [], set()
    for comp in comps:
        if not isinstance(comp, dict): raise ValueError('Comparable must be an object')
        url = urlsplit(str(comp.get('source_url') or ''))
        identity = (comp.get('source_url'), str(comp.get('source_record_id') or ''))
        if url.scheme not in {'https','http'} or not url.hostname or url.username or url.password or not identity[1]:
            raise ValueError('Comparable requires source URL and record identity')
        if identity in seen: raise ValueError('Duplicate comparable identity')
        seen.add(identity)
        price, acres, distance = (number(comp.get(key)) for key in ('sale_price','lot_size_acres','distance_miles'))
        date = sale_date(comp.get('sale_date'))
        if price is None or price <= 0 or acres is None or acres <= 0 or distance is None or distance < 0 or date is None:
            raise ValueError('Invalid comparable sale, size, distance or date')
        payload = {key: comp.get(key) for key in COMP_FIELDS}
        payload.update(sale_price=price, lot_size_acres=acres, distance_miles=distance,
                       sale_date=date.isoformat(), price_per_acre=price/acres, source_record_id=identity[1],
                       sale_qualified=boolean(comp.get('sale_qualified')), vacant_at_sale=boolean(comp.get('vacant_at_sale')))
        out.append(payload)
    return out


def verify_persisted_deal(deal: dict, records: list[dict], run: dict) -> dict:
    def require(condition, message):
        if not condition: raise ValueError(message)
    prop = deal.get('properties') or {}
    metadata = run.get('metadata') or {}
    cfg = metadata.get('source_config') or {}
    fingerprint = source_fingerprint(cfg)
    require(run.get('status') == 'completed' and not metadata.get('audit_gap'), 'Ingestion did not complete with intact audit')
    require(not authorization_error(metadata.get('source_authorization') or {}, cfg), 'Source authorization is incomplete or expired')
    require(fingerprint == metadata.get('source_fingerprint') == metadata.get('authorized_source_fingerprint') == prop.get('source_fingerprint'), 'Source authorization provenance mismatch')
    require(sale_date(metadata.get('source_validated_at')) == sale_date((metadata.get('source_authorization') or {}).get('last_validated_at')), 'Source validation timestamps do not agree')
    by_id = {record['id']: record for record in records}
    record = by_id.get(deal.get('ingestion_record_id')) or {}
    require(record and record.get('status') == 'candidate' and record.get('property_id') == deal.get('property_id') and record.get('county_id') == prop.get('county_id'), 'Deal source record does not match its property')
    require(record.get('source_url') == run.get('source_url') == deal.get('source_url') == prop.get('source_url') and record.get('source_record_id'), 'Source URL or identity is missing/mismatched')
    normalized = verify_property_snapshot(prop,record,cfg)
    raw = record['raw_payload']
    require(prop.get('vacancy_status') == 'qualified' and vacancy_decision(normalized, prop.get('county_id'), cfg)[0], 'Property vacancy is unverified')
    asking_field = normalized['_field_sources'].get('asking_price')
    require(asking_field and number(source_value(raw, asking_field)) == number(deal.get('asking_price')), 'Asking price is not backed by the raw source field')
    # Re-normalization, rather than trusting a previously enriched JSON document,
    # proves the actual raw financial and sale-qualification fields still agree.
    for key, value in normalized.items():
        if not key.startswith('_'):
            require((record.get('normalized_payload') or {}).get(key) == value, f'Normalized audit field differs from source: {key}')
    evidence = deal.get('financial_evidence') or {}
    require(evidence.get('model_version') == deal.get('valuation_model') == MODEL_VERSION and deal.get('asking_price_basis') == 'source', 'Financial model evidence is missing')
    comps = validate_comp_payloads(deal.get('comps') or [])
    for stored_comp,comp in zip(deal.get('comps') or [],comps):
        actual_ppa=number(stored_comp.get('price_per_acre'))
        require(actual_ppa is not None and abs(actual_ppa-comp['price_per_acre'])<=.011, 'Comparable price per acre differs from its sale facts')
        source = by_id.get(comp.get('ingestion_record_id')) or {}
        require(source and source.get('county_id') == comp.get('county_id') == prop.get('county_id') and source.get('source_url') == comp.get('source_url') and source.get('source_record_id') == comp.get('source_record_id'), 'Comparable lacks matching persisted provenance')
        require(source.get('status') in {'held','candidate','persisted'} and source.get('hold_reason') != 'duplicate_county_apn', 'Comparable source identity was rejected or ambiguous')
        require(source.get('id') != record.get('id') and comp.get('source_apn') != prop.get('apn'), 'A property cannot be its own comparable')
        canonical=source.get('raw_payload_canonical')
        require(isinstance(canonical,str) and json.loads(canonical)==json_safe(source.get('raw_payload')), 'Comparable raw source snapshot is missing or inconsistent')
        require(source_fingerprint({**cfg,'fields':source.get('field_mapping') or {}})==fingerprint, 'Comparable mapping differs from authorized source mapping')
        mapped = normalize(source.get('raw_payload') or {}, {**cfg, 'fields': source.get('field_mapping') or {}})
        require(source_identity(source.get('raw_payload') or {}, cfg, mapped) == comp.get('source_record_id'), 'Comparable identity cannot be reproduced')
        require(mapped.get('apn') == comp.get('source_apn') and mapped.get('sale_qualified') is True and mapped.get('vacant_at_sale') is True, 'Comparable sale/vacancy qualification is not source-backed')
        require(mapped.get('last_sale_price') == comp['sale_price'] and mapped.get('lot_size_acres') == comp['lot_size_acres'] and sale_date(mapped.get('last_sale_date')) == sale_date(comp['sale_date']), 'Comparable values differ from source records')
        coordinates = [number(row.get(key)) for row in (normalized,mapped) for key in ('latitude','longitude')]
        require(all(value is not None for value in coordinates), 'Comparable distance has no source coordinates')
        require(abs(_distance_miles(*coordinates)-comp['distance_miles']) <= .02, 'Comparable distance is not reproducible')
    recalculated = score_and_enrich_deal(normalized, comps, cfg)
    require(recalculated is not None and len(recalculated['comps']) == len(comps), 'Persisted deal does not meet evidence/qualification requirements')
    for field in ('estimated_arv_low','estimated_arv_high','estimated_costs','estimated_profit_low','estimated_profit_high','recommended_offer_low','recommended_offer_high','deal_score','valuation_confidence'):
        actual, expected = number(deal.get(field)), number(recalculated.get(field))
        require(actual is not None and expected is not None and abs(actual-expected) <= .01, 'Financial calculation does not match persisted evidence')
    require(evidence == recalculated['financial_evidence'] and deal.get('valuation_basis') == recalculated['valuation_basis'], 'Financial evidence changed after scoring')
    return {'deal_id': deal['id'], 'property_id': deal['property_id'], 'run_id': run['id'],
            'verification_status': 'verified', 'valuation_model': MODEL_VERSION, 'comparable_count': len(comps),
            'verification_expires_at': min(sale_date(metadata['source_validated_at']) + timedelta(days=7), datetime.now(timezone.utc)+timedelta(days=7), min(sale_date(comp['sale_date']) for comp in comps)+timedelta(days=1095)).isoformat()}
