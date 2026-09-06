"""Explicit backend selection. SQLite is a local fallback, never production."""
import os
from pathlib import Path
from config.settings import DATABASE_PATH

_BACKEND_NAME = os.getenv('DEALSCAN_DB_BACKEND', 'sqlite').strip().lower()
if _BACKEND_NAME not in {'sqlite', 'supabase'}:
    raise RuntimeError('DEALSCAN_DB_BACKEND must be sqlite or supabase')
if os.getenv('DEALSCAN_ENV','').strip().lower() == 'production' and _BACKEND_NAME != 'supabase':
    raise RuntimeError('Production ingestion requires the Supabase backend')
_USE_SUPABASE = _BACKEND_NAME == 'supabase'


def get_db_path():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    return DATABASE_PATH


if _USE_SUPABASE:
    from database_supabase import SupabaseDatabase
    _backend = SupabaseDatabase()
    _supabase = _backend
else:
    from database_sqlite import SQLiteDatabase
    _backend = SQLiteDatabase(lambda: get_db_path())


def get_backend(): return _backend


def get_connection():
    if _USE_SUPABASE: raise RuntimeError('SQLite connections are unavailable in Supabase mode')
    return _backend.get_connection()


def init_db(): return _backend.init_db()
def sync_county(county): return _backend.upsert_county(county)
def save_property(data): return _backend.save_property(data)
def save_deal(data): return _backend.save_deal(data)
def save_comps(deal_id, comps): return _backend.save_comps(deal_id, comps)
def get_deal_comps(deal_id): return _backend.get_deal_comps(deal_id)
def get_top_deals(*args, **kwargs): return _backend.get_top_deals(*args, **kwargs)
def get_subscribers(tier=None): return _backend.get_subscribers(tier)
def add_waitlist_entry(email, source='unknown'): return _backend.add_waitlist_entry(email, source)
def verify_deal(deal_id): return _backend.verify_deal(deal_id)

if __name__ == '__main__': init_db()
