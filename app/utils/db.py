import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = Path(__file__).resolve().parent.parent
_DB_REL = os.getenv("DB_PATH", "db/retail.db")
_DB_PATH = (_BASE_DIR.parent / _DB_REL).resolve()

if not _DB_PATH.exists():
    raise FileNotFoundError(f"DB file not found at: {_DB_PATH}")

_CONN = sqlite3.connect(str(_DB_PATH), check_same_thread=False)


def get_cursor():
    return _CONN.cursor()
