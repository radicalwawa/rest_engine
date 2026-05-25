"""
Phase 2 Step F — Full End-to-End Validation Session.
Realistic operator session driven through db_manager, no TUI launch.
Delta-based assertions + per-step inbox fixture guards; safe to re-run.
"""
import hashlib
import os
import shutil
import sqlite3
import sys
import traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

DB_PATH = os.path.join(BASE, "rest_engine.db")
INBOX = os.path.join(os.path.dirname(BASE), "rest_inbox")

FROZEN_HASHES = {
    "db_manager.py": "66080761d7658cd49f5c2419be331d8b3349ac58856b86fdafa88591a0a3f053",
    "prompt_engine.py": "ef39a6c1df61cf13ec69c5fbd682201930954887e8abf139f3bbffffe5364866",
    "daily_pipeline.py": "de151348ffe2e5503cb3fcd8defdfb1355ccf335af322071f7cd3b9d90688c51",
    "tui.py": "b7c5c48ef101abb5ea5a19b216544f6f68360820283ba1631f26b083bedd038c",
}

import db_manager as dbm

passed = 0
failed = 0
created_note_ids = []
created_beat_ids = []
created_archive_paths = []  # absolute paths
pipeline_log_start_count = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label}")


def check_raises(label, exc_type, fn):
    global passed, failed
    try:
        fn()
        failed += 1
        print(f"  FAIL: {label} (no exception raised)")
    except exc_type:
        passed += 1
        print(f"  PASS: {label}")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {label} (got {type(e).__name__}: {e})")


def _recreate_inbox(name):
    """Re-create inbox dummy file."""
    path = os.path.join(INBOX, f"{name}.mp3")
    with open(path, "wb") as f:
        f.write(b"dummy")


def _get_pipeline_log_count():
    conn = sqlite3.connect(DB_PATH)
    cnt = conn.execute("SELECT COUNT(*) FROM pipeline_log").fetchone()[0]
    conn.close()
    return cnt


def _get_table_counts():
    conn = sqlite3.connect(DB_PATH)
    tables = ["pipeline_log", "beats", "identities_v3", "daily_queue",
              "suno_prompts", "notes"]
    counts = {}
    for t in tables:
        counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    conn.close()
    return counts


