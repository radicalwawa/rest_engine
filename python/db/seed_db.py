"""Seed REST Engine SQLite database from JSON source-of-truth files."""

import json
import sqlite3
import sys
from pathlib import Path

# Paths
DB_DIR = Path(__file__).parent
DB_PATH = DB_DIR / "rest_engine.db"
ROOT = DB_DIR.parent.parent  # rest_engine root


def load_json(rel_path: str) -> dict:
    """Load a JSON file relative to project root."""
    fp = ROOT / rel_path
    if not fp.exists():
        print(f"WARN: {rel_path} not found, skipping")
        return {}
    return json.loads(fp.read_text(encoding="utf-8"))


def seed_artists(conn: sqlite3.Connection):
    data = load_json("artists/artist_base.json")
    if not data:
        return
    conn.execute(
        """INSERT OR REPLACE INTO artists
           (artist_id, version, max_bars, lyrical_complexity, vocal_melodic_range,
            delivery_style, persona, melodic_expressiveness, emotional_variance,
            performance_flash)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            data["artist_id"], data["version"], data["max_bars"],
            data["lyrical_complexity"], data["vocal_melodic_range"],
            data["delivery_style"], data["persona"],
            data["melodic_expressiveness"], data["emotional_variance"],
            data["performance_flash"],
        ),
    )
    print("  artists: 1 row")


def seed_identities(conn: sqlite3.Connection):
    data = load_json("domain/album5_identities.json")
    if not data:
        return
    count = 0
    for ident in data.get("identities", []):
        conn.execute(
            """INSERT OR REPLACE INTO identities
               (track_id, state_label, genre_stack, bpm_min, bpm_max, groove,
                drum_language, bass_language, harmony_policy, ambience_policy,
                fx_policy, energy_curve, vocal_delivery, mix_targets,
                suno_prompt_guidelines)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ident["track_id"], ident["state_label"],
                json.dumps(ident["genre_stack"]),
                ident["bpm_min"], ident["bpm_max"], ident["groove"],
                ident["drum_language"], ident["bass_language"],
                ident["harmony_policy"], ident["ambience_policy"],
                json.dumps(ident["fx_policy"]), ident["energy_curve"],
                json.dumps(ident["vocal_delivery"]),
                json.dumps(ident["mix_targets"]),
                json.dumps(ident["suno_prompt_guidelines"]),
            ),
        )
        count += 1
    print(f"  identities: {count} rows")


def seed_tracks(conn: sqlite3.Connection):
    tracks_dir = ROOT / "tracks"
    count = 0
    for fp in sorted(tracks_dir.glob("radical.*.json")):
        t = json.loads(fp.read_text(encoding="utf-8"))
        tp = t["techno_profile"]
        cal = t["calibration"]
        lb = t["library_binding"]
        conn.execute(
            """INSERT OR REPLACE INTO tracks
               (id, version, theme, energy_profile, emotional_tone, lyrical_focus,
                keyword_vector, drive_level, bass_weight, texture_type, spatial_depth,
                bpm_override, structure_override, tested_bpms, proven_bpm, drift_notes,
                binding_kick, binding_bass, binding_hat, binding_lead, binding_texture)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                t["id"], t["version"], t["theme"], t["energy_profile"],
                t["emotional_tone"], t["lyrical_focus"],
                json.dumps(t["keyword_vector"]),
                tp["drive_level"], tp["bass_weight"], tp["texture_type"],
                tp["spatial_depth"],
                t["constraints"]["bpm_override"],
                t["constraints"]["structure_override"],
                json.dumps(cal["tested_bpms"]), cal["proven_bpm"],
                json.dumps(cal["drift_notes"]),
                lb["kick"], lb["bass"], lb["hat"], lb["lead"], lb["texture"],
            ),
        )
        count += 1
    print(f"  tracks: {count} rows")


def seed_sound_library(conn: sqlite3.Connection):
    data = load_json("knowledge/sound_library.json")
    if not data:
        return
    count = 0
    for a in data.get("assets", []):
        lic = a["license"]
        bpm = a.get("bpm_range")
        conn.execute(
            """INSERT OR REPLACE INTO sound_library
               (id, type, color_state, role, intensity, tags, path,
                license_source, license_usage, license_attribution,
                notes, updated_at, status, bpm_range_min, bpm_range_max,
                key, duration_ms, loudness_lufs, checksum_sha256)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                a["id"], a["type"], a["color_state"], a["role"], a["intensity"],
                json.dumps(a["tags"]), a["path"],
                lic["source"], lic["usage"], lic.get("attribution"),
                a.get("notes"), a.get("updated_at"),
                a.get("status", "active"),
                bpm["min"] if bpm else None,
                bpm["max"] if bpm else None,
                a.get("key"), a.get("duration_ms"),
                a.get("loudness_lufs"), a.get("checksum_sha256"),
            ),
        )
        count += 1
    print(f"  sound_library: {count} rows")


