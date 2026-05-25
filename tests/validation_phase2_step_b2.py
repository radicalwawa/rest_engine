"""
Phase 2 Step B continuation validation.
Checks: register_beat_mp3, get_beat_versions, _normalize_track_name,
frozen hashes, row count integrity.
"""
import hashlib
import os
import sqlite3
import sys

PROJECT = "C:/Users/cettb/OneDrive/Masaüstü/rest_engine"
DB_PATH = os.path.join(PROJECT, "rest_engine.db")
sys.path.insert(0, PROJECT)

FROZEN_HASHES = {
    "prompt_engine.py": "ef39a6c1df61cf13ec69c5fbd682201930954887e8abf139f3bbffffe5364866",
    "daily_pipeline.py": "de151348ffe2e5503cb3fcd8defdfb1355ccf335af322071f7cd3b9d90688c51",
}
V3_PREFIX_HASH = "99acd9c6cd14bb45c16ee05dbd315600c417ca963dd6dfc2ccf07388e8124434"

COUNT_TABLES = ["beats", "pipeline_log", "notes", "identities_v3", "daily_queue", "suno_prompts"]

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
        if "STOP" in desc:
            sys.exit(1)


import db_manager as dm

# Capture row counts BEFORE any tests
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys=ON")
conn.row_factory = sqlite3.Row
pre_counts = {}
for tbl in COUNT_TABLES:
    pre_counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]

# --- 1) Functions importable ---
print("\n[1] Functions importable")
check(callable(getattr(dm, "register_beat_mp3", None)), "register_beat_mp3 callable")
check(callable(getattr(dm, "get_beat_versions", None)), "get_beat_versions callable")

# --- 2) _normalize_track_name ---
print("\n[2] _normalize_track_name")
ntn = dm._normalize_track_name

check(ntn("My Track") == "my_track", "My Track -> my_track", f"got {ntn('My Track')}")
check(ntn("  hello  world  ") == "hello_world", "hello world -> hello_world",
      f"got {ntn('  hello  world  ')}")
check(ntn("already_ok") == "already_ok", "already_ok -> already_ok")

try:
    ntn("bad-name!")
    fail("bad-name! raises ValueError")
except ValueError:
    ok("bad-name! raises ValueError")

try:
    ntn("")
    fail("empty string raises ValueError")
except ValueError:
    ok("empty string raises ValueError")

try:
    ntn("   ")
    fail("whitespace-only raises ValueError")
except ValueError:
    ok("whitespace-only raises ValueError")

# --- 3) register_beat_mp3 error cases ---
print("\n[3] register_beat_mp3 error cases")

try:
    dm.register_beat_mp3("invalid_color_xyz", "test", conn=conn)
    fail("unknown color raises ValueError")
except ValueError:
    ok("unknown color raises ValueError")

try:
    dm.register_beat_mp3("grey", "nonexistent_file_xyz", conn=conn)
    fail("missing source raises FileNotFoundError")
except FileNotFoundError:
    ok("missing source raises FileNotFoundError")

# --- 4) Full happy path ---
print("\n[4] register_beat_mp3 happy path (v1)")
INBOX_DIR = r"C:\Users\cettb\OneDrive\Masaüstü\rest_inbox"
os.makedirs(INBOX_DIR, exist_ok=True)
inbox_path = os.path.join(INBOX_DIR, "validation_test.mp3")

# Create test mp3
with open(inbox_path, "wb") as f:
    f.write(b"test")

result = dm.register_beat_mp3("grey", "validation_test", conn=conn)
beat_id_v1 = result["beat_id"]

check(result["color"] == "grey", "return color correct")
check(result["track_name"] == "validation_test", "return track_name correct")
check(result["version_num"] == 1, "return version_num == 1", f"got {result['version_num']}")
check("mp3_path" in result, "return has mp3_path")
check("source_deleted" in result, "return has source_deleted")
check(result["source_deleted"] is True, "inbox file deleted")

# Verify archive file
archive_abs = os.path.join(PROJECT, result["mp3_path"].replace("/", os.sep))
check(os.path.isfile(archive_abs), "archive file exists", archive_abs)
check(not os.path.isfile(inbox_path), "inbox file gone")

