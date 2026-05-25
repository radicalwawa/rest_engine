#!/usr/bin/env python3
"""
REST ENGINE — SQLite Database Manager
JSON -> SQLite mirror layer. JSON is always source of truth.
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("db_manager")

# --- Paths ---
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "rest_engine.db"
TRACKS_DIR = ROOT / "tracks"
DOMAIN_DIR = ROOT / "domain"
KNOWLEDGE_DIR = ROOT / "knowledge"

JSON_SOURCES = {
    "tracks": list(TRACKS_DIR.glob("radical.*.json")),
    "identities": DOMAIN_DIR / "album5_identities.json",
    "registry": KNOWLEDGE_DIR / "registry.json",
    "sound_library": KNOWLEDGE_DIR / "sound_library.json",
    "sdm": ROOT / "sdm.json",
    "works_manifest": DOMAIN_DIR / "works_manifest.json",
    "score_schema": DOMAIN_DIR / "score_schema.json",
    "suno_prompt_format": DOMAIN_DIR / "suno_prompt_format.json",
    "domain_lock": DOMAIN_DIR / "domain_lock.json",
    "revision_rules": DOMAIN_DIR / "revision_rules.json",
    "phase_freeze": DOMAIN_DIR / "phase_freeze_album5.json",
    "album_manifest": DOMAIN_DIR / "album_5_manifest.json",
    "acapella_protocol": DOMAIN_DIR / "acapella_protocol.json",
}

COLOR_ORDER = ["grey", "blue", "green", "cream", "black"]


def _load_json(path: Path) -> dict | list | None:
    """JSON dosyasini guvenli yukler."""
    if not path.exists():
        log.warning("dosya bulunamadi: %s", path)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error("JSON okuma hatasi %s: %s", path, e)
        return None


def _now_iso() -> str:
    """UTC ISO 8601 timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================
# Schema DDL
# ============================================================

SCHEMA_DDL = """
-- sync metadata
CREATE TABLE IF NOT EXISTS sync_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at   TEXT NOT NULL,
    source_file TEXT,
    table_name  TEXT,
    row_count   INTEGER,
    status      TEXT DEFAULT 'ok'
);

-- tracks (5 rows)
CREATE TABLE IF NOT EXISTS tracks (
    id              TEXT PRIMARY KEY,
    version         TEXT,
    theme           TEXT,
    energy_profile  TEXT,
    emotional_tone  TEXT,
    lyrical_focus   TEXT,
    keyword_vector  TEXT,  -- JSON array as text
    drive_level     TEXT,
    bass_weight     TEXT,
    texture_type    TEXT,
    spatial_depth   TEXT,
    bpm_override    REAL,
    structure_override TEXT,
    tested_bpms     TEXT,  -- JSON array
    proven_bpm      REAL,
    drift_notes     TEXT   -- JSON array
);
CREATE INDEX IF NOT EXISTS idx_tracks_energy ON tracks(energy_profile);

-- library_bindings (5 rows, one per track)
CREATE TABLE IF NOT EXISTS library_bindings (
    track_id    TEXT PRIMARY KEY REFERENCES tracks(id),
    kick        TEXT,
    bass        TEXT,
    hat         TEXT,
    lead        TEXT,
    texture     TEXT
);

-- identities (5 rows, full identity per track)
CREATE TABLE IF NOT EXISTS identities (
    track_id        TEXT PRIMARY KEY REFERENCES tracks(id),
    state_label     TEXT,
    genre_stack     TEXT,  -- JSON array
    bpm_min         INTEGER,
    bpm_max         INTEGER,
    groove          TEXT,
    drum_language   TEXT,
    bass_language   TEXT,
    harmony_policy  TEXT,
    ambience_policy TEXT,
    energy_curve    TEXT
);

-- production_dna: vocal, fx, mix per track
CREATE TABLE IF NOT EXISTS production_dna (
    track_id            TEXT PRIMARY KEY REFERENCES tracks(id),
    -- vocal
    vocal_anchor        TEXT,
    vocal_register      TEXT,
    vocal_intensity     TEXT,
    vocal_character     TEXT,
    vocal_adlibs        INTEGER,  -- 0/1/null
    vocal_hook_repeat   TEXT,
    -- fx
    fx_reverb           TEXT,
    fx_delay            TEXT,
    fx_distortion       TEXT,
    fx_brightness       TEXT,
    fx_stereo_width     TEXT,
    -- mix
    mix_kick_sub        TEXT,
    mix_transients      TEXT,
    mix_headroom_db     REAL,
    mix_loudness_target REAL,
    -- suno guidelines
    suno_allow_drop         INTEGER,
    suno_allow_big_reverb   INTEGER,
    suno_focus              TEXT,  -- JSON array
    suno_avoid              TEXT,  -- JSON array
    suno_notes              TEXT
);

-- sound_assets (30 rows)
CREATE TABLE IF NOT EXISTS sound_assets (
    id          TEXT PRIMARY KEY,
    type        TEXT,
    color_state TEXT,
    role        TEXT,
    intensity   INTEGER,
    tags        TEXT,  -- JSON array
    path        TEXT,
    license_source      TEXT,
    license_usage       TEXT,
    license_attribution TEXT,
    notes       TEXT,
    updated_at  TEXT,
    status      TEXT,
    bpm_range_min REAL,
    bpm_range_max REAL
);
CREATE INDEX IF NOT EXISTS idx_assets_color ON sound_assets(color_state);
CREATE INDEX IF NOT EXISTS idx_assets_role ON sound_assets(role);

-- works
CREATE TABLE IF NOT EXISTS works (
    work_id     TEXT PRIMARY KEY,
    track_id    TEXT REFERENCES tracks(id),
    series      TEXT,
    title       TEXT,
    volume      TEXT,
    created_at  TEXT,
    notes       TEXT
);
CREATE INDEX IF NOT EXISTS idx_works_track ON works(track_id);

-- registry (single row)
CREATE TABLE IF NOT EXISTS registry (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    version         TEXT,
    active_tracks   TEXT,  -- JSON array
    run_ids         TEXT,  -- JSON array
    updated_at      TEXT,
    notes           TEXT
);

-- sdm_state (single row)
CREATE TABLE IF NOT EXISTS sdm_state (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    proto               TEXT,
    contract_text       TEXT,
    contract_fingerprint TEXT,
    freeze_pointer      TEXT,
    repo_head           TEXT,
    active_work_id      TEXT,
    active_track        TEXT,
    inv_no_engine_edits     INTEGER,
    inv_no_freeze_edits     INTEGER,
    inv_no_repo_refactor    INTEGER,
    inv_no_ui_tui           INTEGER,
    inv_one_scope_per_change INTEGER,
    inv_json_source_of_truth INTEGER,
    state_updated_at    TEXT,
    mission_id          TEXT,
    mission_title       TEXT,
    mission_scope_guard TEXT,
    mission_steps       TEXT,  -- JSON array
    mission_outputs     TEXT,  -- JSON array
    mission_done_def    TEXT,
    mission_status      TEXT,
    mission_queue       TEXT,  -- JSON array
    mission_updated_at  TEXT,
    delta_window_mode   TEXT,
    delta_window_n      INTEGER,
    delta_updated_at    TEXT,
    sdm_updated_at      TEXT
);

-- sdm_events (windowed list)
CREATE TABLE IF NOT EXISTS sdm_events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT,
    commit_hash TEXT,
    scope   TEXT,
    files   TEXT,  -- JSON array
    result  TEXT,
    note    TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON sdm_events(ts);

-- score_schema (single row)
CREATE TABLE IF NOT EXISTS score_schema (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    version     TEXT,
    score_keys  TEXT,  -- JSON array
    scale_min   INTEGER,
    scale_max   INTEGER,
    total_max   INTEGER,
    encoding    TEXT,
    notes       TEXT
);

-- revision_actions
CREATE TABLE IF NOT EXISTS revision_actions (
    score_key       TEXT PRIMARY KEY,
    when_below      INTEGER,
    prompt_append_tr TEXT,
    tighten         TEXT,  -- JSON object
    loosen          TEXT   -- JSON object or null
);

-- domain_lock (single row)
CREATE TABLE IF NOT EXISTS domain_lock (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    domain_model        TEXT,
    active_colors       TEXT,  -- JSON array
    deprecated_model    TEXT,
    narrative_tagline   TEXT,
    domain_id           TEXT,
    version             TEXT,
    genre_bias          TEXT,
    primary_fusion      TEXT,  -- JSON array
    calibration_bpm_set TEXT,  -- JSON array
    bpm_policy          TEXT,
    mode_default        TEXT,
    cal_single_variable_only    INTEGER,
    cal_no_multi_variable       INTEGER,
    cal_drift_classification    INTEGER,
    cal_no_commercial_deploy    INTEGER,
    prompt_max_genre_anchors    INTEGER,
    prompt_primary_plus_texture INTEGER,
    prompt_avoid_adj_stacking   INTEGER,
    prompt_deterministic        INTEGER,
    prompt_entropy_min          INTEGER,
    vocal_identity_lock         INTEGER,
    vocal_no_timbre_mutation    INTEGER,
    vocal_no_cadence_mutation   INTEGER,
    vocal_no_melodic_exag       INTEGER
);

-- album_manifest_states (5 rows)
CREATE TABLE IF NOT EXISTS album_manifest_states (
    track_id                TEXT PRIMARY KEY REFERENCES tracks(id),
    bpm_range_min           REAL,
    bpm_range_max           REAL,
    structural_energy_curve TEXT,
    suno_prompt_skeleton    TEXT,
    instrumentation_profile TEXT,
    drop_logic              TEXT
);

-- phase_freeze (single row)
CREATE TABLE IF NOT EXISTS phase_freeze (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    version     TEXT,
    phase       TEXT,
    status      TEXT,
    frozen_at   TEXT,
    notes       TEXT,
    components  TEXT,  -- JSON object
    python_components TEXT,  -- JSON object
    engine_state TEXT  -- JSON object
);
"""


