"""
Phase 2 Step B validation.
Checks: v3 section unchanged, frozen modules, new functions importable,
add_note/get_notes/rate_beat/get_recent_beats behavior.
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

V3_SECTION_HASH = "93ee2d9e7aab3b4ba3dae73337f9d03187b510b373a9e5b1059b4fb228dc5e78"

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


# --- 1) v3 section hash ---
print("\n[1] v3 section integrity")
with open(os.path.join(PROJECT, "db_manager.py"), "rb") as f:
    data = f.read()
lines = data.split(b"\n")
v3_hash = None
for i, line in enumerate(lines):
    if b"END v3 OPERATIONAL LAYER" in line:
        v3_bytes = b"\n".join(lines[: i + 2])
        v3_hash = hashlib.sha256(v3_bytes).hexdigest()
        break
check(v3_hash == V3_SECTION_HASH, "v3 section hash unchanged",
      f"got {v3_hash[:16]}..." if v3_hash else "marker not found")

# --- 2) Frozen module hashes ---
print("\n[2] Frozen module hashes")
for filename, expected in FROZEN_HASHES.items():
    filepath = os.path.join(PROJECT, filename)
    with open(filepath, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    check(actual == expected, f"{filename} hash unchanged",
          f"expected {expected[:16]}... got {actual[:16]}...")

# --- 3) Functions importable ---
print("\n[3] Functions importable from db_manager")
import db_manager as dm

for fn_name in ("add_note", "get_notes", "rate_beat", "get_recent_beats",
                "register_beat_mp3", "get_beat_versions"):
    check(callable(getattr(dm, fn_name, None)), f"{fn_name} is callable")

# --- 4) add_note + get_notes integration ---
print("\n[4] add_note + get_notes")
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON;")
conn.row_factory = sqlite3.Row

try:
    conn.execute("BEGIN")
    result = dm.add_note("grey", "validation test note", conn=conn)
    check(result["color"] == "grey", "add_note returns correct color")
    check(result["body"] == "validation test note", "add_note returns correct body")
    check("id" in result, "add_note returns id")
    check("created_at" in result, "add_note returns created_at")

    notes = dm.get_notes("grey", limit=1, conn=conn)
    check(len(notes) >= 1, "get_notes returns at least 1 note")
    check(notes[0]["body"] == "validation test note", "get_notes returns inserted note")
finally:
    conn.rollback()

# add_note with empty body
try:
    conn.execute("BEGIN")
    dm.add_note("grey", "   ", conn=conn)
    conn.rollback()
    fail("add_note rejects empty body")
except ValueError as e:
    conn.rollback()
    check("body cannot be empty" in str(e), "add_note rejects empty body")
except Exception as e:
    conn.rollback()
    fail("add_note rejects empty body", f"wrong exception: {type(e).__name__}")

# add_note with invalid color
try:
    conn.execute("BEGIN")
    dm.add_note("invalid_color", "test", conn=conn)
    conn.rollback()
    fail("add_note rejects invalid color")
except ValueError:
    conn.rollback()
    ok("add_note rejects invalid color")
except Exception as e:
    conn.rollback()
    fail("add_note rejects invalid color", f"wrong exception: {type(e).__name__}")

# --- 5) rate_beat ---
print("\n[5] rate_beat")

# Insert temp beat, rate it, verify
try:
    conn.execute("BEGIN")
    beat_id = dm.add_beat("grey", "validation prompt", conn=conn)

    result = dm.rate_beat(beat_id, 3, 4, 5, 2, 1, rating_note="test", conn=conn)
    check(result["beat_id"] == beat_id, "rate_beat returns correct beat_id")
    check(result["ratings"]["rating_id"] == 3, "rate_beat rating_id=3")
    check(result["ratings"]["rating_flow"] == 4, "rate_beat rating_flow=4")
    check(result["ratings"]["rating_beat"] == 5, "rate_beat rating_beat=5")
    check(result["ratings"]["rating_energy"] == 2, "rate_beat rating_energy=2")
    check(result["ratings"]["rating_replay"] == 1, "rate_beat rating_replay=1")
    check(result["rating_note"] == "test", "rate_beat rating_note correct")
finally:
    conn.rollback()

# rating=6 should raise ValueError
try:
    conn.execute("BEGIN")
    beat_id = dm.add_beat("grey", "validation prompt", conn=conn)
    dm.rate_beat(beat_id, 6, 4, 5, 2, 1, conn=conn)
    conn.rollback()
    fail("rate_beat rejects rating=6")
except ValueError as e:
    conn.rollback()
    check("must be 1..5" in str(e), "rate_beat rejects rating=6 with ValueError")
except Exception as e:
    conn.rollback()
    fail("rate_beat rejects rating=6", f"wrong exception: {type(e).__name__}: {e}")

# rating=0 should raise ValueError
try:
    conn.execute("BEGIN")
    beat_id = dm.add_beat("grey", "validation prompt", conn=conn)
    dm.rate_beat(beat_id, 0, 4, 5, 2, 1, conn=conn)
    conn.rollback()
    fail("rate_beat rejects rating=0")
except ValueError as e:
    conn.rollback()
    check("must be 1..5" in str(e), "rate_beat rejects rating=0 with ValueError")
except Exception as e:
    conn.rollback()
    fail("rate_beat rejects rating=0", f"wrong exception: {type(e).__name__}: {e}")

# beat not found
try:
    conn.execute("BEGIN")
    dm.rate_beat(999999, 3, 4, 5, 2, 1, conn=conn)
    conn.rollback()
    fail("rate_beat rejects nonexistent beat")
except ValueError as e:
    conn.rollback()
    check("beat not found" in str(e), "rate_beat rejects nonexistent beat")
except Exception as e:
    conn.rollback()
    fail("rate_beat rejects nonexistent beat", f"wrong exception: {type(e).__name__}: {e}")

# --- 6) get_recent_beats ---
print("\n[6] get_recent_beats")
try:
    conn.execute("BEGIN")
    beats = dm.get_recent_beats("grey", limit=5, conn=conn)
    check(isinstance(beats, list), "get_recent_beats returns list")
finally:
    conn.rollback()

# --- 7) register_beat_mp3 / get_beat_versions abort (real contract) ---
print("\n[7] register_beat_mp3 / get_beat_versions abort (expected)")
try:
    dm.register_beat_mp3("grey", "definitely_missing_xyz_nonexistent", conn=conn)
    fail("register_beat_mp3 abort fires")
except FileNotFoundError:
    ok("register_beat_mp3 raises FileNotFoundError when source missing")
except Exception as e:
    fail("register_beat_mp3 abort", f"wrong exception: {type(e).__name__}")

try:
    dm.get_beat_versions("not_a_color", "anything", conn=conn)
    fail("get_beat_versions abort fires")
except ValueError as e:
    check("unknown color" in str(e), "get_beat_versions raises ValueError on unknown color")
except Exception as e:
    fail("get_beat_versions abort", f"wrong exception: {type(e).__name__}")

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