# Verify beats row
row = conn.execute("SELECT * FROM beats WHERE id = ?", (beat_id_v1,)).fetchone()
check(row is not None, "beats row exists")
if row:
    check(row["track_name"] == "validation_test", "beats.track_name correct")
    check(row["version_num"] == 1, "beats.version_num == 1")
    check(row["mp3_path"] == result["mp3_path"], "beats.mp3_path correct")

# Verify pipeline_log
plog = conn.execute(
    "SELECT * FROM pipeline_log WHERE entity_type='beat' AND entity_id=? AND action='register_mp3'",
    (beat_id_v1,)
).fetchone()
check(plog is not None, "pipeline_log register_mp3 entry exists")

# --- 5) Version increment (v2) ---
print("\n[5] Version increment (v2)")
with open(inbox_path, "wb") as f:
    f.write(b"test_v2")

result_v2 = dm.register_beat_mp3("grey", "validation_test", conn=conn)
beat_id_v2 = result_v2["beat_id"]

check(result_v2["version_num"] == 2, "v2 version_num == 2", f"got {result_v2['version_num']}")

archive_abs_v2 = os.path.join(PROJECT, result_v2["mp3_path"].replace("/", os.sep))
check(os.path.isfile(archive_abs_v2), "archive v2 file exists")

# --- 6) get_beat_versions (before UNIQUE test which may rollback) ---
print("\n[6] get_beat_versions")
versions = dm.get_beat_versions("grey", "validation_test", conn=conn)
check(len(versions) == 2, "get_beat_versions returns 2 rows", f"got {len(versions)}")
if len(versions) == 2:
    check(versions[0]["version_num"] == 1, "first version is v1")
    check(versions[1]["version_num"] == 2, "second version is v2")

# --- 7) UNIQUE constraint (use savepoint to avoid rolling back test data) ---
print("\n[7] UNIQUE constraint (color, track_name, version_num)")
try:
    conn.execute("SAVEPOINT sp_unique_test")
    conn.execute(
        "INSERT INTO beats (color, suno_prompt, track_name, version_num) "
        "VALUES ('grey', '', 'validation_test', 1)"
    )
    conn.execute("RELEASE sp_unique_test")
    fail("duplicate (color, track_name, version_num) raises IntegrityError")
except sqlite3.IntegrityError:
    conn.execute("ROLLBACK TO sp_unique_test")
    conn.execute("RELEASE sp_unique_test")
    ok("duplicate (color, track_name, version_num) raises IntegrityError")

# --- Cleanup ---
print("\n[cleanup]")
# Delete beats rows
conn.execute("DELETE FROM beats WHERE id = ?", (beat_id_v1,))
conn.execute("DELETE FROM beats WHERE id = ?", (beat_id_v2,))
# Delete pipeline_log rows
conn.execute("DELETE FROM pipeline_log WHERE entity_type='beat' AND entity_id IN (?, ?)",
             (beat_id_v1, beat_id_v2))
conn.commit()

# Remove archive files
for apath in [archive_abs, archive_abs_v2]:
    if os.path.isfile(apath):
        os.remove(apath)
# Remove archive dirs (best-effort)
for apath in [archive_abs_v2, archive_abs]:
    try:
        os.removedirs(os.path.dirname(apath))
    except OSError:
        pass

# --- 8) SHA-256 checks ---
print("\n[8] Frozen module hashes")
for filename, expected in FROZEN_HASHES.items():
    filepath = os.path.join(PROJECT, filename)
    with open(filepath, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    check(actual == expected, f"{filename} hash unchanged",
          f"expected {expected[:16]}... got {actual[:16]}...")

# v3 prefix of db_manager.py
with open(os.path.join(PROJECT, "db_manager.py"), "rb") as f:
    data = f.read()
lines = data.split(b"\n")
for i, line in enumerate(lines):
    if b"PHASE 2 OPERATIONAL LAYER (M5)" in line:
        prefix = b"\n".join(lines[: i - 1])
        h = hashlib.sha256(prefix).hexdigest()
        check(h == V3_PREFIX_HASH, "db_manager.py v3 prefix hash unchanged",
              f"expected {V3_PREFIX_HASH[:16]}... got {h[:16]}...")
        break

# --- 9) Row counts unchanged ---
print("\n[9] Row counts unchanged after cleanup")
for tbl in COUNT_TABLES:
    post = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    check(post == pre_counts[tbl], f"{tbl} row count unchanged ({post})",
          f"before={pre_counts[tbl]} after={post}")

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
