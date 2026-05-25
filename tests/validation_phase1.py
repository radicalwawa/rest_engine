"""
tests/validation_phase1.py
End-to-end validation of REST v3 operational layer.
Exercises: db_manager + prompt_engine + daily_pipeline + uploads + tracks_v3.

Today-aligned date, idempotent teardown, delta-based assertions.
Re-runs cleanly: snapshots max(id) at start, deletes everything it created
in try/finally; defensive pre-teardown removes any leftover from prior crash.

Pass criteria:
  - 5 daily_queue rows created (one per color)
  - 5 prompts staged + 5 logged in suno_prompts (delta)
  - 5 beats created (process_queue_item for each)
  - 3 beats approved, 2 rejected
  - 3 tracks_v3 promoted from approved beats
  - 2 uploads created with full lifecycle (pending -> uploading -> live)
  - 1 upload marked failed (lifecycle pending -> failed)
  - pipeline_log captures every state change with correct entity_type/action
  - Foreign keys + status check constraints enforced
  - M2 tables untouched throughout
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db_manager as dbm
import prompt_engine as pe
import daily_pipeline as dp

DATE = date.today().isoformat()
DB = ROOT / "rest_engine.db"

# Tables this test mutates; teardown filters by snapshot max(id) per table
MUTATED_TABLES = ("uploads", "tracks_v3", "albums",
                  "daily_queue", "beats", "suno_prompts", "pipeline_log")

# ---------- helpers ----------

def expect(cond, msg):
    if not cond:
        raise AssertionError(f"FAIL: {msg}")
    print(f"  OK  {msg}")

def section(n, title):
    print(f"\n--- {n}. {title} ---")

def m2_snapshot():
    with sqlite3.connect(DB) as c:
        return {
            "identities":    c.execute("SELECT COUNT(*) FROM identities").fetchone()[0],
            "tracks":        c.execute("SELECT COUNT(*) FROM tracks").fetchone()[0],
            "sync_log":      c.execute("SELECT COUNT(*) FROM sync_log").fetchone()[0],
            "production_dna":c.execute("SELECT COUNT(*) FROM production_dna").fetchone()[0],
            "identities_v3": c.execute("SELECT COUNT(*) FROM identities_v3").fetchone()[0],
        }

def fail_expected(label, fn):
    try:
        fn()
    except Exception as e:
        print(f"  OK  {label} -> {type(e).__name__}: {e}")
        return
    raise AssertionError(f"FAIL: {label} did not raise")


def _snapshot_max_ids():
    """Return {table: max_id_or_0} for every table this test will mutate."""
    snap = {}
    with sqlite3.connect(DB) as c:
        for t in MUTATED_TABLES:
            row = c.execute(f"SELECT COALESCE(MAX(id), 0) FROM {t}").fetchone()
            snap[t] = row[0]
    return snap


def _cleanup_today_residue():
    """Remove any leftover rows for DATE from a prior failed run, FK-ordered."""
    with sqlite3.connect(DB) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        beat_ids = [
            r[0] for r in c.execute(
                "SELECT beat_id FROM daily_queue "
                "WHERE queue_date = ? AND beat_id IS NOT NULL",
                (DATE,),
            ).fetchall()
        ]
        if beat_ids:
            ph = ",".join("?" * len(beat_ids))
            track_ids = [r[0] for r in c.execute(
                f"SELECT id FROM tracks_v3 WHERE beat_id IN ({ph})", beat_ids
            ).fetchall()]
            if track_ids:
                tph = ",".join("?" * len(track_ids))
                c.execute(f"DELETE FROM uploads WHERE track_id IN ({tph})", track_ids)
                c.execute(f"DELETE FROM tracks_v3 WHERE id IN ({tph})", track_ids)
        c.execute("DELETE FROM daily_queue WHERE queue_date = ?", (DATE,))
        if beat_ids:
            ph = ",".join("?" * len(beat_ids))
            c.execute(f"DELETE FROM beats WHERE id IN ({ph})", beat_ids)
        c.commit()


def _cleanup_post_run(snap):
    """Delete anything this test created since snapshot, FK-ordered."""
    with sqlite3.connect(DB) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        # FK-safe order: uploads -> tracks_v3 -> albums -> daily_queue -> beats
        #                -> suno_prompts -> pipeline_log
        c.execute("DELETE FROM uploads      WHERE id > ?", (snap["uploads"],))
        c.execute("DELETE FROM tracks_v3    WHERE id > ?", (snap["tracks_v3"],))
        c.execute("DELETE FROM albums       WHERE id > ?", (snap["albums"],))
        c.execute("DELETE FROM daily_queue  WHERE id > ?", (snap["daily_queue"],))
        c.execute("DELETE FROM beats        WHERE id > ?", (snap["beats"],))
        c.execute("DELETE FROM suno_prompts WHERE id > ?", (snap["suno_prompts"],))
        c.execute("DELETE FROM pipeline_log WHERE id > ?", (snap["pipeline_log"],))
        c.commit()

# ---------- main cycle ----------

def main():
    print(f"REST v3 PHASE 1 VALIDATION — date={DATE}")
    print(f"DB: {DB}")

    # Defensive pre-cleanup: remove any leftover rows for today from prior crash
    _cleanup_today_residue()

    # Snapshot max ids of all tables this test mutates (for delta + teardown)
    snap = _snapshot_max_ids()
    print(f"\nsnapshot max ids: {snap}")

    baseline = m2_snapshot()
    print(f"baseline: {baseline}")

    try:
        section(1, "init_daily_queue")
        r1 = dp.init_daily_queue(DATE)
        expect(r1["total_rows"] == 5, "5 queue rows total")
        rows = dbm.get_daily_queue(DATE)
        colors = sorted(r["color"] for r in rows)
        expect(colors == ["black","blue","cream","green","grey"], "all 5 colors present")
        expect(all(r["status"] == "pending" for r in rows), "all rows pending")

        section(2, "stage_prompts")
        r2 = dp.stage_prompts(DATE, variation_type="base", seed=100)
        expect(len(r2["staged"]) == 5, "5 prompts staged")
        expect(len(r2["skipped"]) == 0, "0 skipped on first pass")
        rows = dbm.get_daily_queue(DATE)
        expect(all(r["suno_prompt"] for r in rows), "all rows have suno_prompt")
        with sqlite3.connect(DB) as c:
            sp_new = c.execute(
                "SELECT COUNT(*) FROM suno_prompts WHERE id > ?",
                (snap["suno_prompts"],),
            ).fetchone()[0]
        expect(sp_new == 5, "suno_prompts gained 5 new logged templates")

        section(3, "process_queue_item for all 5 colors")
        qmap = {r["color"]: r for r in dbm.get_daily_queue(DATE)}
        beat_ids = {}
        bpm_table = {"green":90, "grey":140, "blue":90, "cream":100, "black":150}
        for color, qrow in qmap.items():
            out = dp.process_queue_item(
                queue_id=qrow["id"],
                suno_url=f"https://suno.fake/{color}-{DATE}",
                bpm=bpm_table[color],
                key_sig="A minor",
                duration_sec=180,
            )
            beat_ids[color] = out["beat_id"]
        expect(len(beat_ids) == 5, "5 beats created")
        with sqlite3.connect(DB) as c:
            gen_beats = c.execute(
                "SELECT COUNT(*) FROM beats "
                "WHERE status='generated' AND id > ?",
                (snap["beats"],),
            ).fetchone()[0]
        expect(gen_beats == 5, "5 new beats in 'generated' status")
        rows = dbm.get_daily_queue(DATE)
        expect(all(r["status"] == "generated" for r in rows),
               "all queue rows now 'generated'")

        section(4, "review_beat: approve 3 (green, cream, black), reject 2 (grey, blue)")
        dp.review_beat(beat_ids["green"], approved=True)
        dp.review_beat(beat_ids["cream"], approved=True)
        dp.review_beat(beat_ids["black"], approved=True)
        dp.review_beat(beat_ids["grey"], approved=False, reason="kick too weak")
        dp.review_beat(beat_ids["blue"], approved=False, reason="too muddy")

        with sqlite3.connect(DB) as c:
            c.row_factory = sqlite3.Row
            approved = c.execute(
                "SELECT COUNT(*) FROM beats "
                "WHERE status='approved' AND id > ?",
                (snap["beats"],),
            ).fetchone()[0]
            rejected = c.execute(
                "SELECT COUNT(*) FROM beats "
                "WHERE status='rejected' AND id > ?",
                (snap["beats"],),
            ).fetchone()[0]
        expect(approved == 3, "3 new beats approved")
        expect(rejected == 2, "2 new beats rejected")

        status = dp.get_today_status(DATE)
        expect(status["by_status"].get("done") == 3, "3 queue rows done")
        expect(status["by_status"].get("skipped") == 2, "2 queue rows skipped")

        section(5, "tracks_v3: create album + promote 3 approved beats to tracks")
        album_id = dbm.add_album("cream", "Test Album 0", target_track_count=5)
        expect(isinstance(album_id, int) and album_id > 0, "album created")

        track_ids = {}
        for color in ("green", "cream", "black"):
            tid = dbm.add_track(
                color=color,
                title=f"{color} validation track",
                album_id=album_id if color == "cream" else None,
                beat_id=beat_ids[color],
                lyrics=f"placeholder lyrics for {color}",
                status="draft",
            )
            track_ids[color] = tid
        expect(len(track_ids) == 3, "3 tracks_v3 rows created")

        # advance track lifecycle
        dbm.update_track_status(track_ids["cream"], "generated")
        dbm.update_track_status(track_ids["cream"], "reviewed")
        dbm.update_track_status(track_ids["cream"], "approved")

        section(6, "uploads: 2 live + 1 failed")
        up_cream = dbm.add_upload(track_ids["cream"], platform="soundcloud",
                                  url="https://soundcloud.fake/cream")
        up_green = dbm.add_upload(track_ids["green"], platform="spotify",
                                  url="https://spotify.fake/green")
        up_black = dbm.add_upload(track_ids["black"], platform="youtube",
                                  url="https://youtube.fake/black")

        dbm.update_upload_status(up_cream, "uploading")
        dbm.update_upload_status(up_cream, "live")
        dbm.update_upload_status(up_green, "uploading")
        dbm.update_upload_status(up_green, "live")
        dbm.update_upload_status(up_black, "failed", error_message="api timeout")

        with sqlite3.connect(DB) as c:
            live = c.execute(
                "SELECT COUNT(*) FROM uploads "
                "WHERE upload_status='live' AND id > ?",
                (snap["uploads"],),
            ).fetchone()[0]
            failed = c.execute(
                "SELECT COUNT(*) FROM uploads "
                "WHERE upload_status='failed' AND id > ?",
                (snap["uploads"],),
            ).fetchone()[0]
            with_ts = c.execute(
                "SELECT COUNT(*) FROM uploads "
                "WHERE uploaded_at IS NOT NULL AND id > ?",
                (snap["uploads"],),
            ).fetchone()[0]
            err_msg = c.execute(
                "SELECT error_message FROM uploads WHERE id=?", (up_black,)).fetchone()[0]
        expect(live == 2, "2 new uploads live")
        expect(failed == 1, "1 new upload failed")
        expect(with_ts == 2, "live uploads have uploaded_at set")
        expect(err_msg == "api timeout", "failed upload has error_message")

        section(7, "pipeline_log audit (delta since snapshot)")
        with sqlite3.connect(DB) as c:
            c.row_factory = sqlite3.Row
            counts = {}
            for row in c.execute(
                "SELECT entity_type, action, COUNT(*) AS n FROM pipeline_log "
                "WHERE id > ? GROUP BY entity_type, action",
                (snap["pipeline_log"],),
            ):
                counts[(row["entity_type"], row["action"])] = row["n"]
        # Expected counts are ONLY this run's contribution (post-snapshot).
        # ('identity_v3','seed') intentionally omitted — those are historical.
        expected = {
            ("daily_queue","create"): 5,
            ("daily_queue","status_change"): 15,  # 5 stage attaches + 5 process + 5 review
            ("prompt","create"): 5,
            ("beat","create"): 5,
            ("beat","status_change"): 5,          # 5 reviews
            ("album","create"): 1,
            ("track","create"): 3,
            ("track","status_change"): 3,         # cream: generated, reviewed, approved
            ("upload","create"): 3,
            ("upload","status_change"): 5,        # cream:2, green:2, black:1
        }
        print("  counts observed (delta):")
        for k, v in sorted(counts.items()):
            print(f"    {k} = {v}")
        for k, want in expected.items():
            got = counts.get(k, 0)
            expect(got == want, f"pipeline_log[{k}] expected {want}, got {got}")

        section(8, "foreign key + constraint enforcement")
        fail_expected(
            "invalid color rejected",
            lambda: dbm.add_beat("purple", suno_prompt="x"))
        fail_expected(
            "invalid beat status rejected",
            lambda: dbm.add_beat("green", suno_prompt="x", status="exploding"))
        fail_expected(
            "invalid track status rejected",
            lambda: dbm.add_track("green", title="x", status="bogus"))
        fail_expected(
            "invalid upload status rejected",
            lambda: dbm.update_upload_status(up_cream, "vanished"))
        fail_expected(
            "review of nonexistent beat rejected",
            lambda: dp.review_beat(99999, approved=True))
        fail_expected(
            "process of nonexistent queue rejected",
            lambda: dp.process_queue_item(99999, suno_url="x"))

        # Foreign key: tracks_v3.album_id must reference albums.id
        with sqlite3.connect(DB) as c:
            c.execute("PRAGMA foreign_keys = ON;")
            try:
                c.execute("INSERT INTO tracks_v3 (color, album_id, title) "
                          "VALUES ('green', 99999, 'fk-test')")
                raise AssertionError("FAIL: FK violation not raised")
            except sqlite3.IntegrityError as e:
                print(f"  OK  FK violation raised: {e}")

        section(9, "M2 integrity")
        final = m2_snapshot()
        for k, v in baseline.items():
            expect(final[k] == v, f"{k} unchanged ({v})")

        section(10, "summary")
        final_counts = {}
        with sqlite3.connect(DB) as c:
            for t in ("identities_v3","albums","beats","tracks_v3",
                      "daily_queue","suno_prompts","uploads","pipeline_log"):
                final_counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(json.dumps(final_counts, indent=2))

        print("\nALL VALIDATION CHECKS PASSED.")
        return 0
    finally:
        # Always clean up what this test created, even on assertion failure
        _cleanup_post_run(snap)


if __name__ == "__main__":
    raise SystemExit(main())
