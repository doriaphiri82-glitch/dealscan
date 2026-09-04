"""DealScan database management."""
import sqlite3, os
from typing import List, Optional
from config.settings import DATABASE_PATH

def get_db_path():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True); return DATABASE_PATH

def get_connection():
    conn=sqlite3.connect(get_db_path()); conn.execute("PRAGMA foreign_keys=ON"); return conn

def init_db():
    conn=get_connection(); conn.executescript('''
    CREATE TABLE IF NOT EXISTS properties (id INTEGER PRIMARY KEY AUTOINCREMENT, apn TEXT NOT NULL, county_id TEXT NOT NULL, address TEXT, lot_size_acres REAL, assessed_value REAL, market_value REAL, owner_name TEXT, owner_address TEXT, owner_state TEXT, tax_amount REAL, tax_delinquent_years INTEGER DEFAULT 0, year_acquired INTEGER, zoning TEXT, land_use TEXT, has_improvements INTEGER DEFAULT 0, legal_description TEXT, latitude REAL, longitude REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(apn, county_id));
    CREATE TABLE IF NOT EXISTS deals (id INTEGER PRIMARY KEY AUTOINCREMENT, property_id INTEGER REFERENCES properties(id), deal_score INTEGER DEFAULT 0, asking_price REAL, estimated_arv_low REAL, estimated_arv_high REAL, estimated_costs REAL, estimated_profit_low REAL, estimated_profit_high REAL, recommended_offer_low REAL, recommended_offer_high REAL, motivation_signals TEXT, motivation_score REAL, market_velocity REAL, competition_level TEXT, status TEXT DEFAULT 'discovered', notes TEXT, source TEXT, source_url TEXT, source_vendor TEXT, source_quality TEXT, verification_status TEXT, data_freshness TEXT, valuation_basis TEXT, valuation_confidence REAL, discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, delivered_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS comps (id INTEGER PRIMARY KEY AUTOINCREMENT, deal_id INTEGER REFERENCES deals(id), address TEXT, sale_price REAL, sale_date TIMESTAMP, distance_miles REAL, lot_size_acres REAL, price_per_acre REAL);
    CREATE TABLE IF NOT EXISTS subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, name TEXT, tier TEXT DEFAULT 'free', budget_min REAL DEFAULT 5000, budget_max REAL DEFAULT 50000, target_states TEXT, target_counties TEXT, min_profit REAL DEFAULT 3000, joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS deliveries (id INTEGER PRIMARY KEY AUTOINCREMENT, subscriber_id INTEGER REFERENCES subscribers(id), deal_id INTEGER REFERENCES deals(id), delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS waitlist (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, source TEXT, joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_properties_county ON properties(county_id);
    CREATE INDEX IF NOT EXISTS idx_deals_status_score ON deals(status, deal_score DESC);
    CREATE INDEX IF NOT EXISTS idx_deals_property ON deals(property_id);
    CREATE INDEX IF NOT EXISTS idx_deals_county_score ON deals(property_id, deal_score DESC);
    ''')
    for column, definition in {
        'source_url':'TEXT','source_vendor':'TEXT','source_quality':'TEXT','verification_status':'TEXT',
        'data_freshness':'TEXT','valuation_basis':'TEXT','valuation_confidence':'REAL'
    }.items():
        try: conn.execute(f'ALTER TABLE deals ADD COLUMN {column} {definition}')
        except sqlite3.OperationalError: pass
    conn.commit(); conn.close()

def save_property(data: dict) -> int:
    conn=get_connection(); cur=conn.cursor()
    cur.execute('''INSERT INTO properties (apn,county_id,address,lot_size_acres,assessed_value,market_value,owner_name,owner_address,owner_state,tax_amount,tax_delinquent_years,year_acquired,zoning,land_use,has_improvements,legal_description,latitude,longitude,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(apn,county_id) DO UPDATE SET address=excluded.address,lot_size_acres=excluded.lot_size_acres,assessed_value=excluded.assessed_value,market_value=excluded.market_value,owner_name=excluded.owner_name,owner_address=excluded.owner_address,owner_state=excluded.owner_state,tax_amount=excluded.tax_amount,tax_delinquent_years=excluded.tax_delinquent_years,year_acquired=excluded.year_acquired,zoning=excluded.zoning,land_use=excluded.land_use,has_improvements=excluded.has_improvements,legal_description=excluded.legal_description,latitude=excluded.latitude,longitude=excluded.longitude,updated_at=CURRENT_TIMESTAMP''',(data['apn'],data['county_id'],data.get('address'),data.get('lot_size_acres'),data.get('assessed_value'),data.get('market_value'),data.get('owner_name'),data.get('owner_address'),data.get('owner_state'),data.get('tax_amount'),data.get('tax_delinquent_years',0),data.get('year_acquired'),data.get('zoning'),data.get('land_use'),int(data.get('has_improvements',False)),data.get('legal_description'),data.get('latitude'),data.get('longitude')))
    cur.execute('SELECT id FROM properties WHERE apn=? AND county_id=?',(data['apn'],data['county_id'])); row=cur.fetchone(); conn.commit(); conn.close(); return int(row[0])