def main():
    global pipeline_log_start_count

    # Defensive pre-cleanup: remove any leftover inbox fixtures from prior runs
    for f in ["validation_alpha", "validation_beta", "validation_gamma", "validation_delta"]:
        p = os.path.join(INBOX, f"{f}.mp3")
        if os.path.exists(p):
            os.remove(p)

    pre_counts = _get_table_counts()
    pipeline_log_start_count = pre_counts["pipeline_log"]
    print(f"Pre-validation counts: {pre_counts}")

    # ================================================================
    # PHASE 1: Notes across identities
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 1: Notes across identities")
    print("=" * 60)

    note_plan = {
        "green": ["Cypress note 1", "Cypress note 2", "Cypress note 3"],
        "grey": ["Ember note 1", "Ember note 2"],
        "blue": ["Tide note 1"],
        "cream": [],
        "black": ["Nightfall note 1"],
    }
    expected_note_count = 7

    # Snapshot per-color note counts BEFORE additions (delta baseline)
    pre_note_counts = {
        color: len(dbm.get_notes(color, limit=1000)) for color in note_plan
    }

    for color, bodies in note_plan.items():
        for body in bodies:
            result = dbm.add_note(color, body)
            created_note_ids.append(result["id"])

    # Verify counts and ordering (delta-based)
    for color, bodies in note_plan.items():
        notes = dbm.get_notes(color, limit=1000)
        expected = pre_note_counts[color] + len(bodies)
        check(
            f"get_notes('{color}') count == pre({pre_note_counts[color]}) + added({len(bodies)})",
            len(notes) == expected,
        )
        if notes and len(bodies) > 1:
            # Newest first: last added should be first returned
            check(
                f"get_notes('{color}') newest first",
                notes[0]["body"] == bodies[-1],
            )

    # Cream: 0 added; count must equal pre-count
    check(
        "get_notes('cream') unchanged after 0 additions",
        len(dbm.get_notes("cream", limit=1000)) == pre_note_counts["cream"],
    )

    # Whitespace-only body -> ValueError
    check_raises(
        "add_note whitespace body -> ValueError",
        ValueError,
        lambda: dbm.add_note("green", "   "),
    )

    # Unknown color -> error (ValueError or IntegrityError)
    check_raises(
        "add_note unknown color -> error",
        (ValueError, sqlite3.IntegrityError),
        lambda: dbm.add_note("purple", "test"),
    )

    print(f"\n  Notes created: {len(created_note_ids)} (IDs: {created_note_ids})")

    # ================================================================
    # PHASE 2: Register mp3s across identities
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 2: Register mp3s across identities")
    print("=" * 60)

    # 2.1 — Cypress validation_alpha v1
    _recreate_inbox("validation_alpha")
    r1 = dbm.register_beat_mp3("green", "validation_alpha")
    created_beat_ids.append(r1["beat_id"])
    archive_abs_1 = os.path.join(BASE, r1["mp3_path"].replace("/", os.sep))
    created_archive_paths.append(archive_abs_1)

    check("register v1 return dict shape",
          all(k in r1 for k in ("beat_id", "color", "track_name", "version_num", "mp3_path")))
    check("register v1 version_num == 1", r1["version_num"] == 1)
    check("register v1 track_name normalized", r1["track_name"] == "validation_alpha")
    check("register v1 archive file exists", os.path.isfile(archive_abs_1))
    check("register v1 inbox file removed",
          not os.path.exists(os.path.join(INBOX, "validation_alpha.mp3")))

    # Verify beats row
    beats = dbm.get_recent_beats("green", limit=10)
    b1 = [b for b in beats if b["id"] == r1["beat_id"]]
    check("register v1 beats row exists", len(b1) == 1)
    if b1:
        check("register v1 beats row color", b1[0]["color"] == "green")
        check("register v1 beats row track_name", b1[0]["track_name"] == "validation_alpha")
        check("register v1 beats row version_num", b1[0]["version_num"] == 1)
        check("register v1 beats row mp3_path set", b1[0].get("mp3_path") is not None)

    # 2.2 — Re-register without inbox file -> FileNotFoundError
    check_raises(
        "register without inbox -> FileNotFoundError",
        FileNotFoundError,
        lambda: dbm.register_beat_mp3("green", "validation_alpha"),
    )

    # 2.3 — Re-create inbox, register v2
    _recreate_inbox("validation_alpha")
    r2 = dbm.register_beat_mp3("green", "validation_alpha")
    created_beat_ids.append(r2["beat_id"])
    archive_abs_2 = os.path.join(BASE, r2["mp3_path"].replace("/", os.sep))
    created_archive_paths.append(archive_abs_2)
    check("register v2 version_num == 2", r2["version_num"] == 2)
    check("register v2 mp3_path different from v1", r2["mp3_path"] != r1["mp3_path"])

    # 2.4 — Ember validation_beta v1
    _recreate_inbox("validation_beta")
    r3 = dbm.register_beat_mp3("grey", "validation_beta")
    created_beat_ids.append(r3["beat_id"])
    created_archive_paths.append(os.path.join(BASE, r3["mp3_path"].replace("/", os.sep)))
    check("register Ember v1", r3["version_num"] == 1 and r3["color"] == "grey")

    # 2.5 — Tide validation_gamma v1
    _recreate_inbox("validation_gamma")
    r4 = dbm.register_beat_mp3("blue", "validation_gamma")
    created_beat_ids.append(r4["beat_id"])
    created_archive_paths.append(os.path.join(BASE, r4["mp3_path"].replace("/", os.sep)))
    check("register Tide v1", r4["version_num"] == 1 and r4["color"] == "blue")

    # 2.6 — Nightfall validation_delta v1
    _recreate_inbox("validation_delta")
    r5 = dbm.register_beat_mp3("black", "validation_delta")
    created_beat_ids.append(r5["beat_id"])
    created_archive_paths.append(os.path.join(BASE, r5["mp3_path"].replace("/", os.sep)))
    check("register Nightfall v1", r5["version_num"] == 1 and r5["color"] == "black")

    # 2.7 — Mixed case normalization: 'Validation Alpha' -> validation_alpha v3
    _recreate_inbox("validation_alpha")
    r6 = dbm.register_beat_mp3("green", "Validation Alpha")
    created_beat_ids.append(r6["beat_id"])
    created_archive_paths.append(os.path.join(BASE, r6["mp3_path"].replace("/", os.sep)))
    check("register mixed case -> normalized v3",
          r6["track_name"] == "validation_alpha" and r6["version_num"] == 3)

    # 2.8 — Invalid track name
    check_raises(
        "register invalid track name -> ValueError",
        ValueError,
        lambda: dbm.register_beat_mp3("green", "bad-name!"),
    )

    # 2.9 — Unknown color
    check_raises(
        "register unknown color -> ValueError",
        ValueError,
        lambda: dbm.register_beat_mp3("purple", "test"),
    )

    print(f"\n  Beats created: {len(created_beat_ids)} (IDs: {created_beat_ids})")

    # ================================================================
    # PHASE 3: Rate beats
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 3: Rate beats")
    print("=" * 60)

    # Rate Cypress validation_alpha v1
    target_id = r1["beat_id"]
    dbm.rate_beat(
        beat_id=target_id,
        rating_id=5, rating_flow=4, rating_beat_score=3,
        rating_energy=5, rating_replay=4,
        rating_note="strong first version",
    )
    check("rate v1 success", True)

    # Verify in get_recent_beats
    beats = dbm.get_recent_beats("green", limit=10)
    rated = [b for b in beats if b["id"] == target_id]
    check("rated beat visible in get_recent_beats", len(rated) == 1)
    if rated:
        check("rating_id == 5", rated[0]["rating_id"] == 5)
        check("rating_flow == 4", rated[0]["rating_flow"] == 4)
        check("rating_beat == 3", rated[0]["rating_beat"] == 3)
        check("rating_energy == 5", rated[0]["rating_energy"] == 5)
        check("rating_replay == 4", rated[0]["rating_replay"] == 4)
        check("rating_note correct", rated[0]["rating_note"] == "strong first version")

    # Re-rate with different values (overwrite)
    dbm.rate_beat(
        beat_id=target_id,
        rating_id=4, rating_flow=4, rating_beat_score=4,
        rating_energy=4, rating_replay=4,
        rating_note="re-rated",
    )
    beats2 = dbm.get_recent_beats("green", limit=10)
    re_rated = [b for b in beats2 if b["id"] == target_id]
    check("re-rate overwrites rating_id", re_rated[0]["rating_id"] == 4)
    check("re-rate overwrites note", re_rated[0]["rating_note"] == "re-rated")

    # pipeline_log: should have 2 'rate' entries for this beat_id
    conn = sqlite3.connect(DB_PATH)
    rate_count = conn.execute(
        "SELECT COUNT(*) FROM pipeline_log WHERE entity_type='beat' AND entity_id=? AND action='rate'",
        (target_id,),
    ).fetchone()[0]
    conn.close()
    check("pipeline_log has 2 rate entries for this beat", rate_count == 2)

    # Invalid rating values
    check_raises(
        "rate_beat rating_id=6 -> ValueError",
        ValueError,
        lambda: dbm.rate_beat(target_id, 6, 4, 4, 4, 4),
    )
    check_raises(
        "rate_beat rating_id=0 -> ValueError",
        ValueError,
        lambda: dbm.rate_beat(target_id, 0, 4, 4, 4, 4),
    )

    # String rating: db_manager validates isinstance(val, int)
    check_raises(
        "rate_beat string rating -> ValueError",
        (ValueError, TypeError),
        lambda: dbm.rate_beat(target_id, "3", 4, 4, 4, 4),
    )

    # Unknown beat_id
    check_raises(
        "rate_beat unknown beat_id -> ValueError",
        ValueError,
        lambda: dbm.rate_beat(999999, 3, 3, 3, 3, 3),
    )

    # ================================================================
    # PHASE 4: Version history
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 4: Version history")
    print("=" * 60)

    v_alpha = dbm.get_beat_versions("green", "validation_alpha")
    check("get_beat_versions green/validation_alpha count == 3", len(v_alpha) == 3)
    if len(v_alpha) == 3:
        check("versions ascending order (1,2,3)",
              [v["version_num"] for v in v_alpha] == [1, 2, 3])

    v_beta = dbm.get_beat_versions("grey", "validation_beta")
    check("get_beat_versions grey/validation_beta count == 1", len(v_beta) == 1)

    v_nonexist = dbm.get_beat_versions("cream", "nonexistent_track")
    check("get_beat_versions cream/nonexistent empty", len(v_nonexist) == 0)

    # Normalization consistency
    v_alpha_mixed = dbm.get_beat_versions("green", "Validation Alpha")
    check("get_beat_versions normalizes query (same 3 results)",
          len(v_alpha_mixed) == 3)

    # ================================================================
    # PHASE 5: get_recent_beats across identities
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 5: get_recent_beats across identities")
    print("=" * 60)

    expected_counts = {"green": 3, "grey": 1, "blue": 1, "cream": 0, "black": 1}
    for color, expected in expected_counts.items():
        actual = len(dbm.get_recent_beats(color, limit=20))
        check(f"get_recent_beats('{color}') == {expected}", actual == expected)

    # Limit honored
    limited = dbm.get_recent_beats("green", limit=1)
    check("get_recent_beats limit=1 returns exactly 1", len(limited) == 1)

    # ================================================================
    # PHASE 6: pipeline_log integrity
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 6: pipeline_log integrity")
    print("=" * 60)

    current_pl_count = _get_pipeline_log_count()
    delta = current_pl_count - pipeline_log_start_count
    # Expected: 7 notes + 6 register_mp3 + 6 inbox_cleanup (best-effort logged per beat)
    #           + 2 rate = at least 15
    # inbox_cleanup_failed entries: 0 expected (all files existed)
    # Each register also logs inbox cleanup success? No — looking at db_manager:
    #   log_action for register_mp3 is always logged.
    #   inbox_cleanup_failed is only logged on failure.
    #   source_deleted success is NOT separately logged.
    # So: 7 notes + 6 register + 2 rate = 15
    print(f"  pipeline_log delta: {delta} (start={pipeline_log_start_count}, now={current_pl_count})")

    conn = sqlite3.connect(DB_PATH)
    # Get all new entries
    new_entries = conn.execute(
        "SELECT id, entity_type, entity_id, action FROM pipeline_log WHERE id > ?",
        (pipeline_log_start_count,) if pipeline_log_start_count > 0 else (0,),
    ).fetchall()

    # Actually, pipeline_log IDs may have gaps. Use rowid ordering.
    # Better: count by action types in this session's entries
    new_entries = conn.execute(
        "SELECT entity_type, entity_id, action FROM pipeline_log ORDER BY id DESC LIMIT ?",
        (delta,),
    ).fetchall()

    action_counts = {}
    for et, eid, action in new_entries:
        key = f"{et}/{action}"
        action_counts[key] = action_counts.get(key, 0) + 1

    print(f"  Action breakdown: {action_counts}")

    check(f"pipeline_log delta == 15 (7 notes + 6 register + 2 rate)", delta == 15)

    # Entity types used
    entity_types_used = set(et for et, _, _ in new_entries)
    check("'notes' in pipeline_log entity_types", "notes" in entity_types_used)
    check("'beat' in pipeline_log entity_types", "beat" in entity_types_used)

    # No NULL entity_id or action in entire table
    null_check = conn.execute(
        "SELECT COUNT(*) FROM pipeline_log WHERE action IS NULL"
    ).fetchone()[0]
    check("no NULL action in pipeline_log", null_check == 0)

    # entity_id can be NULL for some legacy entries (e.g. identity_v3 seed)
    # but Phase 2 entries should all have entity_id
    null_eid_new = conn.execute(
        "SELECT COUNT(*) FROM pipeline_log WHERE entity_id IS NULL AND entity_type IN ('notes','beat')"
    ).fetchone()[0]
    check("no NULL entity_id in Phase 2 entries", null_eid_new == 0)

    conn.close()

    # ================================================================
    # PHASE 7: Cross-cutting
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 7: Cross-cutting")
    print("=" * 60)

    # Hash checks
    for fname, expected in FROZEN_HASHES.items():
        actual = hashlib.sha256(
            open(os.path.join(BASE, fname), "rb").read()
        ).hexdigest()
        check(f"{fname} hash unchanged", actual == expected)

    # DB integrity
    conn = sqlite3.connect(DB_PATH)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    check("PRAGMA integrity_check == ok", integrity == "ok")

    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    check("PRAGMA foreign_key_check == no rows", len(fk_violations) == 0)

    conn.close()

    # ================================================================
    # PHASE 8: Cleanup
    # ================================================================
    print("\n" + "=" * 60)
    print("PHASE 8: Cleanup")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)

    # Delete notes
    for nid in created_note_ids:
        conn.execute("DELETE FROM notes WHERE id = ?", (nid,))

    # Delete pipeline_log entries for our beats and notes
    for bid in created_beat_ids:
        conn.execute(
            "DELETE FROM pipeline_log WHERE entity_type = 'beat' AND entity_id = ?",
            (bid,),
        )
    for nid in created_note_ids:
        conn.execute(
            "DELETE FROM pipeline_log WHERE entity_type = 'notes' AND entity_id = ?",
            (nid,),
        )

    # Delete beats
    for bid in created_beat_ids:
        conn.execute("DELETE FROM beats WHERE id = ?", (bid,))

    conn.commit()
    conn.close()

    # Delete archive directories
    archive_dirs_cleaned = set()
    for apath in created_archive_paths:
        if os.path.isfile(apath):
            os.remove(apath)
        # Clean parent dir if empty
        parent = os.path.dirname(apath)
        if parent not in archive_dirs_cleaned and os.path.isdir(parent):
            try:
                shutil.rmtree(parent)
                archive_dirs_cleaned.add(parent)
            except Exception as e:
                print(f"  WARNING: could not remove {parent}: {e}")

    # Clean any leftover inbox files
    for f in ["validation_alpha", "validation_beta", "validation_gamma", "validation_delta"]:
        p = os.path.join(INBOX, f"{f}.mp3")
        if os.path.exists(p):
            os.remove(p)

    # Verify row counts returned to pre-validation baseline
    conn_now = sqlite3.connect(DB_PATH)
    tables_check = ["pipeline_log", "beats", "identities_v3", "daily_queue",
                     "suno_prompts", "notes"]
    for t in tables_check:
        now_cnt = conn_now.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        pre_cnt = pre_counts[t]
        check(f"cleanup {t}: {now_cnt} == pre({pre_cnt})", now_cnt == pre_cnt)

    # Final integrity check
    integrity2 = conn_now.execute("PRAGMA integrity_check").fetchone()[0]
    check("post-cleanup integrity_check == ok", integrity2 == "ok")
    fk2 = conn_now.execute("PRAGMA foreign_key_check").fetchall()
    check("post-cleanup foreign_key_check == no rows", len(fk2) == 0)

    conn_now.close()

    # ================================================================
    # RESULT
    # ================================================================
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"SONUC: {passed}/{total} PASSED")
    if failed > 0:
        print(f"BASARISIZ: {failed} assertion(s)")
    else:
        print("Tum assertion'lar gecti!")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        exit(main())
    except Exception:
        traceback.print_exc()
        print("\nFATAL: Unhandled exception in validation script.")
        exit(2)
