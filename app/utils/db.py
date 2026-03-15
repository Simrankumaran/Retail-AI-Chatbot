import os
import sqlite3
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = Path(__file__).resolve().parent.parent
_DB_REL = os.getenv("DB_PATH", "db/retail.db")
_DB_PATH = (_BASE_DIR.parent / _DB_REL).resolve()

if not _DB_PATH.exists():
    # If the parent directory doesn't exist, create it? 
    # Or assume the user has a db. rigid check previously.
    # We'll just stick to the previous behavior of checking existence, but maybe weak check.
    if not _DB_PATH.parent.exists():
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # raise FileNotFoundError(f"DB file not found at: {_DB_PATH}")

# Use thread-local storage for connections
_local_storage = threading.local()

def get_connection():
    if not hasattr(_local_storage, "connection"):
        # Connect to the DB for this thread
        _local_storage.connection = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        # Enable WAL mode for better concurrency
        try:
            _local_storage.connection.execute("PRAGMA journal_mode=WAL;")
        except:
            pass
    return _local_storage.connection

def get_cursor():
    return get_connection().cursor()

def close_connection():
    if hasattr(_local_storage, "connection"):
        try:
            _local_storage.connection.close()
        except:
            pass
        del _local_storage.connection

def init_db_schema():
    """Ensure schema migrations are applied."""
    # Create a fresh connection for migration to avoid interfering with thread locals roughly,
    # though it doesn't matter much for startup.
    conn = sqlite3.connect(str(_DB_PATH))
    cur = conn.cursor()
    
    try:
        cur.execute("PRAGMA table_info(products)")
        cols = [r[1] for r in cur.fetchall()]
        
        if "is_returnable" not in cols:
            print("Migrating: Adding is_returnable to products")
            cur.execute("ALTER TABLE products ADD COLUMN is_returnable INTEGER DEFAULT 1")
            
        if "return_window_days" not in cols:
            print("Migrating: Adding return_window_days to products")
            cur.execute("ALTER TABLE products ADD COLUMN return_window_days INTEGER DEFAULT 7")
            
        conn.commit()
    except Exception as e:
        print(f"Migration warning: {e}")
    finally:
        conn.close()
