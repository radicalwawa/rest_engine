"""CRUD query functions for REST Engine SQLite database."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "rest_engine.db"


def _conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- Tracks ---

def get_all_tracks(db_path: Path = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute("SELECT * FROM tracks ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_track_by_id(track_id: str, db_path: Path = DB_PATH) -> Optional[dict]:
    conn = _conn(db_path)
    row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tracks_by_color(color: str, db_path: Path = DB_PATH) -> list[dict]:
    """Get tracks matching a color (e.g. 'grey' matches 'radical.grey')."""
    pattern = f"radical.{color}" if not color.startswith("radical.") else color
    conn = _conn(db_path)
    rows = conn.execute("SELECT * FROM tracks WHERE id = ?", (pattern,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Identities ---

def get_identity(track_id: str, db_path: Path = DB_PATH) -> Optional[dict]:
    conn = _conn(db_path)
    row = conn.execute("SELECT * FROM identities WHERE track_id = ?", (track_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for k in ("genre_stack", "fx_policy", "vocal_delivery", "mix_targets", "suno_prompt_guidelines"):
        if d.get(k):
            d[k] = json.loads(d[k])
    return d


# --- Works ---

def get_works(db_path: Path = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute("SELECT * FROM works ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_works_by_track(track_id: str, db_path: Path = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute(
        "SELECT * FROM works WHERE track_id = ? ORDER BY created_at", (track_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Scores ---

def add_score(
    work_id: str, mix: int, vocal: int, color: int, flow: int, replay: int,
    notes: Optional[str] = None, db_path: Path = DB_PATH
) -> int:
    """Insert a score row. Returns score_id."""
    conn = _conn(db_path)
    cursor = conn.execute(
        """INSERT INTO scores (work_id, mix, vocal, color, flow, replay, notes)
           VALUES (?,?,?,?,?,?,?)""",
        (work_id, mix, vocal, color, flow, replay, notes),
    )
    conn.commit()
    score_id = cursor.lastrowid
    conn.close()
    return score_id


def get_scores_by_work(work_id: str, db_path: Path = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute(
        "SELECT * FROM scores WHERE work_id = ? ORDER BY scored_at", (work_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Audio Files ---

def add_audio_file(
    work_id: str, file_path: str, file_type: str,
    suno_ref: Optional[str] = None, version_tag: Optional[str] = None,
    notes: Optional[str] = None, db_path: Path = DB_PATH
) -> int:
    """Insert an audio file record. Returns file_id."""
    conn = _conn(db_path)
    cursor = conn.execute(
        """INSERT INTO audio_files (work_id, file_path, file_type, suno_ref, version_tag, notes)
           VALUES (?,?,?,?,?,?)""",
        (work_id, file_path, file_type, suno_ref, version_tag, notes),
    )
    conn.commit()
    file_id = cursor.lastrowid
    conn.close()
    return file_id


def get_audio_files_by_work(work_id: str, db_path: Path = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute(
        "SELECT * FROM audio_files WHERE work_id = ? ORDER BY created_at", (work_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Sound Library ---

def get_sound_assets_by_color(color_state: str, db_path: Path = DB_PATH) -> list[dict]:
    pattern = f"radical.{color_state}" if not color_state.startswith("radical.") else color_state
    conn = _conn(db_path)
    rows = conn.execute(
        "SELECT * FROM sound_library WHERE color_state = ? ORDER BY role", (pattern,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sound_asset(asset_id: str, db_path: Path = DB_PATH) -> Optional[dict]:
    conn = _conn(db_path)
    row = conn.execute("SELECT * FROM sound_library WHERE id = ?", (asset_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Prompts ---

def add_prompt(
    track_id: str, prompt_text: str, variation: str,
    seed_hash_hex: Optional[str] = None, notes: Optional[str] = None,
    db_path: Path = DB_PATH
) -> int:
    conn = _conn(db_path)
    cursor = conn.execute(
        """INSERT INTO prompts (track_id, prompt_text, variation, seed_hash_hex, notes)
           VALUES (?,?,?,?,?)""",
        (track_id, prompt_text, variation, seed_hash_hex, notes),
    )
    conn.commit()
    prompt_id = cursor.lastrowid
    conn.close()
    return prompt_id


# --- Lyrics ---

def add_lyrics(
    work_id: str, track_id: str, content: str,
    bar_count: Optional[int] = None, language: str = "tr",
    notes: Optional[str] = None, db_path: Path = DB_PATH
) -> int:
    conn = _conn(db_path)
    cursor = conn.execute(
        """INSERT INTO lyrics (work_id, track_id, content, bar_count, language, notes)
           VALUES (?,?,?,?,?,?)""",
        (work_id, track_id, content, bar_count, language, notes),
    )
    conn.commit()
    lyric_id = cursor.lastrowid
    conn.close()
    return lyric_id


# --- Delta Events ---

def add_delta_event(
    target_type: str, target_id: str, action: str,
    delta_payload: dict, actor: str = "system",
    db_path: Path = DB_PATH
) -> int:
    conn = _conn(db_path)
    cursor = conn.execute(
        """INSERT INTO delta_events (target_type, target_id, action, delta_payload, actor)
           VALUES (?,?,?,?,?)""",
        (target_type, target_id, action, json.dumps(delta_payload), actor),
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return event_id


def get_delta_events(
    target_id: Optional[str] = None, limit: int = 50,
    db_path: Path = DB_PATH
) -> list[dict]:
    conn = _conn(db_path)
    if target_id:
        rows = conn.execute(
            "SELECT * FROM delta_events WHERE target_id = ? ORDER BY created_at DESC LIMIT ?",
            (target_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM delta_events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Runs ---

def get_runs(track_id: Optional[str] = None, db_path: Path = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    if track_id:
        rows = conn.execute(
            "SELECT * FROM runs WHERE track_id = ? ORDER BY timestamp", (track_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM runs ORDER BY timestamp").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Revision Rules ---

def get_revision_rules(db_path: Path = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute("SELECT * FROM revision_rules ORDER BY key").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("tighten"):
            d["tighten"] = json.loads(d["tighten"])
        return result
    return result


# --- Freeze State ---

def get_freeze_state(db_path: Path = DB_PATH) -> Optional[dict]:
    conn = _conn(db_path)
    row = conn.execute("SELECT * FROM freeze_state LIMIT 1").fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for k in ("components", "python_components", "engine_state"):
        if d.get(k):
            d[k] = json.loads(d[k])
    return d


# --- Quick verification ---

def verify_db(db_path: Path = DB_PATH):
    """Print row counts for all tables."""
    conn = _conn(db_path)
    tables = [
        r[0] for r in
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    ]
    print(f"Database: {db_path}")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        print(f"  {t}: {count} rows")
    conn.close()


if __name__ == "__main__":
    verify_db()