# ============================================================
# DbManager
# ============================================================

class DbManager:
    """REST Engine SQLite mirror. JSON kaynagindan okur, SQLite'a yazar."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._conn: sqlite3.Connection | None = None

    # --- context manager ---
    def __enter__(self) -> "DbManager":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def connect(self) -> None:
        """Veritabani baglantisi ac ve schema olustur."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_DDL)
        self._conn.commit()

    def close(self) -> None:
        """Baglanti kapat."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("veritabani bagli degil — connect() cagir")
        return self._conn

    def _log_sync(self, source: str, table: str, count: int, status: str = "ok") -> None:
        """sync_log tablosuna kayit ekle."""
        self.conn.execute(
            "INSERT INTO sync_log (synced_at, source_file, table_name, row_count, status) VALUES (?, ?, ?, ?, ?)",
            (_now_iso(), source, table, count, status),
        )

    # ============================================================
    # Sync: JSON -> SQLite
    # ============================================================

    def sync_from_json(self) -> dict[str, int]:
        """Tum JSON dosyalarini oku, SQLite'a yaz. Destructive replace."""
        log.info("sync basliyor...")
        counts: dict[str, int] = {}

        counts["tracks"] = self._sync_tracks()
        counts["identities"] = self._sync_identities()
        counts["sound_assets"] = self._sync_sound_library()
        counts["works"] = self._sync_works()
        counts["registry"] = self._sync_registry()
        counts["sdm"] = self._sync_sdm()
        counts["score_schema"] = self._sync_score_schema()
        counts["revision_actions"] = self._sync_revision_rules()
        counts["domain_lock"] = self._sync_domain_lock()
        counts["album_manifest"] = self._sync_album_manifest()
        counts["phase_freeze"] = self._sync_phase_freeze()

        self.conn.commit()
        log.info("sync tamamlandi: %s", counts)
        return counts

    def _sync_tracks(self) -> int:
        """tracks + library_bindings tablolarini doldur."""
        self.conn.execute("DELETE FROM library_bindings")
        self.conn.execute("DELETE FROM tracks")
        count = 0
        for path in sorted(TRACKS_DIR.glob("radical.*.json")):
            t = _load_json(path)
            if not isinstance(t, dict):
                continue
            tp = t.get("techno_profile") or {}
            con = t.get("constraints") or {}
            cal = t.get("calibration") or {}
            lb = t.get("library_binding") or {}

            self.conn.execute(
                """INSERT INTO tracks (id, version, theme, energy_profile, emotional_tone,
                   lyrical_focus, keyword_vector, drive_level, bass_weight, texture_type,
                   spatial_depth, bpm_override, structure_override, tested_bpms, proven_bpm,
                   drift_notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    t.get("id"), t.get("version"), t.get("theme"),
                    t.get("energy_profile"), t.get("emotional_tone"),
                    t.get("lyrical_focus"),
                    json.dumps(t.get("keyword_vector", []), ensure_ascii=False),
                    tp.get("drive_level"), tp.get("bass_weight"),
                    tp.get("texture_type"), tp.get("spatial_depth"),
                    con.get("bpm_override"), con.get("structure_override"),
                    json.dumps(cal.get("tested_bpms", []), ensure_ascii=False),
                    cal.get("proven_bpm"),
                    json.dumps(cal.get("drift_notes", []), ensure_ascii=False),
                ),
            )
            self.conn.execute(
                "INSERT INTO library_bindings (track_id, kick, bass, hat, lead, texture) VALUES (?,?,?,?,?,?)",
                (t.get("id"), lb.get("kick"), lb.get("bass"), lb.get("hat"), lb.get("lead"), lb.get("texture")),
            )
            count += 1
            self._log_sync(str(path.name), "tracks", 1)
        return count

    def _sync_identities(self) -> int:
        """identities + production_dna tablolarini doldur."""
        self.conn.execute("DELETE FROM production_dna")
        self.conn.execute("DELETE FROM identities")
        data = _load_json(JSON_SOURCES["identities"])
        if not isinstance(data, dict):
            return 0
        idents = data.get("identities") or []
        count = 0
        for i in idents:
            self.conn.execute(
                """INSERT INTO identities (track_id, state_label, genre_stack, bpm_min,
                   bpm_max, groove, drum_language, bass_language, harmony_policy,
                   ambience_policy, energy_curve)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    i.get("track_id"), i.get("state_label"),
                    json.dumps(i.get("genre_stack", []), ensure_ascii=False),
                    i.get("bpm_min"), i.get("bpm_max"), i.get("groove"),
                    i.get("drum_language"), i.get("bass_language"),
                    i.get("harmony_policy"), i.get("ambience_policy"),
                    i.get("energy_curve"),
                ),
            )
            vd = i.get("vocal_delivery") or {}
            fx = i.get("fx_policy") or {}
            mx = i.get("mix_targets") or {}
            sg = i.get("suno_prompt_guidelines") or {}
            adlibs = vd.get("adlibs")
            adlibs_int = None if adlibs is None else (1 if adlibs else 0)

            self.conn.execute(
                """INSERT INTO production_dna (track_id,
                   vocal_anchor, vocal_register, vocal_intensity, vocal_character,
                   vocal_adlibs, vocal_hook_repeat,
                   fx_reverb, fx_delay, fx_distortion, fx_brightness, fx_stereo_width,
                   mix_kick_sub, mix_transients, mix_headroom_db, mix_loudness_target,
                   suno_allow_drop, suno_allow_big_reverb, suno_focus, suno_avoid, suno_notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    i.get("track_id"),
                    vd.get("anchor"), vd.get("register"), vd.get("intensity"),
                    vd.get("character"), adlibs_int, vd.get("hook_last_word_repeat"),
                    fx.get("reverb"), fx.get("delay"), fx.get("distortion"),
                    fx.get("brightness"), fx.get("stereo_width"),
                    mx.get("kick_sub_relationship"), mx.get("transients"),
                    mx.get("headroom_db"), mx.get("loudness_target"),
                    1 if sg.get("allow_drop") else 0,
                    1 if sg.get("allow_big_reverb") else 0,
                    json.dumps(sg.get("focus", []), ensure_ascii=False),
                    json.dumps(sg.get("avoid", []), ensure_ascii=False),
                    sg.get("notes"),
                ),
            )
            count += 1
        self._log_sync("album5_identities.json", "identities", count)
        return count

    def _sync_sound_library(self) -> int:
        """sound_assets tablosunu doldur."""
        self.conn.execute("DELETE FROM sound_assets")
        data = _load_json(JSON_SOURCES["sound_library"])
        if not isinstance(data, dict):
            return 0
        assets = data.get("assets") or []
        count = 0
        for a in assets:
            lic = a.get("license") or {}
            bpm = a.get("bpm_range") or {}
            self.conn.execute(
                """INSERT INTO sound_assets (id, type, color_state, role, intensity, tags,
                   path, license_source, license_usage, license_attribution,
                   notes, updated_at, status, bpm_range_min, bpm_range_max)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    a.get("id"), a.get("type"), a.get("color_state"), a.get("role"),
                    a.get("intensity"),
                    json.dumps(a.get("tags", []), ensure_ascii=False),
                    a.get("path"), lic.get("source"), lic.get("usage"),
                    lic.get("attribution"), a.get("notes"), a.get("updated_at"),
                    a.get("status"), bpm.get("min"), bpm.get("max"),
                ),
            )
            count += 1
        self._log_sync("sound_library.json", "sound_assets", count)
        return count

    def _sync_works(self) -> int:
        """works tablosunu doldur."""
        self.conn.execute("DELETE FROM works")
        data = _load_json(JSON_SOURCES["works_manifest"])
        if not isinstance(data, dict):
            return 0
        wlist = data.get("works") or []
        count = 0
        for w in wlist:
            self.conn.execute(
                "INSERT INTO works (work_id, track_id, series, title, volume, created_at, notes) VALUES (?,?,?,?,?,?,?)",
                (w.get("work_id"), w.get("track_id"), w.get("series"),
                 w.get("title"), w.get("volume"), w.get("created_at"), w.get("notes")),
            )
            count += 1
        self._log_sync("works_manifest.json", "works", count)
        return count

    def _sync_registry(self) -> int:
        """registry tablosunu doldur (tek satir)."""
        self.conn.execute("DELETE FROM registry")
        data = _load_json(JSON_SOURCES["registry"])
        if not isinstance(data, dict):
            return 0
        self.conn.execute(
            "INSERT INTO registry (id, version, active_tracks, run_ids, updated_at, notes) VALUES (1,?,?,?,?,?)",
            (
                data.get("version"),
                json.dumps(data.get("active_tracks", []), ensure_ascii=False),
                json.dumps(data.get("run_ids", []), ensure_ascii=False),
                data.get("updated_at"), data.get("notes"),
            ),
        )
        self._log_sync("registry.json", "registry", 1)
        return 1

    def _sync_sdm(self) -> int:
        """sdm_state + sdm_events tablolarini doldur."""
        self.conn.execute("DELETE FROM sdm_events")
        self.conn.execute("DELETE FROM sdm_state")
        data = _load_json(JSON_SOURCES["sdm"])
        if not isinstance(data, dict):
            return 0
        ct = data.get("contract") or {}
        st = data.get("state") or {}
        inv = st.get("invariants") or {}
        dl = data.get("delta") or {}
        win = dl.get("window") or {}
        ms = data.get("mission") or {}
        cur = ms.get("current") or {}

        self.conn.execute(
            """INSERT INTO sdm_state (id, proto, contract_text, contract_fingerprint,
               freeze_pointer, repo_head, active_work_id, active_track,
               inv_no_engine_edits, inv_no_freeze_edits, inv_no_repo_refactor,
               inv_no_ui_tui, inv_one_scope_per_change, inv_json_source_of_truth,
               state_updated_at, mission_id, mission_title, mission_scope_guard,
               mission_steps, mission_outputs, mission_done_def, mission_status,
               mission_queue, mission_updated_at, delta_window_mode, delta_window_n,
               delta_updated_at, sdm_updated_at)
               VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("proto"), ct.get("text"), ct.get("fingerprint"),
                st.get("freeze_pointer"), st.get("repo_head"),
                st.get("active_work_id"), st.get("active_track"),
                _bool_to_int(inv.get("no_engine_edits")),
                _bool_to_int(inv.get("no_freeze_edits")),
                _bool_to_int(inv.get("no_repo_refactor")),
                _bool_to_int(inv.get("no_ui_tui")),
                _bool_to_int(inv.get("one_scope_per_change")),
                _bool_to_int(inv.get("json_source_of_truth")),
                st.get("updated_at"),
                cur.get("id"), cur.get("title"), cur.get("scope_guard"),
                json.dumps(cur.get("steps", []), ensure_ascii=False),
                json.dumps(cur.get("expected_outputs", []), ensure_ascii=False),
                cur.get("done_definition"), cur.get("status"),
                json.dumps(ms.get("queue", []), ensure_ascii=False),
                ms.get("updated_at"),
                win.get("mode"), win.get("n"),
                dl.get("updated_at"), data.get("updated_at"),
            ),
        )
        events = dl.get("events") or []
        ev_count = 0
        for ev in events:
            self.conn.execute(
                "INSERT INTO sdm_events (ts, commit_hash, scope, files, result, note) VALUES (?,?,?,?,?,?)",
                (
                    ev.get("ts"), ev.get("commit"), ev.get("scope"),
                    json.dumps(ev.get("files", []), ensure_ascii=False),
                    ev.get("result"), ev.get("note"),
                ),
            )
            ev_count += 1
        self._log_sync("sdm.json", "sdm_state", 1)
        self._log_sync("sdm.json", "sdm_events", ev_count)
        return 1 + ev_count

    def _sync_score_schema(self) -> int:
        """score_schema tablosunu doldur."""
        self.conn.execute("DELETE FROM score_schema")
        data = _load_json(JSON_SOURCES["score_schema"])
        if not isinstance(data, dict):
            return 0
        scale = data.get("scale") or [0, 10]
        self.conn.execute(
            """INSERT INTO score_schema (id, version, score_keys, scale_min, scale_max,
               total_max, encoding, notes) VALUES (1,?,?,?,?,?,?,?)""",
            (
                data.get("version"),
                json.dumps(data.get("score_keys", []), ensure_ascii=False),
                scale[0] if len(scale) > 0 else 0,
                scale[1] if len(scale) > 1 else 10,
                data.get("total_max"), data.get("encoding"), data.get("notes"),
            ),
        )
        self._log_sync("score_schema.json", "score_schema", 1)
        return 1

    def _sync_revision_rules(self) -> int:
        """revision_actions tablosunu doldur."""
        self.conn.execute("DELETE FROM revision_actions")
        data = _load_json(JSON_SOURCES["revision_rules"])
        if not isinstance(data, dict):
            return 0
        actions = data.get("actions") or []
        count = 0
        for a in actions:
            self.conn.execute(
                "INSERT INTO revision_actions (score_key, when_below, prompt_append_tr, tighten, loosen) VALUES (?,?,?,?,?)",
                (
                    a.get("key"), a.get("when_below"), a.get("prompt_append_tr"),
                    json.dumps(a.get("tighten"), ensure_ascii=False) if a.get("tighten") else None,
                    json.dumps(a.get("loosen"), ensure_ascii=False) if a.get("loosen") else None,
                ),
            )
            count += 1
        self._log_sync("revision_rules.json", "revision_actions", count)
        return count

    def _sync_domain_lock(self) -> int:
        """domain_lock tablosunu doldur."""
        self.conn.execute("DELETE FROM domain_lock")
        d = _load_json(JSON_SOURCES["domain_lock"])
        if not isinstance(d, dict):
            return 0
        cr = d.get("calibration_rules") or {}
        pp = d.get("prompt_policy") or {}
        vp = d.get("vocal_policy") or {}
        self.conn.execute(
            """INSERT INTO domain_lock (id, domain_model, active_colors, deprecated_model,
               narrative_tagline, domain_id, version, genre_bias, primary_fusion,
               calibration_bpm_set, bpm_policy, mode_default,
               cal_single_variable_only, cal_no_multi_variable, cal_drift_classification,
               cal_no_commercial_deploy, prompt_max_genre_anchors, prompt_primary_plus_texture,
               prompt_avoid_adj_stacking, prompt_deterministic, prompt_entropy_min,
               vocal_identity_lock, vocal_no_timbre_mutation, vocal_no_cadence_mutation,
               vocal_no_melodic_exag)
               VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d.get("domain_model"),
                json.dumps(d.get("active_colors", []), ensure_ascii=False),
                d.get("deprecated_model"), d.get("narrative_tagline"),
                d.get("domain_id"), d.get("version"), d.get("genre_bias"),
                json.dumps(d.get("primary_fusion", []), ensure_ascii=False),
                json.dumps(d.get("calibration_bpm_set", []), ensure_ascii=False),
                d.get("bpm_policy"), d.get("mode_default"),
                _bool_to_int(cr.get("single_variable_only")),
                _bool_to_int(cr.get("no_multi_variable_correction")),
                _bool_to_int(cr.get("drift_classification_required")),
                _bool_to_int(cr.get("no_commercial_deploy_in_calibration")),
                pp.get("max_genre_anchors"),
                _bool_to_int(pp.get("primary_plus_one_texture")),
                _bool_to_int(pp.get("avoid_adjective_stacking")),
                _bool_to_int(pp.get("deterministic_phrasing")),
                _bool_to_int(pp.get("entropy_minimization")),
                _bool_to_int(vp.get("vocal_identity_lock_mandatory")),
                _bool_to_int(vp.get("no_timbre_mutation")),
                _bool_to_int(vp.get("no_cadence_mutation")),
                _bool_to_int(vp.get("no_melodic_exaggeration")),
            ),
        )
        self._log_sync("domain_lock.json", "domain_lock", 1)
        return 1

    def _sync_album_manifest(self) -> int:
        """album_manifest_states tablosunu doldur."""
        self.conn.execute("DELETE FROM album_manifest_states")
        data = _load_json(JSON_SOURCES["album_manifest"])
        if not isinstance(data, dict):
            return 0
        states = data.get("states") or []
        count = 0
        for s in states:
            bpm = s.get("bpm_range") or {}
            self.conn.execute(
                """INSERT INTO album_manifest_states (track_id, bpm_range_min, bpm_range_max,
                   structural_energy_curve, suno_prompt_skeleton, instrumentation_profile,
                   drop_logic) VALUES (?,?,?,?,?,?,?)""",
                (
                    s.get("track_id"), bpm.get("min"), bpm.get("max"),
                    s.get("structural_energy_curve"),
                    s.get("suno_prompt_template_skeleton"),
                    s.get("allowed_instrumentation_profile"),
                    s.get("drop_logic"),
                ),
            )
            count += 1
        self._log_sync("album_5_manifest.json", "album_manifest_states", count)
        return count

    def _sync_phase_freeze(self) -> int:
        """phase_freeze tablosunu doldur."""
        self.conn.execute("DELETE FROM phase_freeze")
        d = _load_json(JSON_SOURCES["phase_freeze"])
        if not isinstance(d, dict):
            return 0
        self.conn.execute(
            """INSERT INTO phase_freeze (id, version, phase, status, frozen_at, notes,
               components, python_components, engine_state)
               VALUES (1,?,?,?,?,?,?,?,?)""",
            (
                d.get("version"), d.get("phase"), d.get("status"),
                d.get("frozen_at"), d.get("notes"),
                json.dumps(d.get("components"), ensure_ascii=False) if d.get("components") else None,
                json.dumps(d.get("python_components"), ensure_ascii=False) if d.get("python_components") else None,
                json.dumps(d.get("engine_state"), ensure_ascii=False) if d.get("engine_state") else None,
            ),
        )
        self._log_sync("phase_freeze_album5.json", "phase_freeze", 1)
        return 1

    # ============================================================
    # File watcher (optional)
    # ============================================================

    def watch_and_sync(self, interval: float = 5.0) -> None:
        """JSON dosyalarini izle, degisiklik olunca sync yap.
        Ctrl+C ile durdurulur.
        """
        log.info("dosya izleme basliyor (%.1fs aralik)...", interval)
        mtimes: dict[str, float] = {}
        stop = threading.Event()

        def _collect_paths() -> list[Path]:
            paths = []
            for v in JSON_SOURCES.values():
                if isinstance(v, list):
                    paths.extend(v)
                elif isinstance(v, Path):
                    paths.append(v)
            return paths

        def _get_mtimes() -> dict[str, float]:
            result = {}
            for p in _collect_paths():
                if p.exists():
                    result[str(p)] = p.stat().st_mtime
            return result

        mtimes = _get_mtimes()
        try:
            while not stop.is_set():
                time.sleep(interval)
                new_mtimes = _get_mtimes()
                if new_mtimes != mtimes:
                    changed = [k for k in new_mtimes if new_mtimes.get(k) != mtimes.get(k)]
                    log.info("degisiklik algilandi: %s", [Path(c).name for c in changed])
                    self.sync_from_json()
                    mtimes = new_mtimes
        except KeyboardInterrupt:
            log.info("izleme durduruldu.")

    # ============================================================
    # Query API
    # ============================================================

    def get_all_tracks(self) -> list[dict]:
        """Tum track ozetlerini dondur."""
        rows = self.conn.execute(
            """SELECT t.id, t.version, t.theme, t.energy_profile,
                      i.state_label, i.bpm_min, i.bpm_max, i.groove
               FROM tracks t
               LEFT JOIN identities i ON t.id = i.track_id
               ORDER BY t.id"""
        ).fetchall()
        return [dict(r) for r in rows]

    def get_track_detail(self, track_id: str) -> dict | None:
        """Tek track icin tam detay: track + identity + production_dna + bindings."""
        row = self.conn.execute(
            "SELECT * FROM tracks WHERE id = ?", (track_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)

        # identity
        ident = self.conn.execute(
            "SELECT * FROM identities WHERE track_id = ?", (track_id,)
        ).fetchone()
        if ident:
            result["identity"] = dict(ident)

        # production_dna
        dna = self.conn.execute(
            "SELECT * FROM production_dna WHERE track_id = ?", (track_id,)
        ).fetchone()
        if dna:
            result["production_dna"] = dict(dna)

        # library_bindings
        bind = self.conn.execute(
            "SELECT * FROM library_bindings WHERE track_id = ?", (track_id,)
        ).fetchone()
        if bind:
            result["library_binding"] = dict(bind)

        # sound assets for this track color
        assets = self.conn.execute(
            "SELECT * FROM sound_assets WHERE color_state = ? ORDER BY role",
            (track_id,),
        ).fetchall()
        result["sound_assets"] = [dict(a) for a in assets]

        # works
        works = self.conn.execute(
            "SELECT * FROM works WHERE track_id = ? ORDER BY created_at", (track_id,)
        ).fetchall()
        result["works"] = [dict(w) for w in works]

        return result

    def get_identity(self, color: str) -> dict | None:
        """Renk adina gore identity dondur. 'grey' veya 'radical.grey' kabul eder."""
        track_id = color if color.startswith("radical.") else f"radical.{color}"
        row = self.conn.execute(
            """SELECT i.*, p.*
               FROM identities i
               LEFT JOIN production_dna p ON i.track_id = p.track_id
               WHERE i.track_id = ?""",
            (track_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_version_chain(self, track_id: str) -> list[dict]:
        """Track icin works + versiyon zinciri (hash chain). created_at sirasiyla."""
        rows = self.conn.execute(
            """SELECT w.work_id, w.track_id, w.series, w.title, w.volume,
                      w.created_at, w.notes,
                      t.version as track_version
               FROM works w
               JOIN tracks t ON w.track_id = t.id
               WHERE w.track_id = ?
               ORDER BY w.created_at""",
            (track_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sdm_state(self) -> dict | None:
        """Guncel SDM snapshot'i dondur."""
        row = self.conn.execute("SELECT * FROM sdm_state WHERE id = 1").fetchone()
        if not row:
            return None
        result = dict(row)
        events = self.conn.execute(
            "SELECT * FROM sdm_events ORDER BY ts"
        ).fetchall()
        result["events"] = [dict(e) for e in events]
        return result

    def search_tracks(self, query: str) -> list[dict]:
        """Track adlari, tema, label ve keyword'lerde metin arama."""
        pattern = f"%{query}%"
        rows = self.conn.execute(
            """SELECT t.id, t.version, t.theme, t.energy_profile, t.keyword_vector,
                      i.state_label, i.genre_stack
               FROM tracks t
               LEFT JOIN identities i ON t.id = i.track_id
               WHERE t.id LIKE ?
                  OR t.theme LIKE ?
                  OR t.emotional_tone LIKE ?
                  OR t.lyrical_focus LIKE ?
                  OR t.keyword_vector LIKE ?
                  OR i.state_label LIKE ?
                  OR i.genre_stack LIKE ?""",
            (pattern, pattern, pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Genel istatistikler."""
        track_count = self.conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        work_count = self.conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        asset_count = self.conn.execute("SELECT COUNT(*) FROM sound_assets").fetchone()[0]
        event_count = self.conn.execute("SELECT COUNT(*) FROM sdm_events").fetchone()[0]
        identity_count = self.conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0]

        # assets per color
        color_dist = {}
        rows = self.conn.execute(
            "SELECT color_state, COUNT(*) as cnt FROM sound_assets GROUP BY color_state ORDER BY color_state"
        ).fetchall()
        for r in rows:
            color_dist[r["color_state"]] = r["cnt"]

        # works per track
        work_dist = {}
        rows = self.conn.execute(
            "SELECT track_id, COUNT(*) as cnt FROM works GROUP BY track_id ORDER BY track_id"
        ).fetchall()
        for r in rows:
            work_dist[r["track_id"]] = r["cnt"]

        # last sync
        last_sync = self.conn.execute(
            "SELECT synced_at FROM sync_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return {
            "tracks": track_count,
            "identities": identity_count,
            "works": work_count,
            "sound_assets": asset_count,
            "sdm_events": event_count,
            "assets_per_color": color_dist,
            "works_per_track": work_dist,
            "last_sync": last_sync["synced_at"] if last_sync else None,
        }


def _bool_to_int(val: Any) -> int | None:
    """bool -> 0/1, None -> None."""
    if val is None:
        return None
    return 1 if val else 0


# ============================================================
# CLI
# ============================================================

def main() -> None:
    """Sync calistir, istatistikleri yazdir."""
    with DbManager() as db:
        counts = db.sync_from_json()

        print("\n=== REST ENGINE — DB SYNC SONUCLARI ===\n")
        for table, count in counts.items():
            print(f"  {table:<20} {count:>3} satir")

        print(f"\n  veritabani: {DB_PATH}")
        print(f"  boyut:      {DB_PATH.stat().st_size / 1024:.1f} KB")

        stats = db.get_stats()
        print("\n=== ISTATISTIKLER ===\n")
        print(f"  tracks:       {stats['tracks']}")
        print(f"  identities:   {stats['identities']}")
        print(f"  works:        {stats['works']}")
        print(f"  sound_assets: {stats['sound_assets']}")
        print(f"  sdm_events:   {stats['sdm_events']}")

        print("\n  assets/renk:")
        for color, cnt in stats["assets_per_color"].items():
            print(f"    {color:<16} {cnt}")

        if stats["works_per_track"]:
            print("\n  works/track:")
            for tid, cnt in stats["works_per_track"].items():
                print(f"    {tid:<16} {cnt}")

        # Query API smoke test
        print("\n=== QUERY API TEST ===\n")
        tracks = db.get_all_tracks()
        print(f"  get_all_tracks():       {len(tracks)} track")
        for t in tracks:
            print(f"    {t['id']} v{t['version']} — {t['state_label']}")

        detail = db.get_track_detail("radical.grey")
        if detail:
            print(f"\n  get_track_detail('radical.grey'):")
            print(f"    theme:   {detail['theme'][:50]}")
            print(f"    assets:  {len(detail['sound_assets'])}")
            print(f"    works:   {len(detail['works'])}")

        ident = db.get_identity("blue")
        if ident:
            print(f"\n  get_identity('blue'):")
            print(f"    state:   {ident['state_label']}")
            print(f"    vocal:   {ident['vocal_character']}")

        sdm = db.get_sdm_state()
        if sdm:
            print(f"\n  get_sdm_state():")
            print(f"    proto:   {sdm['proto']}")
            print(f"    mission: {sdm['mission_id']} — {sdm['mission_title']}")
            print(f"    events:  {len(sdm['events'])}")

        results = db.search_tracks("rage")
        print(f"\n  search_tracks('rage'):  {len(results)} sonuc")
        for r in results:
            print(f"    {r['id']} — {r['theme'][:40]}")

        print("\n=== SYNC BASARILI ===")


if __name__ == "__main__":
    main()


# ============================================================================
# v3 OPERATIONAL LAYER — added per MIRAS_20260320_v3 Phase 1 Step 1
# All writes to v3 tables (identities_v3, albums, beats, tracks_v3,
# daily_queue, suno_prompts, uploads, pipeline_log) MUST go through this
# section. M2 sync code above is untouched.
# ============================================================================

import json as _json_v3
import sqlite3 as _sqlite3_v3
from contextlib import contextmanager as _contextmanager_v3
from datetime import date as _date_v3
from pathlib import Path as _Path_v3

_DB_PATH_V3 = _Path_v3(__file__).resolve().parent / "rest_engine.db"

_V3_COLORS = ("green", "grey", "blue", "cream", "black")

_BEAT_STATUSES = ("pending", "generated", "reviewed", "approved", "rejected", "archived")
_TRACK_STATUSES = ("draft", "generated", "reviewed", "approved", "released", "archived")
_QUEUE_STATUSES = ("pending", "generated", "reviewed", "done", "skipped")
_UPLOAD_STATUSES = ("pending", "uploading", "live", "failed", "removed")


@_contextmanager_v3
def _v3_conn(conn=None):
    """Yield a connection. If caller passed one, reuse it (no commit/close).
    Otherwise open a fresh one, commit on success, always close."""
    if conn is not None:
        yield conn
        return
    own = _sqlite3_v3.connect(_DB_PATH_V3)
    own.execute("PRAGMA foreign_keys = ON;")
    own.row_factory = _sqlite3_v3.Row
    try:
        yield own
        own.commit()
    finally:
        own.close()


def _row_to_dict(row):
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def log_action(entity_type, entity_id, action, details=None, conn=None):
    """Insert a pipeline_log row. details accepts dict (json-encoded) or str."""
    if isinstance(details, dict):
        details = _json_v3.dumps(details, ensure_ascii=False)
    with _v3_conn(conn) as c:
        cur = c.execute(
            "INSERT INTO pipeline_log (entity_type, entity_id, action, details) "
            "VALUES (?,?,?,?)",
            (entity_type, entity_id, action, details),
        )
        return cur.lastrowid


# --- identities_v3 (read-only API; seeding lives in migrations/002) -----------

def get_identity_profile(color, conn=None):
    """Return full identities_v3 row as dict, with JSON arrays decoded."""
    if color not in _V3_COLORS:
        raise ValueError(f"unknown color: {color!r}; expected one of {_V3_COLORS}")
    with _v3_conn(conn) as c:
        c.row_factory = _sqlite3_v3.Row
        row = c.execute("SELECT * FROM identities_v3 WHERE color = ?", (color,)).fetchone()
    if row is None:
        return None
    d = _row_to_dict(row)
    for k in ("key_signatures", "instrumentation_rap",
              "instrumentation_techno", "instrumentation_shared"):
        if d.get(k):
            try:
                d[k] = _json_v3.loads(d[k])
            except (TypeError, _json_v3.JSONDecodeError):
                pass
    return d


def list_identities_v3(conn=None):
    """Return all 5 identity profiles, ordered by color."""
    return [get_identity_profile(color, conn=conn) for color in sorted(_V3_COLORS)]


# --- albums -------------------------------------------------------------------

def add_album(color, title, target_track_count=None, conn=None):
    if color not in _V3_COLORS:
        raise ValueError(f"unknown color: {color!r}")
    with _v3_conn(conn) as c:
        cur = c.execute(
            "INSERT INTO albums (color, title, target_track_count) VALUES (?,?,?)",
            (color, title, target_track_count),
        )
        album_id = cur.lastrowid
        log_action("album", album_id, "create",
                   {"color": color, "title": title,
                    "target_track_count": target_track_count}, conn=c)
        return album_id


def get_album(album_id, conn=None):
    with _v3_conn(conn) as c:
        c.row_factory = _sqlite3_v3.Row
        row = c.execute("SELECT * FROM albums WHERE id = ?", (album_id,)).fetchone()
    return _row_to_dict(row)


# --- beats --------------------------------------------------------------------

def add_beat(color, suno_prompt, bpm=None, key_sig=None,
             negative_prompt=None, suno_url=None, suno_audio_id=None,
             duration_sec=None, notes=None, status="pending", conn=None):
    if color not in _V3_COLORS:
        raise ValueError(f"unknown color: {color!r}")
    if status not in _BEAT_STATUSES:
        raise ValueError(f"invalid beat status: {status!r}")
    with _v3_conn(conn) as c:
        cur = c.execute(
            "INSERT INTO beats (color, suno_prompt, negative_prompt, bpm, key_sig, "
            "suno_url, suno_audio_id, duration_sec, status, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (color, suno_prompt, negative_prompt, bpm, key_sig,
             suno_url, suno_audio_id, duration_sec, status, notes),
        )
        beat_id = cur.lastrowid
        log_action("beat", beat_id, "create",
                   {"color": color, "bpm": bpm, "key": key_sig,
                    "status": status}, conn=c)
        return beat_id


def update_beat_status(beat_id, new_status, reason=None, conn=None):
    if new_status not in _BEAT_STATUSES:
        raise ValueError(f"invalid beat status: {new_status!r}")
    with _v3_conn(conn) as c:
        old = c.execute("SELECT status FROM beats WHERE id = ?", (beat_id,)).fetchone()
        if old is None:
            raise ValueError(f"beat {beat_id} not found")
        old_status = old[0]
        if new_status == "rejected":
            c.execute("UPDATE beats SET status = ?, reject_reason = ? WHERE id = ?",
                      (new_status, reason, beat_id))
        else:
            c.execute("UPDATE beats SET status = ? WHERE id = ?",
                      (new_status, beat_id))
        log_action("beat", beat_id, "status_change",
                   {"from": old_status, "to": new_status, "reason": reason}, conn=c)
        return True


def get_beat(beat_id, conn=None):
    with _v3_conn(conn) as c:
        c.row_factory = _sqlite3_v3.Row
        row = c.execute("SELECT * FROM beats WHERE id = ?", (beat_id,)).fetchone()
    return _row_to_dict(row)


def get_beats_by_status(status, color=None, conn=None):
    if status not in _BEAT_STATUSES:
        raise ValueError(f"invalid beat status: {status!r}")
    with _v3_conn(conn) as c:
        c.row_factory = _sqlite3_v3.Row
        if color:
            if color not in _V3_COLORS:
                raise ValueError(f"unknown color: {color!r}")
            rows = c.execute(
                "SELECT * FROM beats WHERE status = ? AND color = ? "
                "ORDER BY created_at DESC", (status, color)).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM beats WHERE status = ? "
                "ORDER BY created_at DESC", (status,)).fetchall()
    return [_row_to_dict(r) for r in rows]


# --- tracks_v3 ----------------------------------------------------------------

def add_track(color, title, album_id=None, beat_id=None, lyrics=None,
              suno_url=None, duration_sec=None, notes=None,
              status="draft", conn=None):
    if color not in _V3_COLORS:
        raise ValueError(f"unknown color: {color!r}")
    if status not in _TRACK_STATUSES:
        raise ValueError(f"invalid track status: {status!r}")
    with _v3_conn(conn) as c:
        cur = c.execute(
            "INSERT INTO tracks_v3 (color, album_id, beat_id, title, lyrics, "
            "suno_url, duration_sec, status, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (color, album_id, beat_id, title, lyrics,
             suno_url, duration_sec, status, notes),
        )
        track_id = cur.lastrowid
        log_action("track", track_id, "create",
                   {"color": color, "title": title, "album_id": album_id,
                    "beat_id": beat_id, "status": status}, conn=c)
        return track_id


def update_track_status(track_id, new_status, conn=None):
    if new_status not in _TRACK_STATUSES:
        raise ValueError(f"invalid track status: {new_status!r}")
    with _v3_conn(conn) as c:
        old = c.execute("SELECT status FROM tracks_v3 WHERE id = ?", (track_id,)).fetchone()
        if old is None:
            raise ValueError(f"track {track_id} not found")
        c.execute("UPDATE tracks_v3 SET status = ? WHERE id = ?", (new_status, track_id))
        log_action("track", track_id, "status_change",
                   {"from": old[0], "to": new_status}, conn=c)
        return True


def get_track(track_id, conn=None):
    with _v3_conn(conn) as c:
        c.row_factory = _sqlite3_v3.Row
        row = c.execute("SELECT * FROM tracks_v3 WHERE id = ?", (track_id,)).fetchone()
    return _row_to_dict(row)


# --- daily_queue --------------------------------------------------------------

def create_daily_queue(queue_date=None, conn=None):
    """Insert 5 pending rows (one per color) for the given date.
    Idempotent: UNIQUE(queue_date, color) makes re-runs no-op for existing rows."""
    if queue_date is None:
        queue_date = _date_v3.today().isoformat()
    created = []
    with _v3_conn(conn) as c:
        for color in sorted(_V3_COLORS):
            try:
                cur = c.execute(
                    "INSERT INTO daily_queue (queue_date, color, status) "
                    "VALUES (?,?, 'pending')", (queue_date, color))
                created.append({"color": color, "queue_id": cur.lastrowid})
                log_action("daily_queue", cur.lastrowid, "create",
                           {"queue_date": queue_date, "color": color}, conn=c)
            except _sqlite3_v3.IntegrityError:
                # already exists for this date+color, skip
                pass
    return {"queue_date": queue_date, "created": created}


def get_daily_queue(queue_date=None, conn=None):
    if queue_date is None:
        queue_date = _date_v3.today().isoformat()
    with _v3_conn(conn) as c:
        c.row_factory = _sqlite3_v3.Row
        rows = c.execute(
            "SELECT * FROM daily_queue WHERE queue_date = ? ORDER BY color",
            (queue_date,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_queue_status(queue_id, new_status, skip_reason=None,
                        beat_id=None, suno_prompt=None, conn=None):
    if new_status not in _QUEUE_STATUSES:
        raise ValueError(f"invalid queue status: {new_status!r}")
    with _v3_conn(conn) as c:
        old = c.execute("SELECT status FROM daily_queue WHERE id = ?",
                        (queue_id,)).fetchone()
        if old is None:
            raise ValueError(f"queue item {queue_id} not found")
        sets = ["status = ?"]
        vals = [new_status]
        if skip_reason is not None:
            sets.append("skip_reason = ?"); vals.append(skip_reason)
        if beat_id is not None:
            sets.append("beat_id = ?"); vals.append(beat_id)
        if suno_prompt is not None:
            sets.append("suno_prompt = ?"); vals.append(suno_prompt)
        vals.append(queue_id)
        c.execute(f"UPDATE daily_queue SET {', '.join(sets)} WHERE id = ?", vals)
        log_action("daily_queue", queue_id, "status_change",
                   {"from": old[0], "to": new_status,
                    "skip_reason": skip_reason, "beat_id": beat_id}, conn=c)
        return True


# --- suno_prompts -------------------------------------------------------------

def save_prompt_template(color, prompt_type, style_prompt,
                         negative_prompt=None, variation_type="base", conn=None):
    if color not in _V3_COLORS:
        raise ValueError(f"unknown color: {color!r}")
    if prompt_type not in ("beat", "track"):
        raise ValueError(f"invalid prompt_type: {prompt_type!r}")
    with _v3_conn(conn) as c:
        cur = c.execute(
            "INSERT INTO suno_prompts (color, prompt_type, variation_type, "
            "style_prompt, negative_prompt) VALUES (?,?,?,?,?)",
            (color, prompt_type, variation_type, style_prompt, negative_prompt),
        )
        prompt_id = cur.lastrowid
        log_action("prompt", prompt_id, "create",
                   {"color": color, "prompt_type": prompt_type,
                    "variation_type": variation_type}, conn=c)
        return prompt_id


def bump_prompt_usage(prompt_id, conn=None):
    with _v3_conn(conn) as c:
        c.execute(
            "UPDATE suno_prompts SET times_used = times_used + 1, "
            "last_used_at = datetime('now') WHERE id = ?", (prompt_id,))


# --- uploads ------------------------------------------------------------------

def add_upload(track_id, platform, url=None, conn=None):
    with _v3_conn(conn) as c:
        cur = c.execute(
            "INSERT INTO uploads (track_id, platform, url, upload_status) "
            "VALUES (?,?,?, 'pending')", (track_id, platform, url))
        upload_id = cur.lastrowid
        log_action("upload", upload_id, "create",
                   {"track_id": track_id, "platform": platform}, conn=c)
        return upload_id


def update_upload_status(upload_id, new_status, error_message=None, conn=None):
    if new_status not in _UPLOAD_STATUSES:
        raise ValueError(f"invalid upload status: {new_status!r}")
    with _v3_conn(conn) as c:
        old = c.execute("SELECT upload_status FROM uploads WHERE id = ?",
                        (upload_id,)).fetchone()
        if old is None:
            raise ValueError(f"upload {upload_id} not found")
        if new_status == "live":
            c.execute("UPDATE uploads SET upload_status = ?, "
                      "uploaded_at = datetime('now') WHERE id = ?",
                      (new_status, upload_id))
        elif new_status == "failed":
            c.execute("UPDATE uploads SET upload_status = ?, "
                      "error_message = ? WHERE id = ?",
                      (new_status, error_message, upload_id))
        else:
            c.execute("UPDATE uploads SET upload_status = ? WHERE id = ?",
                      (new_status, upload_id))
        log_action("upload", upload_id, "status_change",
                   {"from": old[0], "to": new_status,
                    "error": error_message}, conn=c)
        return True


# --- stats helpers ------------------------------------------------------------

def v3_stats(conn=None):
    """Quick counts for a TUI dashboard or smoke test."""
    out = {}
    with _v3_conn(conn) as c:
        for tbl in ("identities_v3", "albums", "beats", "tracks_v3",
                    "daily_queue", "suno_prompts", "uploads", "pipeline_log"):
            out[tbl] = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    return out


# ============================================================================
# END v3 OPERATIONAL LAYER
# ============================================================================


# ============================================================
# PHASE 2 OPERATIONAL LAYER (M5)
# Added: 2026-05-15
# Frozen contract: do not modify above this line.
# ============================================================

import re as _re_p2
import os as _os_p2
import shutil as _shutil_p2

_INBOX_DIR = r"C:\Users\cettb\OneDrive\Masaüstü\rest_inbox"
_ARCHIVE_BEATS_DIR = "archive/beats"  # repo-relative


def _normalize_track_name(s):
    """Normalize track name: strip, lowercase, collapse whitespace to underscore.
    Raises ValueError if empty or contains invalid chars."""
    s = s.strip().lower()
    s = _re_p2.sub(r"\s+", "_", s)
    if not s:
        raise ValueError("track_name empty after normalization")
    if not _re_p2.fullmatch(r"[a-z0-9_]+", s):
        raise ValueError(f"track_name invalid: {s}")
    return s


def _validate_color_p2(color, conn):
    """Raise ValueError if color not in identities_v3."""
    row = conn.execute(
        "SELECT 1 FROM identities_v3 WHERE color = ?", (color,)
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown color: {color!r}")


def add_note(color, body, conn=None):
    """Insert a new note for the given identity color.
    Returns dict with id, color, body, created_at."""
    with _v3_conn(conn) as c:
        _validate_color_p2(color, c)
        body_stripped = body.strip() if body else ""
        if not body_stripped:
            raise ValueError("body cannot be empty")
        cur = c.execute(
            "INSERT INTO notes (color, body) VALUES (?, ?)",
            (color, body_stripped),
        )
        note_id = cur.lastrowid
        log_action("notes", note_id, "create",
                   f"color={color}, len={len(body_stripped)}", conn=c)
        row = c.execute(
            "SELECT id, color, body, created_at FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()
        return _row_to_dict(row)


def get_notes(color, limit=20, conn=None):
    """Return up to `limit` notes for the given color, newest first."""
    with _v3_conn(conn) as c:
        _validate_color_p2(color, c)
        c.row_factory = _sqlite3_v3.Row
        rows = c.execute(
            "SELECT id, color, body, created_at, updated_at "
            "FROM notes WHERE color = ? ORDER BY id DESC LIMIT ?",
            (color, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def rate_beat(beat_id, rating_id, rating_flow, rating_beat_score,
              rating_energy, rating_replay, rating_note=None, conn=None):
    """Rate a beat on 5 dimensions (each 1..5). Updates the beat row."""
    ratings = {
        "rating_id": rating_id,
        "rating_flow": rating_flow,
        "rating_beat": rating_beat_score,
        "rating_energy": rating_energy,
        "rating_replay": rating_replay,
    }
    for name, val in ratings.items():
        if not isinstance(val, int) or val < 1 or val > 5:
            raise ValueError(f"{name} must be 1..5")

    with _v3_conn(conn) as c:
        row = c.execute("SELECT id FROM beats WHERE id = ?", (beat_id,)).fetchone()
        if row is None:
            raise ValueError("beat not found")
        c.execute(
            "UPDATE beats SET rating_id = ?, rating_flow = ?, rating_beat = ?, "
            "rating_energy = ?, rating_replay = ?, rating_note = ? WHERE id = ?",
            (rating_id, rating_flow, rating_beat_score,
             rating_energy, rating_replay, rating_note, beat_id),
        )
        log_action("beat", beat_id, "rate",
                   f"id={rating_id} flow={rating_flow} beat={rating_beat_score} "
                   f"energy={rating_energy} replay={rating_replay}", conn=c)
        return {
            "beat_id": beat_id,
            "ratings": ratings,
            "rating_note": rating_note,
        }


def get_recent_beats(color, limit=10, conn=None):
    """Return up to `limit` beats for the given color, newest first.
    Includes all columns (v3 + Phase 2)."""
    with _v3_conn(conn) as c:
        _validate_color_p2(color, c)
        c.row_factory = _sqlite3_v3.Row
        rows = c.execute(
            "SELECT * FROM beats WHERE color = ? ORDER BY id DESC LIMIT ?",
            (color, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def register_beat_mp3(color, track_name, source_path=None, conn=None):
    """Inbox -> archive workflow. Copy MP3 to archive, insert beats row."""
    normalized = _normalize_track_name(track_name)

    with _v3_conn(conn) as c:
        _validate_color_p2(color, c)

        # Resolve source
        if source_path is None:
            source = _os_p2.path.join(_INBOX_DIR, f"{normalized}.mp3")
        else:
            source = source_path
        if not _os_p2.path.isfile(source):
            raise FileNotFoundError(source)

        # Next version
        row = c.execute(
            "SELECT COALESCE(MAX(version_num), 0) + 1 FROM beats "
            "WHERE color = ? AND track_name = ?",
            (color, normalized),
        ).fetchone()
        next_version = row[0]

        # Archive path (repo-relative, forward slashes for DB)
        archive_rel = (
            f"{_ARCHIVE_BEATS_DIR}/{color}/{normalized}/"
            f"{normalized}_v{next_version}.mp3"
        )
        archive_abs = _os_p2.path.join(str(ROOT), archive_rel.replace("/", _os_p2.sep))

        # Create dir, check dest not exists
        _os_p2.makedirs(_os_p2.path.dirname(archive_abs), exist_ok=True)
        if _os_p2.path.exists(archive_abs):
            raise FileExistsError(archive_abs)

        # Copy file first
        _shutil_p2.copy2(source, archive_abs)

        # Insert beats row
        try:
            cur = c.execute(
                "INSERT INTO beats (color, suno_prompt, track_name, version_num, mp3_path) "
                "VALUES (?, '', ?, ?, ?)",
                (color, normalized, next_version, archive_rel),
            )
            beat_id = cur.lastrowid
        except Exception:
            # Cleanup copied file on DB failure
            try:
                _os_p2.remove(archive_abs)
            except OSError:
                pass
            raise

        log_action("beat", beat_id, "register_mp3",
                   f"color={color} track={normalized} v={next_version} "
                   f"path={archive_rel}", conn=c)

        # Inbox cleanup (best-effort)
        source_deleted = False
        try:
            _os_p2.remove(source)
            source_deleted = True
        except OSError as e:
            log_action("beat", beat_id, "inbox_cleanup_failed",
                       str(e), conn=c)

        return {
            "beat_id": beat_id,
            "color": color,
            "track_name": normalized,
            "version_num": next_version,
            "mp3_path": archive_rel,
            "source_deleted": source_deleted,
        }


def get_beat_versions(color, track_name, conn=None):
    """List all versions of a beat by track_name, ordered ascending."""
    normalized = _normalize_track_name(track_name)
    with _v3_conn(conn) as c:
        _validate_color_p2(color, c)
        c.row_factory = _sqlite3_v3.Row
        rows = c.execute(
            "SELECT id, color, track_name, version_num, mp3_path, created_at, "
            "rating_id, rating_flow, rating_beat, rating_energy, "
            "rating_replay, rating_note "
            "FROM beats WHERE color = ? AND track_name = ? "
            "ORDER BY version_num ASC",
            (color, normalized),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


# ============================================================
# PHASE 2 SMOKE TESTS
# ============================================================

if __name__ == "__main__" and _os_p2.environ.get("REST_SMOKE_PHASE2") == "1":
    import traceback

    _smoke_db = _sqlite3_v3.connect(_DB_PATH_V3)
    _smoke_db.execute("PRAGMA foreign_keys = ON;")
    _smoke_db.row_factory = _sqlite3_v3.Row

    def _smoke_test(name, fn):
        try:
            _smoke_db.execute("BEGIN")
            fn()
            print(f"smoke OK: {name}")
        except Exception:
            print(f"smoke FAIL: {name}")
            traceback.print_exc()
            raise
        finally:
            _smoke_db.rollback()

    def _test_add_note():
        result = add_note("grey", "smoke test note", conn=_smoke_db)
        assert result["color"] == "grey"
        assert result["body"] == "smoke test note"
        assert "id" in result

    def _test_get_notes():
        add_note("grey", "smoke get test", conn=_smoke_db)
        notes = get_notes("grey", limit=1, conn=_smoke_db)
        assert len(notes) >= 1
        assert notes[0]["color"] == "grey"

    def _test_rate_beat():
        beat_id = add_beat("grey", "smoke prompt", conn=_smoke_db)
        result = rate_beat(beat_id, 3, 4, 5, 2, 1, rating_note="ok", conn=_smoke_db)
        assert result["beat_id"] == beat_id
        assert result["ratings"]["rating_id"] == 3

    def _test_get_recent_beats():
        beats = get_recent_beats("grey", limit=5, conn=_smoke_db)
        assert isinstance(beats, list)

    def _test_register_beat_mp3():
        # Create dummy inbox mp3
        inbox = _os_p2.path.join(_INBOX_DIR, "_smoketest.mp3")
        _os_p2.makedirs(_INBOX_DIR, exist_ok=True)
        with open(inbox, "wb") as f:
            f.write(b"SMOKETEST")
        result = register_beat_mp3("grey", "_smoketest", conn=_smoke_db)
        assert result["color"] == "grey"
        assert result["track_name"] == "_smoketest"
        assert result["version_num"] == 1
        assert "mp3_path" in result
        # Verify archive file exists
        archive_abs = _os_p2.path.join(str(ROOT), result["mp3_path"].replace("/", _os_p2.sep))
        assert _os_p2.path.isfile(archive_abs), f"archive missing: {archive_abs}"
        # Verify inbox gone
        assert not _os_p2.path.isfile(inbox), "inbox file should be deleted"
        # Cleanup: remove archive file + dirs
        _os_p2.remove(archive_abs)
        try:
            _os_p2.removedirs(_os_p2.path.dirname(archive_abs))
        except OSError:
            pass

    def _test_get_beat_versions():
        # Insert two temp beats directly
        _smoke_db.execute(
            "INSERT INTO beats (color, suno_prompt, track_name, version_num) "
            "VALUES ('grey', '', 'smoke_versions', 1)")
        _smoke_db.execute(
            "INSERT INTO beats (color, suno_prompt, track_name, version_num) "
            "VALUES ('grey', '', 'smoke_versions', 2)")
        versions = get_beat_versions("grey", "smoke_versions", conn=_smoke_db)
        assert len(versions) == 2
        assert versions[0]["version_num"] == 1
        assert versions[1]["version_num"] == 2

    _smoke_test("add_note", _test_add_note)
    _smoke_test("get_notes", _test_get_notes)
    _smoke_test("rate_beat", _test_rate_beat)
    _smoke_test("get_recent_beats", _test_get_recent_beats)
    _smoke_test("register_beat_mp3", _test_register_beat_mp3)
    _smoke_test("get_beat_versions", _test_get_beat_versions)

    _smoke_db.close()
    print("\n6/6 smoke tests passed")
