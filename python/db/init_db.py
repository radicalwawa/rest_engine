"""Initialize REST Engine SQLite database from schema.sql."""

import sqlite3
import sys
from pathlib import Path

DB_DIR = Path(__file__).parent
DB_PATH = DB_DIR / "rest_engine.db"
SCHEMA_PATH = DB_DIR / "schema.sql"


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create database and apply schema. Returns open connection."""
    if not SCHEMA_PATH.exists():
        print(f"FAIL: schema.sql not found at {SCHEMA_PATH}")
        sys.exit(1)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema_sql)
    conn.commit()
    print(f"OK: database created at {db_path}")
    return conn


if __name__ == "__main__":
    conn = init_db()
    # Verify tables
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables ({len(tables)}): {', '.join(tables)}")
    conn.close()