def seed_sound_map(conn: sqlite3.Connection):
    data = load_json("domain/domain_lock.json")
    if not data:
        return
    for color in data.get("active_colors", []):
        conn.execute(
            """INSERT OR REPLACE INTO sound_map
               (color, domain_model, genre_bias, calibration_bpm_set,
                bpm_policy, mode_default)
               VALUES (?,?,?,?,?,?)""",
            (
                color, data["domain_model"], data["genre_bias"],
                json.dumps(data["calibration_bpm_set"]),
                data["bpm_policy"], data["mode_default"],
            ),
        )
    print(f"  sound_map: {len(data.get('active_colors', []))} rows")


def seed_works(conn: sqlite3.Connection):
    data = load_json("domain/works_manifest.json")
    if not data:
        return
    count = 0
    for w in data.get("works", []):
        conn.execute(
            """INSERT OR REPLACE INTO works
               (work_id, track_id, series, title, volume, created_at, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (
                w["work_id"], w["track_id"], w["series"], w["title"],
                w["volume"], w["created_at"], w.get("notes"),
            ),
        )
        count += 1
    print(f"  works: {count} rows")


def seed_revision_rules(conn: sqlite3.Connection):
    data = load_json("domain/revision_rules.json")
    if not data:
        return
    count = 0
    for action in data.get("actions", []):
        conn.execute(
            """INSERT OR REPLACE INTO revision_rules
               (key, when_below, prompt_append_tr, tighten, loosen)
               VALUES (?,?,?,?,?)""",
            (
                action["key"], action["when_below"],
                action["prompt_append_tr"],
                json.dumps(action["tighten"]),
                json.dumps(action["loosen"]) if action.get("loosen") else None,
            ),
        )
        count += 1
    print(f"  revision_rules: {count} rows")


def seed_freeze_state(conn: sqlite3.Connection):
    data = load_json("domain/phase_freeze_album5.json")
    if not data:
        return
    conn.execute(
        """INSERT OR REPLACE INTO freeze_state
           (phase, status, frozen_at, notes, components,
            python_components, engine_state)
           VALUES (?,?,?,?,?,?,?)""",
        (
            data["phase"], data["status"], data.get("frozen_at"),
            data.get("notes"),
            json.dumps(data["components"]),
            json.dumps(data["python_components"]),
            json.dumps(data["engine_state"]),
        ),
    )
    print("  freeze_state: 1 row")


def seed_all(db_path: Path = DB_PATH):
    if not db_path.exists():
        print(f"FAIL: database not found at {db_path}. Run init_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    print("Seeding database...")
    seed_artists(conn)
    seed_identities(conn)
    seed_tracks(conn)
    seed_sound_library(conn)
    seed_sound_map(conn)
    seed_works(conn)
    seed_revision_rules(conn)
    seed_freeze_state(conn)

    conn.commit()
    conn.close()
    print("DONE: all JSON data migrated to SQLite")


if __name__ == "__main__":
    seed_all()
