"""Local-only SQLite backend; mirrors production's audit and publication contract."""
from __future__ import annotations
import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from persistence import (AuditRunNotFound, COMP_FIELDS, PUBLIC_COMP_FIELDS, DEAL_FIELDS, PROPERTY_FIELDS, PUBLIC_DEAL_FIELDS, PUBLIC_PROPERTY_FIELDS,
                         STATUS_MAP, audit_record, audit_records, deal_payload, now, property_payload, run_payload)

JSON_FIELDS = {'vacancy_evidence', 'financial_evidence', 'raw_payload', 'normalized_payload', 'field_mapping', 'metadata'}


def _encode(value):
    return json.dumps(value, allow_nan=False) if isinstance(value, (dict, list)) else value


def _row(row):
    if row is None: return None
    result = dict(row)
    for field in JSON_FIELDS:
        if field in result:
            try: result[field] = json.loads(result[field] or '{}')
            except (ValueError, TypeError): result[field] = {}
    return result


class SQLiteDatabase:
    def __init__(self, path_provider):
        self.path_provider = path_provider
        self._active: dict | None = None
        self.audit_failures: list[str] = []

    def get_connection(self):
        conn = sqlite3.connect(self.path_provider(), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    @contextmanager
    def connection(self):
        conn = self.get_connection()
        try:
            with conn: yield conn
        finally: conn.close()

    def init_db(self):
        with self.connection() as conn:
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS properties(id INTEGER PRIMARY KEY AUTOINCREMENT, apn TEXT NOT NULL, county_id TEXT NOT NULL REFERENCES counties(county_id), created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(apn,county_id));
            CREATE TABLE IF NOT EXISTS deals(id INTEGER PRIMARY KEY AUTOINCREMENT, property_id INTEGER NOT NULL REFERENCES properties(id), discovered_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS comps(id INTEGER PRIMARY KEY AUTOINCREMENT, deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS counties(county_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_properties_id_county ON properties(id,county_id);
            CREATE TABLE IF NOT EXISTS ingestion_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, run_key TEXT UNIQUE NOT NULL, county_id TEXT NOT NULL, run_type TEXT NOT NULL DEFAULT 'manual', source_url TEXT, started_at TEXT NOT NULL, heartbeat_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, records_seen INTEGER DEFAULT 0, records_normalized INTEGER DEFAULT 0, records_persisted INTEGER DEFAULT 0, records_rejected INTEGER DEFAULT 0, records_held INTEGER DEFAULT 0, records_skipped INTEGER DEFAULT 0, deals_persisted INTEGER DEFAULT 0, records_failed INTEGER DEFAULT 0, records_published INTEGER DEFAULT 0, error_message TEXT, metadata TEXT DEFAULT '{}', UNIQUE(id,county_id));
            CREATE TABLE IF NOT EXISTS ingestion_records(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, county_id TEXT NOT NULL, record_key TEXT NOT NULL, source_record_id TEXT, source_url TEXT, raw_payload TEXT, normalized_payload TEXT, field_mapping TEXT, property_id INTEGER, deal_id INTEGER REFERENCES deals(id), status TEXT NOT NULL, rejection_reason TEXT, hold_reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(run_id,county_id) REFERENCES ingestion_runs(id,county_id), FOREIGN KEY(property_id,county_id) REFERENCES properties(id,county_id), UNIQUE(run_id,record_key));
            CREATE TABLE IF NOT EXISTS subscribers(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, name TEXT, tier TEXT DEFAULT 'free', budget_min REAL, budget_max REAL, target_states TEXT, target_counties TEXT, min_profit REAL, joined_at TEXT DEFAULT CURRENT_TIMESTAMP, is_active INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY AUTOINCREMENT, subscriber_id INTEGER REFERENCES subscribers(id), deal_id INTEGER REFERENCES deals(id), delivered_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS waitlist(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, source TEXT, joined_at TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
            numeric = {'lot_size_acres','assessed_value','market_value','tax_amount','latitude','longitude','asking_price',
                       'estimated_arv_low','estimated_arv_high','estimated_costs','estimated_profit_low','estimated_profit_high',
                       'recommended_offer_low','recommended_offer_high','motivation_score','market_velocity','valuation_confidence',
                       'sale_price','distance_miles','price_per_acre'}
            integers = {'tax_delinquent_years','year_acquired','has_improvements','deal_score','ingestion_record_id','sale_qualified','vacant_at_sale','revision'}
            for table, fields in [('properties', PROPERTY_FIELDS), ('deals', (*DEAL_FIELDS,'revision')), ('comps', COMP_FIELDS), ('ingestion_records', ('raw_payload_canonical',)), ('subscribers', ('consented_at','unsubscribe_url'))]:
                existing = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}
                for field in fields:
                    if field not in existing:
                        definition = 'INTEGER REFERENCES ingestion_records(id)' if field == 'ingestion_record_id' else 'INTEGER NOT NULL DEFAULT 0' if field == 'revision' else 'REAL' if field in numeric else 'INTEGER' if field in integers else 'TEXT'
                        conn.execute(f'ALTER TABLE {table} ADD COLUMN {field} {definition}')
            conn.executescript('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_deals_one_per_property ON deals(property_id);
            CREATE INDEX IF NOT EXISTS idx_properties_county ON properties(county_id);
            CREATE INDEX IF NOT EXISTS idx_deals_status_score ON deals(status,verification_status,deal_score);
            CREATE INDEX IF NOT EXISTS idx_comps_deal ON comps(deal_id);
            CREATE INDEX IF NOT EXISTS idx_ingestion_records_property ON ingestion_records(property_id);
            CREATE TRIGGER IF NOT EXISTS deal_revision AFTER UPDATE ON deals WHEN NEW.revision = OLD.revision
            BEGIN UPDATE deals SET revision=OLD.revision+1 WHERE id=NEW.id; END;
            CREATE TRIGGER IF NOT EXISTS comp_insert_revoke AFTER INSERT ON comps
            BEGIN UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL WHERE id=NEW.deal_id; END;
            CREATE TRIGGER IF NOT EXISTS comp_update_revoke AFTER UPDATE ON comps
            BEGIN UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL WHERE id IN (OLD.deal_id,NEW.deal_id); END;
            CREATE TRIGGER IF NOT EXISTS comp_delete_revoke AFTER DELETE ON comps
            BEGIN UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL WHERE id=OLD.deal_id; END;
            DROP TRIGGER IF EXISTS audit_update_revoke;
            CREATE TRIGGER audit_update_revoke AFTER UPDATE ON ingestion_records
            WHEN NEW.raw_payload IS NOT OLD.raw_payload OR NEW.normalized_payload IS NOT OLD.normalized_payload
              OR NEW.raw_payload_canonical IS NOT OLD.raw_payload_canonical
              OR NEW.field_mapping IS NOT OLD.field_mapping OR NEW.property_id IS NOT OLD.property_id
              OR NEW.run_id IS NOT OLD.run_id OR NEW.county_id IS NOT OLD.county_id OR NEW.status IS NOT OLD.status
              OR NEW.source_url IS NOT OLD.source_url OR NEW.source_record_id IS NOT OLD.source_record_id
            BEGIN UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL
              WHERE ingestion_record_id=OLD.id OR id IN (SELECT deal_id FROM comps WHERE ingestion_record_id=OLD.id); END;
            CREATE TRIGGER IF NOT EXISTS run_update_revoke AFTER UPDATE ON ingestion_runs
            WHEN NEW.status IS NOT OLD.status OR NEW.metadata IS NOT OLD.metadata OR NEW.source_url IS NOT OLD.source_url
            BEGIN UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL
              WHERE ingestion_record_id IN (SELECT id FROM ingestion_records WHERE run_id=OLD.id); END;
            CREATE TRIGGER IF NOT EXISTS county_update_revoke AFTER UPDATE ON counties
            WHEN json_extract(NEW.payload,'$.ingestion_authorized') IS NOT json_extract(OLD.payload,'$.ingestion_authorized')
              OR json_extract(NEW.payload,'$.authorized_source_fingerprint') IS NOT json_extract(OLD.payload,'$.authorized_source_fingerprint')
              OR json_extract(NEW.payload,'$.validation_status') IS NOT json_extract(OLD.payload,'$.validation_status')
              OR json_extract(NEW.payload,'$.arcgis_layer_url') IS NOT json_extract(OLD.payload,'$.arcgis_layer_url')
              OR json_extract(NEW.payload,'$.field_mapping') IS NOT json_extract(OLD.payload,'$.field_mapping')
            BEGIN UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL
              WHERE property_id IN (SELECT id FROM properties WHERE county_id=NEW.county_id); END;
            DROP TRIGGER IF EXISTS county_validation_proof_revoke;
            CREATE TRIGGER county_validation_proof_revoke AFTER UPDATE ON counties
            WHEN json_extract(NEW.payload,'$.validation_source_fields_checked') IS NOT json_extract(OLD.payload,'$.validation_source_fields_checked')
              OR json_extract(NEW.payload,'$.validation_pagination_checked') IS NOT json_extract(OLD.payload,'$.validation_pagination_checked')
              OR json_extract(NEW.payload,'$.validation_sample_checked') IS NOT json_extract(OLD.payload,'$.validation_sample_checked')
              OR json_extract(NEW.payload,'$.last_validated_at') IS NOT json_extract(OLD.payload,'$.last_validated_at')
              OR json_extract(NEW.payload,'$.validated_source_fingerprint') IS NOT json_extract(OLD.payload,'$.validated_source_fingerprint')
            BEGIN UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL
              WHERE verification_status='verified' AND property_id IN (SELECT id FROM properties WHERE county_id=NEW.county_id); END;
            CREATE TRIGGER IF NOT EXISTS publication_guard BEFORE UPDATE ON deals
            WHEN NEW.verification_status='verified' AND (
              NEW.verified_at IS NULL OR NEW.verification_expires_at IS NULL OR julianday(NEW.verification_expires_at)<=julianday('now')
              OR NOT EXISTS(SELECT 1 FROM ingestion_records r JOIN ingestion_runs u ON u.id=r.run_id
                JOIN properties p ON p.id=r.property_id JOIN counties c ON c.county_id=p.county_id
                WHERE r.id=NEW.ingestion_record_id AND r.property_id=NEW.property_id AND r.county_id=p.county_id
                  AND u.status='completed' AND r.status='candidate' AND p.vacancy_status='qualified'
                  AND json_extract(c.payload,'$.ingestion_authorized')=1
                  AND json_extract(c.payload,'$.authorized_source_fingerprint')=p.source_fingerprint)
              OR (SELECT count(*) FROM comps WHERE deal_id=NEW.id AND ingestion_record_id IS NOT NULL)<3)
            BEGIN SELECT RAISE(ABORT,'Publication requires complete persisted evidence'); END;
            CREATE TRIGGER IF NOT EXISTS publication_insert_guard BEFORE INSERT ON deals
            WHEN NEW.verification_status='verified' AND (
              NEW.verified_at IS NULL OR NEW.verification_expires_at IS NULL OR julianday(NEW.verification_expires_at)<=julianday('now')
              OR NOT EXISTS(SELECT 1 FROM ingestion_records r JOIN ingestion_runs u ON u.id=r.run_id
                JOIN properties p ON p.id=r.property_id JOIN counties c ON c.county_id=p.county_id
                WHERE r.id=NEW.ingestion_record_id AND r.property_id=NEW.property_id AND r.county_id=p.county_id
                  AND u.status='completed' AND r.status='candidate' AND p.vacancy_status='qualified'
                  AND json_extract(c.payload,'$.ingestion_authorized')=1
                  AND json_extract(c.payload,'$.authorized_source_fingerprint')=p.source_fingerprint)
              OR (SELECT count(*) FROM comps WHERE deal_id=NEW.id AND ingestion_record_id IS NOT NULL)<3)
            BEGIN SELECT RAISE(ABORT,'Publication requires complete persisted evidence'); END;
            CREATE TRIGGER IF NOT EXISTS property_change_revokes_deals AFTER UPDATE ON properties
            WHEN NEW.source_payload_hash IS NOT OLD.source_payload_hash OR NEW.source_fingerprint IS NOT OLD.source_fingerprint
              OR NEW.vacancy_status IS NOT OLD.vacancy_status OR NEW.lot_size_acres IS NOT OLD.lot_size_acres
              OR NEW.has_improvements IS NOT OLD.has_improvements OR NEW.land_use IS NOT OLD.land_use
              OR NEW.source_url IS NOT OLD.source_url OR NEW.source_record_id IS NOT OLD.source_record_id
              OR NEW.latitude IS NOT OLD.latitude OR NEW.longitude IS NOT OLD.longitude
              OR NEW.vacancy_evidence IS NOT OLD.vacancy_evidence
            BEGIN UPDATE deals SET verification_status='pending_review', verified_at=NULL, verification_expires_at=NULL WHERE property_id=NEW.id; END;
            ''')

    def upsert_county(self, county):
        with self.connection() as conn:
            conn.execute('INSERT INTO counties(county_id,payload) VALUES(?,?) ON CONFLICT(county_id) DO UPDATE SET payload=excluded.payload', (county['county_id'], _encode(county)))

    def _upsert(self, conn, table, payload, conflict):
        fields = list(payload)
        columns = ','.join(fields)
        updates = ','.join(f'{field}=excluded.{field}' for field in fields if field not in conflict)
        sql = f'INSERT INTO {table} ({columns}) VALUES ({",".join("?" for _ in fields)}) ON CONFLICT({",".join(conflict)}) DO UPDATE SET {updates} RETURNING id'
        return int(conn.execute(sql, [_encode(payload[field]) for field in fields]).fetchone()['id'])

    def warn_audit(self, operation, exc):
        message = f'{operation}: {type(exc).__name__}'
        self.audit_failures.append(message)
        logging.getLogger(__name__).warning('Ingestion audit unavailable (%s); primary data retained', message)

    def save_property(self, data):
        payload = property_payload(data)
        payload['updated_at'] = now()
        with self.connection() as conn:
            conn.execute('INSERT INTO counties(county_id,payload) VALUES(?,?) ON CONFLICT(county_id) DO NOTHING',
                         (data['county_id'], _encode({'county_id':data['county_id'],'county_name':data.get('county_name') or data['county_id']})))
            property_id = self._upsert(conn, 'properties', payload, ['apn','county_id'])
        if not data.get('_defer_audit'):
            try:
                run_id = self.ensure_active_ingestion_run(data['county_id'], data.get('source_url'))
                self.record_ingestion_records(run_id, data['county_id'], [{'source_record_id': payload['source_record_id'],
                    'source_url': data.get('source_url'), 'raw_payload': data.get('_raw_payload'),
                    'normalized_payload': data, 'property_id': property_id, 'status': 'persisted'}])
            except Exception as exc:
                self.warn_audit('property_audit', exc); self.clear_active_run()
        return property_id

    def save_deal(self, data):
        payload = deal_payload(data); payload['updated_at'] = now()
        with self.connection() as conn:
            deal_id = self._upsert(conn, 'deals', payload, ['property_id'])
        if data.get('ingestion_record_id'):
            try:
                with self.connection() as conn:
                    conn.execute('UPDATE ingestion_records SET deal_id=? WHERE id=? AND property_id=?', (deal_id,data['ingestion_record_id'],data['property_id']))
            except Exception as exc: self.warn_audit('link_deal', exc)
        return deal_id

    def hold_deal_for_property(self, property_id):
        with self.connection() as conn:
            conn.execute("UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL WHERE property_id=?", (property_id,))

    def hold_deals_for_parcels(self, county_id, apns):
        with self.connection() as conn:
            for apn in set(apns):
                conn.execute("UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL WHERE property_id IN (SELECT id FROM properties WHERE county_id=? AND apn=?)", (county_id,apn))

    def hold_deal_for_parcel(self, county_id, apn):
        self.hold_deals_for_parcels(county_id, [apn])

    def save_comps(self, deal_id, comps):
        from validation.publication import validate_comp_payloads
        payloads = validate_comp_payloads(comps)
        with self.connection() as conn:
            conn.execute("UPDATE deals SET verification_status='pending_review',verified_at=NULL,verification_expires_at=NULL WHERE id=?", (deal_id,))
            conn.execute('DELETE FROM comps WHERE deal_id=?', (deal_id,))
            for comp in payloads:
                columns = ','.join(COMP_FIELDS)
                conn.execute(f'INSERT INTO comps(deal_id,{columns}) VALUES(?,{",".join("?" for _ in COMP_FIELDS)})',
                             [deal_id, *[_encode(comp.get(field)) for field in COMP_FIELDS]])
        return len(payloads)

    def get_deal_comps(self, deal_id):
        with self.connection() as conn:
            return [_row(row) for row in conn.execute('SELECT * FROM comps WHERE deal_id=? ORDER BY distance_miles', (deal_id,))]

    def get_top_deals(self, limit=10, min_score=40, county_id=None):
        columns = ','.join('p.' + field for field in PUBLIC_PROPERTY_FIELDS)
        deal_columns = ','.join('d.'+field for field in PUBLIC_DEAL_FIELDS)
        sql = f"SELECT {deal_columns},{columns} FROM deals d JOIN properties p ON d.property_id=p.id WHERE d.status='discovered' AND d.verification_status='verified' AND julianday(d.verification_expires_at)>julianday('now') AND d.deal_score>=?"
        args = [min_score]
        if county_id: sql += ' AND p.county_id=?'; args.append(county_id)
        sql += ' ORDER BY d.deal_score DESC,d.id LIMIT ?'; args.append(max(1,min(int(limit),100)))
        with self.connection() as conn:
            rows = [_row(row) for row in conn.execute(sql,args)]
            by_id = {row['id']: row for row in rows}
            for row in rows: row['comps'] = []
            if rows:
                for comp in conn.execute(f'SELECT * FROM comps WHERE deal_id IN ({",".join("?" for _ in rows)})', list(by_id)):
                    by_id[comp['deal_id']]['comps'].append({field:comp[field] for field in PUBLIC_COMP_FIELDS})
            return rows

    def record_ingestion_run(self, county_id, status, counts, error='', source_url=None, metadata=None, run_key=None):
        payload = run_payload(county_id,status,counts,error,metadata)
        payload.update(run_key=run_key or str(uuid.uuid4()),source_url=source_url,started_at=now())
        with self.connection() as conn:
            fields = list(payload)
            conn.execute(f'INSERT INTO ingestion_runs({",".join(fields)}) VALUES({",".join("?" for _ in fields)}) ON CONFLICT(run_key) DO NOTHING', [_encode(payload[field]) for field in fields])
            return int(conn.execute('SELECT id FROM ingestion_runs WHERE run_key=?',(payload['run_key'],)).fetchone()['id'])

    def update_ingestion_run(self, run_id, county_id, status, counts, error='', metadata=None):
        active = self._active if self._active and self._active['id'] == run_id and self._active['county_id'] == county_id else {}
        payload = run_payload(county_id,status,counts,error,{**active.get('metadata',{}),**(metadata or {})})
        with self.connection() as conn:
            fields = list(payload)
            changed = conn.execute(f'UPDATE ingestion_runs SET {",".join(field+"=?" for field in fields)} WHERE id=? AND county_id=? AND status=\'running\'', [*[_encode(payload[field]) for field in fields],run_id,county_id]).rowcount
            if not changed:
                row = conn.execute('SELECT status FROM ingestion_runs WHERE id=? AND county_id=?',(run_id,county_id)).fetchone()
                if not row: raise AuditRunNotFound('Active run not found')
                if row['status'] != STATUS_MAP[status]: raise RuntimeError('Run was already finalized with a different outcome')
        if status == 'running' and self._active: self._active['metadata'] = payload['metadata']
        if status != 'running': self.clear_active_run()
        return run_id

    def ensure_active_ingestion_run(self, county_id, source_url=None):
        if self._active and self._active['county_id'] == county_id and self._active['source_url'] == source_url:
            with self.connection() as conn:
                row = conn.execute("SELECT id FROM ingestion_runs WHERE id=? AND county_id=? AND status='running'", (self._active['id'],county_id)).fetchone()
                if row: return self._active['id']
        run_id = self.record_ingestion_run(county_id,'running',{},source_url=source_url)
        self._active = {'id':run_id,'county_id':county_id,'source_url':source_url,'metadata':{}}
        return run_id

    def active_run_id(self, county_id):
        return self._active['id'] if self._active and self._active['county_id'] == county_id else None

    def clear_active_run(self): self._active = None

    def record_ingestion_records(self, run_id, county_id, records):
        payloads = audit_records(run_id,county_id,records)
        with self.connection() as conn:
            for payload in payloads:
                payload['updated_at'] = now()
                self._upsert(conn,'ingestion_records',payload,['run_id','record_key'])
        return len(payloads)

    def get_ingestion_records(self, run_id, include_payloads=True):
        select = '*' if include_payloads else 'id,record_key,source_url,source_record_id,property_id'
        with self.connection() as conn:
            return [_row(row) for row in conn.execute(f'SELECT {select} FROM ingestion_records WHERE run_id=? ORDER BY id',(run_id,))]

    def get_deal_for_verification(self, deal_id):
        with self.connection() as conn:
            deal = _row(conn.execute('SELECT * FROM deals WHERE id=?',(deal_id,)).fetchone())
            if not deal: return None
            deal['properties'] = _row(conn.execute('SELECT * FROM properties WHERE id=?',(deal['property_id'],)).fetchone())
            deal['comps'] = self.get_deal_comps(deal_id)
            return deal

    def verify_deal(self, deal_id):
        from validation.publication import verify_persisted_deal
        deal = self.get_deal_for_verification(deal_id)
        if not deal: raise ValueError('Deal not found')
        with self.connection() as conn:
            record = _row(conn.execute('SELECT * FROM ingestion_records WHERE id=?',(deal.get('ingestion_record_id'),)).fetchone())
            if not record: raise ValueError('Deal has no persisted source audit')
            run = _row(conn.execute('SELECT * FROM ingestion_runs WHERE id=?',(record['run_id'],)).fetchone())
        result = verify_persisted_deal(deal,self.get_ingestion_records(run['id']),run)
        with self.connection() as conn:
            changed = conn.execute("UPDATE deals SET verification_status='verified',verified_at=?,verification_expires_at=? WHERE id=? AND revision=?", (now(),result['verification_expires_at'],deal_id,deal['revision'])).rowcount
            if not changed: raise RuntimeError('Deal changed during verification')
        return result

    def get_subscribers(self, tier=None):
        with self.connection() as conn:
            return [_row(row) for row in conn.execute('SELECT * FROM subscribers WHERE is_active=1 AND consented_at IS NOT NULL' + (' AND tier=?' if tier else ''), (tier,) if tier else ())]

    def add_waitlist_entry(self, email, source='unknown'):
        with self.connection() as conn:
            conn.execute('INSERT INTO waitlist(email,source) VALUES(?,?) ON CONFLICT(email) DO NOTHING', (email,source))
