"""
daily_pipeline.py
REST ENGINE — Phase 1 Step 3 (MIRAS_20260320_v3).

Orchestrates the daily production cycle:
  - init_daily_queue(date)        : ensure 5 queue rows exist (one per color)
  - stage_prompts(date)           : generate + attach a suno_prompt to each pending row
  - process_queue_item(id, ...)   : mark a queue row 'generated' once Suno output arrives
                                    and create the corresponding beats row
  - review_beat(beat_id, ...)     : approve or reject, cascade queue row to done/skipped
  - get_today_status(date)        : summary of today's queue

All DB writes flow through db_manager. All prompt generation flows through
prompt_engine. No raw SQL in this module.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date as _date
from typing import Optional

import db_manager as dbm
import prompt_engine as pe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLORS = ("green", "grey", "blue", "cream", "black")

def _today() -> str:
    return _date.today().isoformat()


def _set_queue_prompt(queue_id: int, prompt_text: str) -> None:
    """Attach a staged suno_prompt to a pending queue row without changing status.
       Uses db_manager.update_queue_status keeping status='pending'."""
    dbm.update_queue_status(queue_id, "pending", suno_prompt=prompt_text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_daily_queue(queue_date: Optional[str] = None) -> dict:
    """Create the 5-row queue for the given date (default: today).
    Idempotent — re-runs leave existing rows alone."""
    queue_date = queue_date or _today()
    result = dbm.create_daily_queue(queue_date)
    queue = dbm.get_daily_queue(queue_date)
    return {
        "queue_date": queue_date,
        "newly_created": len(result["created"]),
        "total_rows": len(queue),
        "rows": queue,
    }


def stage_prompts(
    queue_date: Optional[str] = None,
    variation_type: str = "base",
    seed: Optional[int] = None,
    overwrite: bool = False,
) -> dict:
    """Generate a beat prompt per pending row and attach it to suno_prompt.

    Args:
        queue_date: target date (default today).
        variation_type: prompt_engine variation; one of VALID_VARIATIONS.
        seed: optional RNG seed; if set, each color gets seed + color-index
              so output is reproducible but still distinct per color.
        overwrite: if True, replace existing suno_prompt on pending rows.
                   if False, skip rows that already have one.
    """
    queue_date = queue_date or _today()
    rows = dbm.get_daily_queue(queue_date)
    if not rows:
        raise RuntimeError(
            f"no queue rows for {queue_date}; call init_daily_queue() first")

    staged = []
    skipped = []
    color_index = {c: i for i, c in enumerate(sorted(COLORS))}

    for row in rows:
        if row["status"] != "pending":
            skipped.append({"queue_id": row["id"], "color": row["color"],
                            "reason": f"status={row['status']}"})
            continue
        if row.get("suno_prompt") and not overwrite:
            skipped.append({"queue_id": row["id"], "color": row["color"],
                            "reason": "prompt already staged"})
            continue

        row_seed = (seed + color_index[row["color"]]) if seed is not None else None
        out = pe.generate_beat_prompt(
            color=row["color"],
            variation_type=variation_type,
            seed=row_seed,
            persist=True,   # log the template in suno_prompts
        )
        _set_queue_prompt(row["id"], out["style_prompt"])
        staged.append({
            "queue_id": row["id"],
            "color": row["color"],
            "prompt_id": out["prompt_id"],
            "variation_type": variation_type,
        })

    return {
        "queue_date": queue_date,
        "staged": staged,
        "skipped": skipped,
    }


def process_queue_item(
    queue_id: int,
    suno_url: str,
    bpm: Optional[int] = None,
    key_sig: Optional[str] = None,
    suno_audio_id: Optional[str] = None,
    duration_sec: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """Operator marks: Suno produced output for this queue row.
    Creates a beats row in status='generated', links it to the queue row,
    and advances queue status to 'generated'."""
    # We need the queue row to know color + staged prompt. Read via dbm.
    # No direct dbm.get_queue_item exists yet — fetch by date+filter.
    # Simpler: walk recent queue dates, find by id. To avoid full scan we
    # accept that callers pass a real queue_id and we look it up by scanning
    # today's and yesterday's queues (sufficient for daily cadence).
    target = None
    for d_offset in (0, 1, 2, 7):
        from datetime import timedelta
        d = (_date.today() - timedelta(days=d_offset)).isoformat()
        for row in dbm.get_daily_queue(d):
            if row["id"] == queue_id:
                target = row
                break
        if target:
            break
    if target is None:
        raise ValueError(f"queue_id {queue_id} not found in last 7 days")
    if target["status"] != "pending":
        raise ValueError(
            f"queue {queue_id} is in status {target['status']!r}, expected 'pending'")
    if not target.get("suno_prompt"):
        raise ValueError(
            f"queue {queue_id} has no staged suno_prompt; run stage_prompts() first")

    beat_id = dbm.add_beat(
        color=target["color"],
        suno_prompt=target["suno_prompt"],
        bpm=bpm,
        key_sig=key_sig,
        suno_url=suno_url,
        suno_audio_id=suno_audio_id,
        duration_sec=duration_sec,
        notes=notes,
        status="generated",
    )
    dbm.update_queue_status(queue_id, "generated", beat_id=beat_id)

    return {
        "queue_id": queue_id,
        "beat_id": beat_id,
        "color": target["color"],
        "status": "generated",
    }


def review_beat(
    beat_id: int,
    approved: bool,
    reason: Optional[str] = None,
) -> dict:
    """Approve or reject a beat. Cascades the queue row:
       approved → queue status='done'
       rejected → queue status='skipped' with skip_reason=reason."""
    beat = dbm.get_beat(beat_id)
    if beat is None:
        raise ValueError(f"beat {beat_id} not found")
    if beat["status"] not in ("generated", "reviewed", "pending"):
        raise ValueError(
            f"beat {beat_id} status {beat['status']!r} not reviewable")

    new_beat_status = "approved" if approved else "rejected"
    dbm.update_beat_status(beat_id, new_beat_status, reason=reason)

    # Find linked queue row (any date) and cascade.
    from datetime import timedelta
    cascaded_queue_id = None
    for d_offset in range(0, 14):
        d = (_date.today() - timedelta(days=d_offset)).isoformat()
        for row in dbm.get_daily_queue(d):
            if row.get("beat_id") == beat_id:
                cascaded_queue_id = row["id"]
                new_q_status = "done" if approved else "skipped"
                dbm.update_queue_status(
                    row["id"], new_q_status, skip_reason=reason if not approved else None)
                break
        if cascaded_queue_id is not None:
            break

    return {
        "beat_id": beat_id,
        "beat_status": new_beat_status,
        "queue_id": cascaded_queue_id,
        "approved": approved,
        "reason": reason,
    }


def get_today_status(queue_date: Optional[str] = None) -> dict:
    """Summary view of today's queue for dashboard/TUI consumption."""
    queue_date = queue_date or _today()
    rows = dbm.get_daily_queue(queue_date)
    by_status: dict = {}
    by_color: dict = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_color[r["color"]] = {
            "queue_id": r["id"],
            "status": r["status"],
            "beat_id": r.get("beat_id"),
            "has_prompt": bool(r.get("suno_prompt")),
            "skip_reason": r.get("skip_reason"),
        }
    return {
        "queue_date": queue_date,
        "total": len(rows),
        "by_status": by_status,
        "by_color": by_color,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    p = argparse.ArgumentParser(description="REST daily_pipeline runner")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create today's queue (5 pending rows)")
    p_init.add_argument("--date", default=None)

    p_stage = sub.add_parser("stage", help="stage suno prompts for pending rows")
    p_stage.add_argument("--date", default=None)
    p_stage.add_argument("--variation", default="base",
                         choices=pe.VALID_VARIATIONS)
    p_stage.add_argument("--seed", type=int, default=None)
    p_stage.add_argument("--overwrite", action="store_true")

    p_proc = sub.add_parser("process", help="mark a queue row as generated")
    p_proc.add_argument("--queue-id", type=int, required=True)
    p_proc.add_argument("--suno-url", required=True)
    p_proc.add_argument("--bpm", type=int, default=None)
    p_proc.add_argument("--key", default=None)
    p_proc.add_argument("--duration", type=int, default=None)
    p_proc.add_argument("--notes", default=None)

    p_rev = sub.add_parser("review", help="approve or reject a beat")
    p_rev.add_argument("--beat-id", type=int, required=True)
    g = p_rev.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--reject", action="store_true")
    p_rev.add_argument("--reason", default=None)

    p_st = sub.add_parser("status", help="show queue status for a date")
    p_st.add_argument("--date", default=None)

    args = p.parse_args()

    if args.cmd == "init":
        out = init_daily_queue(args.date)
    elif args.cmd == "stage":
        out = stage_prompts(args.date, variation_type=args.variation,
                            seed=args.seed, overwrite=args.overwrite)
    elif args.cmd == "process":
        out = process_queue_item(
            queue_id=args.queue_id, suno_url=args.suno_url,
            bpm=args.bpm, key_sig=args.key,
            duration_sec=args.duration, notes=args.notes)
    elif args.cmd == "review":
        out = review_beat(args.beat_id, approved=args.approve,
                          reason=args.reason)
    elif args.cmd == "status":
        out = get_today_status(args.date)
    else:
        raise SystemExit(2)

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    _cli()
