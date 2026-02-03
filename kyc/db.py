import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.sqlite3"

print("DB_PATH =", DB_PATH)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS verification_sessions (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        status TEXT NOT NULL,
        current_step INTEGER NOT NULL,

        front_image TEXT,
        back_image TEXT,
        selfie_image TEXT,

        liveness_running INTEGER DEFAULT 0,
        liveness_completed INTEGER DEFAULT 0,
        liveness_verified INTEGER DEFAULT 0,
        liveness_confidence REAL DEFAULT 0,

        verify_verified INTEGER DEFAULT 0,
        verify_confidence REAL DEFAULT 0,
        verify_similarity REAL DEFAULT 0,

        user_agent TEXT,
        ip_address TEXT
    );
    """)
    conn.commit()
    conn.close()
