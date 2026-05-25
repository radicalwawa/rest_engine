"""
Phase 2 Step A - Schema Additions Validation
Row counts compared against frozen post-Phase-2 baseline (not pre-step_a snapshot).
"""
import sqlite3
import hashlib
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "rest_engine.db")

FROZEN_HASHES = {
    "db_manager.py": "66080761d7658cd49f5c2419be331d8b3349ac58856b86fdafa88591a0a3f053",
    "prompt_engine.py": "ef39a6c1df61cf13ec69c5fbd682201930954887e8abf139f3bbffffe5364866",
    "daily_pipeline.py": "de151348ffe2e5503cb3fcd8defdfb1355ccf335af322071f7cd3b9d90688c51",
}

EXPECTED_COUNTS = {
    "pipeline_log": 39,
    "beats": 0,
    "identities_v3": 5,
    "daily_queue": 5,
    "suno_prompts": 5,
}

PIPELINE_LOG_ALLOWED = [
    'beat', 'track', 'album', 'daily_queue', 'prompt', 'upload', 'identity_v3', 'notes'
]

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label}")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    # ── 1. notes tablosu var mı + kolon doğrulama ──
    print("\n[1] notes tablosu")
    cur.execute("PRAGMA table_info(notes)")
    cols = {r[1]: {"type": r[2], "notnull": r[3], "pk": r[5]} for r in cur.fetchall()}

    check("notes tablosu mevcut", len(cols) > 0)
    check("id: INTEGER PK", cols.get("id", {}).get("type") == "INTEGER" and cols.get("id", {}).get("pk") == 1)
    check("color: TEXT NOT NULL", cols.get("color", {}).get("type") == "TEXT" and cols.get("color", {}).get("notnull") == 1)
    check("body: TEXT NOT NULL", cols.get("body", {}).get("type") == "TEXT" and cols.get("body", {}).get("notnull") == 1)
    check("created_at: TEXT", cols.get("created_at", {}).get("type") == "TEXT")
    check("updated_at: TEXT", cols.get("updated_at", {}).get("type") == "TEXT")

    # FK kontrolü: geçersiz color INSERT dene
    try:
        conn.execute("INSERT INTO notes (color, body) VALUES ('nonexistent', 'test')")
        conn.rollback()
        check("notes FK -> identities_v3(color)", False)
    except sqlite3.IntegrityError:
        check("notes FK -> identities_v3(color)", True)

    # ── 2. idx_notes_color index var mı ──
    print("\n[2] idx_notes_color index")
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_notes_color'")
    check("idx_notes_color mevcut", cur.fetchone() is not None)

    # ── 3. beats 7 yeni kolon ──
    print("\n[3] beats yeni kolonlar")
    cur.execute("PRAGMA table_info(beats)")
    beat_cols = {r[1]: r[2] for r in cur.fetchall()}
    new_cols = ["rating_id", "rating_flow", "rating_beat", "rating_energy", "rating_replay", "rating_note", "mp3_path"]
    for col in new_cols:
        expected_type = "INTEGER" if col.startswith("rating_") and col != "rating_note" else "TEXT"
        check(f"beats.{col} ({expected_type})", col in beat_cols and beat_cols[col] == expected_type)

    # ── 4. beats rating CHECK constraint'leri ──
    print("\n[4] beats rating CHECK testleri")
    rating_cols = ["rating_id", "rating_flow", "rating_beat", "rating_energy", "rating_replay"]

    # Geçerli değer (3) testi
    try:
        conn.execute(
            "INSERT INTO beats (color, suno_prompt, status, rating_id) VALUES ('green', 'test', 'pending', 3)"
        )
        conn.rollback()
        check("rating_id=3 INSERT basarili", True)
    except Exception as e:
        check(f"rating_id=3 INSERT basarili ({e})", False)

    # Geçersiz değer testleri (6 ve 0)
    for col in rating_cols:
        for bad_val in [6, 0]:
            try:
                conn.execute(
                    f"INSERT INTO beats (color, suno_prompt, status, {col}) VALUES ('green', 'test', 'pending', {bad_val})"
                )
                conn.rollback()
                check(f"{col}={bad_val} IntegrityError", False)
            except sqlite3.IntegrityError:
                check(f"{col}={bad_val} IntegrityError", True)

    # ── 5. pipeline_log entity_type='notes' kabul ──
    print("\n[5] pipeline_log entity_type testleri")
    try:
        conn.execute(
            "INSERT INTO pipeline_log (entity_type, action) VALUES ('notes', 'test')"
        )
        conn.rollback()
        check("entity_type='notes' INSERT basarili", True)
    except Exception as e:
        check(f"entity_type='notes' INSERT basarili ({e})", False)

    # ── 6. pipeline_log mevcut entity_type'lar hala gecerli (regresyon) ──
    print("\n[6] pipeline_log regresyon - mevcut entity_type'lar")
    for et in PIPELINE_LOG_ALLOWED:
        try:
            conn.execute(
                "INSERT INTO pipeline_log (entity_type, action) VALUES (?, 'regression_test')", (et,)
            )
            conn.rollback()
            check(f"entity_type='{et}' hala gecerli", True)
        except Exception as e:
            check(f"entity_type='{et}' hala gecerli ({e})", False)

    # ── 7. pipeline_log geçersiz entity_type reddi ──
    print("\n[7] pipeline_log gecersiz entity_type")
    try:
        conn.execute(
            "INSERT INTO pipeline_log (entity_type, action) VALUES ('__bogus__', 'test')"
        )
        conn.rollback()
        check("entity_type='__bogus__' IntegrityError", False)
    except sqlite3.IntegrityError:
        check("entity_type='__bogus__' IntegrityError", True)

    # ── 8. Row count'lar frozen post-Phase-2 baseline ile eslesme ──
    print("\n[8] Row count eslesmesi (frozen baseline vs current)")
    for tbl, expected in EXPECTED_COUNTS.items():
        actual = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        check(f"{tbl} count == {expected} (actual {actual})", actual == expected)

    # ── 9. Frozen modüller SHA-256 hash kontrolü ──
    print("\n[9] Frozen modul hash kontrolu")
    for fname, expected_hash in FROZEN_HASHES.items():
        fpath = os.path.join(BASE, fname)
        actual_hash = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        check(f"{fname} hash eslesiyor", actual_hash == expected_hash)

    conn.close()

    # ── Sonuç ──
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"SONUC: {passed}/{total} PASSED")
    if failed > 0:
        print(f"BASARISIZ: {failed} assertion")
    else:
        print("Tum assertion'lar gecti!")
    print(f"{'='*50}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
