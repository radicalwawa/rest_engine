"""
Phase 2 Step A.2 validation.
Checks: new beats columns, indexes, constraints, row counts, frozen hashes.
Row counts rebaselined to post-phase2 frozen state (not pre-step_a2 snapshot).
"""
import hashlib
import os
import sqlite3
import sys

PROJECT = "C:/Users/cettb/OneDrive/Masaüstü/rest_engine"
DB_PATH = os.path.join(PROJECT, "rest_engine.db")

FROZEN_HASHES = {
    "db_manager.py":     "66080761d7658cd49f5c2419be331d8b3349ac58856b86fdafa88591a0a3f053",
    "prompt_engine.py":  "ef39a6c1df61cf13ec69c5fbd682201930954887e8abf139f3bbffffe5364866",
    "daily_pipeline.py": "de151348ffe2e5503cb3fcd8defdfb1355ccf335af322071f7cd3b9d90688c51",
}

EXPECTED_COUNTS = {
    "beats": 0,
    "pipeline_log": 39,
    "identities_v3": 5,
    "daily_queue": 5,
    "suno_prompts": 5,
    "notes": 14,
}

passed = 0
failed = 0


def ok(desc):
    global passed
    passed += 1
    print(f"  PASS: {desc}")


def fail(desc, detail=""):
    global failed
    failed += 1
    msg = f"  FAIL: {desc}"
    if detail:
        msg += f" -- {detail}"
    print(msg)


def check(condition, desc, detail=""):
    if condition:
        ok(desc)
    else:
        fail(desc, detail)


# Use a separate temp DB for insert constraint tests to avoid polluting production
TEMP_DB = os.path.join(PROJECT, "_test_a2_temp.db")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys=ON")
cur = conn.cursor()

# --- 1) New columns exist ---
print("\n[1] beats new columns")
cur.execute("PRAGMA table_info(beats)")
cols = {row[1]: row for row in cur.fetchall()}

check("track_name" in cols, "beats.track_name exists")
if "track_name" in cols:
    check(cols["track_name"][2] == "TEXT", "beats.track_name type is TEXT",
          f"got {cols['track_name'][2]}")
    check(cols["track_name"][3] == 0, "beats.track_name is nullable",
          f"notnull={cols['track_name'][3]}")

check("version_num" in cols, "beats.version_num exists")
if "version_num" in cols:
    check(cols["version_num"][2] == "INTEGER", "beats.version_num type is INTEGER",
          f"got {cols['version_num'][2]}")
    check(cols["version_num"][3] == 0, "beats.version_num is nullable",
          f"notnull={cols['version_num'][3]}")

# --- 2) Indexes exist ---
print("\n[2] Indexes")
cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='beats' AND name='idx_beats_color_track'")
check(cur.fetchone() is not None, "idx_beats_color_track exists")

cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name='idx_beats_color_track_version_uniq'")
row = cur.fetchone()
check(row is not None, "idx_beats_color_track_version_uniq exists")
if row:
    idx_sql = row[1]
    check("UNIQUE" in idx_sql.upper(), "idx is UNIQUE", idx_sql)
    check("WHERE track_name IS NOT NULL" in idx_sql, "idx is partial (WHERE track_name IS NOT NULL)",
          idx_sql)

# --- 3) Constraint tests (use production DB with rollback) ---
print("\n[3] Constraint tests")

# version_num=0 should raise IntegrityError
try:
    cur.execute("BEGIN")
    cur.execute("INSERT INTO beats (color, suno_prompt, version_num) VALUES ('grey', '__test__', 0)")
    conn.rollback()
    fail("version_num=0 rejected")
except sqlite3.IntegrityError:
    conn.rollback()
    ok("version_num=0 rejected (IntegrityError)")
except Exception as e:
    conn.rollback()
    fail("version_num=0 rejected", f"wrong exception: {type(e).__name__}: {e}")

# version_num=-1 should raise IntegrityError
try:
    cur.execute("BEGIN")
    cur.execute("INSERT INTO beats (color, suno_prompt, version_num) VALUES ('grey', '__test__', -1)")
    conn.rollback()
    fail("version_num=-1 rejected")
except sqlite3.IntegrityError:
    conn.rollback()
    ok("version_num=-1 rejected (IntegrityError)")
except Exception as e:
    conn.rollback()
    fail("version_num=-1 rejected", f"wrong exception: {type(e).__name__}: {e}")

# version_num=1 should succeed
try:
    cur.execute("BEGIN")
    cur.execute("INSERT INTO beats (color, suno_prompt, version_num) VALUES ('grey', '__test__', 1)")
    ok("version_num=1 accepted")
    conn.rollback()
except Exception as e:
    conn.rollback()
    fail("version_num=1 accepted", str(e))

# Duplicate (color, track_name, version_num) where track_name NOT NULL -> IntegrityError
try:
    cur.execute("BEGIN")
    cur.execute("INSERT INTO beats (color, suno_prompt, track_name, version_num) VALUES ('grey', '__test1__', 'test_track', 1)")
    cur.execute("INSERT INTO beats (color, suno_prompt, track_name, version_num) VALUES ('grey', '__test2__', 'test_track', 1)")
    conn.rollback()
    fail("duplicate (color, track_name, version_num) rejected")
except sqlite3.IntegrityError:
    conn.rollback()
    ok("duplicate (color, track_name, version_num) rejected (IntegrityError)")
except Exception as e:
    conn.rollback()
    fail("duplicate (color, track_name, version_num) rejected", f"wrong exception: {type(e).__name__}: {e}")

# Two rows with NULL track_name, same version_num -> both succeed
try:
    cur.execute("BEGIN")
    cur.execute("INSERT INTO beats (color, suno_prompt, track_name, version_num) VALUES ('grey', '__test1__', NULL, 1)")
    cur.execute("INSERT INTO beats (color, suno_prompt, track_name, version_num) VALUES ('grey', '__test2__', NULL, 1)")
    ok("two NULL track_name rows with same version_num both accepted")
    conn.rollback()
except Exception as e:
    conn.rollback()
    fail("two NULL track_name rows accepted", str(e))

# --- 4) Row counts match frozen post-Phase-2 baseline ---
print("\n[4] Row count comparison with frozen baseline")
for tbl, expected in EXPECTED_COUNTS.items():
    try:
        live_count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        check(live_count == expected, f"{tbl} row count == {expected} (live {live_count})",
              f"expected={expected} live={live_count}")
    except Exception as e:
        fail(f"{tbl} row count", str(e))

# --- 5) Frozen module hashes ---
print("\n[5] Frozen module SHA-256")
for filename, expected in FROZEN_HASHES.items():
    filepath = os.path.join(PROJECT, filename)
    with open(filepath, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    check(actual == expected, f"{filename} hash unchanged",
          f"expected {expected[:16]}... got {actual[:16]}...")

conn.close()

# --- Summary ---
total = passed + failed
print(f"\n{'=' * 40}")
print(f"{passed}/{total} pass")
if failed:
    print(f"{failed} FAILED")
    sys.exit(1)
else:
    print("All assertions passed")