def save_deal(data: dict) -> int:
    conn=get_connection(); cur=conn.cursor(); pid=data['property_id']
    cur.execute('SELECT id FROM deals WHERE property_id=? ORDER BY id DESC LIMIT 1',(pid,)); row=cur.fetchone()
    vals=(data.get('deal_score',0),data.get('asking_price'),data.get('estimated_arv_low'),data.get('estimated_arv_high'),data.get('estimated_costs'),data.get('estimated_profit_low'),data.get('estimated_profit_high'),data.get('recommended_offer_low'),data.get('recommended_offer_high'),data.get('motivation_signals',''),data.get('motivation_score',0),data.get('market_velocity',0),data.get('competition_level','low'),data.get('status','discovered'),data.get('notes',''),data.get('source',''),data.get('source_url'),data.get('source_vendor'),data.get('source_quality'),data.get('verification_status'),data.get('data_freshness'),data.get('valuation_basis'),data.get('valuation_confidence'))
    if row:
        cur.execute('''UPDATE deals SET deal_score=?,asking_price=?,estimated_arv_low=?,estimated_arv_high=?,estimated_costs=?,estimated_profit_low=?,estimated_profit_high=?,recommended_offer_low=?,recommended_offer_high=?,motivation_signals=?,motivation_score=?,market_velocity=?,competition_level=?,status=?,notes=?,source=?,source_url=?,source_vendor=?,source_quality=?,verification_status=?,data_freshness=?,valuation_basis=?,valuation_confidence=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',vals+(row[0],)); did=row[0]
    else:
        cur.execute('''INSERT INTO deals (property_id,deal_score,asking_price,estimated_arv_low,estimated_arv_high,estimated_costs,estimated_profit_low,estimated_profit_high,recommended_offer_low,recommended_offer_high,motivation_signals,motivation_score,market_velocity,competition_level,status,notes,source,source_url,source_vendor,source_quality,verification_status,data_freshness,valuation_basis,valuation_confidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(pid,)+vals); did=cur.lastrowid
    conn.commit(); conn.close(); return int(did)

def save_comps(deal_id: int, comps: List[dict]) -> int:
    """Persist only real source-derived comparable rows attached to a deal."""
    if not comps: return 0
    conn=get_connection(); cur=conn.cursor()
    cur.execute('DELETE FROM comps WHERE deal_id=?',(deal_id,))
    rows=[]
    for comp in comps:
        try:
            rows.append((deal_id, comp.get('address'), float(comp.get('sale_price')), comp.get('sale_date'), float(comp.get('distance_miles')), float(comp.get('lot_size_acres')), float(comp.get('price_per_acre'))))
        except (TypeError, ValueError):
            continue
    cur.executemany('INSERT INTO comps (deal_id,address,sale_price,sale_date,distance_miles,lot_size_acres,price_per_acre) VALUES (?,?,?,?,?,?,?)',rows)
    conn.commit(); conn.close(); return len(rows)

def get_deal_comps(deal_id: int) -> List[dict]:
    conn=get_connection(); conn.row_factory=sqlite3.Row; cur=conn.cursor()
    cur.execute('SELECT address,sale_price,sale_date,distance_miles,lot_size_acres,price_per_acre FROM comps WHERE deal_id=? ORDER BY distance_miles ASC',(deal_id,))
    out=[dict(r) for r in cur.fetchall()]; conn.close(); return out

def get_top_deals(limit=10,min_score=40,county_id: Optional[str]=None) -> List[dict]:
    conn=get_connection(); conn.row_factory=sqlite3.Row; cur=conn.cursor()
    sql='''SELECT d.*,p.apn,p.county_id,p.address,p.lot_size_acres,p.owner_name,p.owner_state,p.tax_delinquent_years,p.zoning FROM deals d JOIN properties p ON d.property_id=p.id WHERE d.status='discovered' AND d.deal_score>=?'''; args=[min_score]
    if county_id: sql+=' AND p.county_id=?'; args.append(county_id)
    sql+=' ORDER BY d.deal_score DESC LIMIT ?'; args.append(limit)
    cur.execute(sql,args); out=[dict(r) for r in cur.fetchall()]; conn.close(); return out

def get_subscribers(tier=None) -> List[dict]:
    conn=get_connection(); conn.row_factory=sqlite3.Row; cur=conn.cursor(); cur.execute('SELECT * FROM subscribers WHERE is_active=1'+(' AND tier=?' if tier else ''),((tier,) if tier else ())); out=[dict(r) for r in cur.fetchall()]; conn.close(); return out

def add_waitlist_entry(email:str,source:str='unknown'):
    conn=get_connection(); conn.execute('INSERT OR IGNORE INTO waitlist(email,source) VALUES (?,?)',(email,source)); conn.commit(); conn.close()

if __name__=='__main__': init_db()
