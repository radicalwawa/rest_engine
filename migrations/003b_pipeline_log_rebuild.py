"""
pipeline_log entity_type CHECK -> 'notes' ekleme.
Tablo rebuild gerekli (SQLite ALTER ile CHECK degistirilemez).
"""
import sqlite3
import sys
import re

DB_PATH = "C:/Users/cettb/OneDrive/Masaüstü/rest_engine/rest_engine.db"

EXPECTED_TYPES = {'beat', 'track', 'album', 'daily_queue', 'prompt', 'upload', 'identity_v3', 'notes'}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1) Mevcut DDL
cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pipeline_log'")
row = cur.fetchone()
if not row:
    print("ERROR: pipeline_log table not found")
    sys.exit(1)
original_ddl = row[0]
print(f"Original DDL:\n{original_ddl}\n")

# 2) Index DDL
cur.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='pipeline_log' AND sql IS NOT NULL")
index_ddls = [r[0] for r in cur.fetchall()]
print(f"{len(index_ddls)} indexes found")

# 3) Row count
cur.execute("SELECT COUNT(*) FROM pipeline_log")
pre_count = cur.fetchone()[0]
print(f"Pre-count: {pre_count}")

# 4) Build new DDL with 'notes' in CHECK
pattern = r"(entity_type\s+TEXT\s+.*?CHECK\s*\(\s*entity_type\s+IN\s*\()([^)]+)(\))"
match = re.search(pattern, original_ddl, re.IGNORECASE | re.DOTALL)
if not match:
    print("ERROR: entity_type CHECK constraint not found")
    sys.exit(1)

existing_values = match.group(2)
if "'notes'" in existing_values:
    print("'notes' already present, nothing to do")
    sys.exit(0)

new_values = existing_values.rstrip() + ",'notes'"
new_ddl = original_ddl[:match.start(2)] + new_values + original_ddl[match.end(2):]
new_ddl = new_ddl.replace("CREATE TABLE pipeline_log", "CREATE TABLE pipeline_log_new", 1)

# Verify all 8 types present
for t in EXPECTED_TYPES:
    if f"'{t}'" not in new_ddl:
        print(f"ERROR: '{t}' not found in new DDL")
        sys.exit(1)
print("All 8 entity_type values verified")
print(f"\nNew DDL:\n{new_ddl}\n")

# 5) Rebuild in single transaction
try:
    cur.execute("PRAGMA foreign_keys=OFF")
    cur.execute("BEGIN")
    cur.execute(new_ddl)
    cur.execute("INSERT INTO pipeline_log_new SELECT * FROM pipeline_log")

    cur.execute("SELECT COUNT(*) FROM pipeline_log_new")
    new_count = cur.fetchone()[0]
    if new_count != pre_count:
        conn.rollback()
        print(f"ERROR: Row count mismatch - expected {pre_count}, got {new_count}")
        sys.exit(1)

    cur.execute("DROP TABLE pipeline_log")
    cur.execute("ALTER TABLE pipeline_log_new RENAME TO pipeline_log")

    for idx_ddl in index_ddls:
        cur.execute(idx_ddl)

    conn.commit()
    cur.execute("PRAGMA foreign_keys=ON")

    cur.execute("SELECT COUNT(*) FROM pipeline_log")
    final_count = cur.fetchone()[0]
    assert final_count == pre_count, f"Final check failed: {final_count} != {pre_count}"

    print(f"pipeline_log rebuilt: {pre_count} rows preserved, 8 allowed entity_types, {len(index_ddls)} indexes restored")

except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    conn.close()
