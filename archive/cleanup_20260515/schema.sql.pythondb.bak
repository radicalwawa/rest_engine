-- REST Engine SQLite Schema
-- Generated from JSON source-of-truth files
-- JSON remains canonical; this DB is a read/query overlay

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Artists (from artists/artist_base.json)
CREATE TABLE IF NOT EXISTS artists (
    artist_id       TEXT PRIMARY KEY,
    version         TEXT NOT NULL,
    max_bars        INTEGER NOT NULL,
    lyrical_complexity TEXT NOT NULL,
    vocal_melodic_range TEXT NOT NULL,
    delivery_style  TEXT NOT NULL,
    persona         TEXT NOT NULL,
    melodic_expressiveness TEXT NOT NULL,
    emotional_variance TEXT NOT NULL,
    performance_flash TEXT NOT NULL
);

-- Identities (from domain/album5_identities.json)
CREATE TABLE IF NOT EXISTS identities (
    track_id        TEXT PRIMARY KEY,
    state_label     TEXT NOT NULL,
    genre_stack     TEXT NOT NULL,  -- JSON array
    bpm_min         INTEGER NOT NULL,
    bpm_max         INTEGER NOT NULL,
    groove          TEXT NOT NULL,
    drum_language   TEXT NOT NULL,
    bass_language   TEXT NOT NULL,
    harmony_policy  TEXT NOT NULL,
    ambience_policy TEXT NOT NULL,
    fx_policy       TEXT NOT NULL,  -- JSON object
    energy_curve    TEXT NOT NULL,
    vocal_delivery  TEXT NOT NULL,  -- JSON object
    mix_targets     TEXT NOT NULL,  -- JSON object
    suno_prompt_guidelines TEXT NOT NULL  -- JSON object
);

-- Tracks (from tracks/radical.*.json)
CREATE TABLE IF NOT EXISTS tracks (
    id              TEXT PRIMARY KEY,
    version         TEXT NOT NULL,
    theme           TEXT NOT NULL,
    energy_profile  TEXT NOT NULL,
    emotional_tone  TEXT NOT NULL,
    lyrical_focus   TEXT NOT NULL,
    keyword_vector  TEXT NOT NULL,  -- JSON array
    drive_level     TEXT NOT NULL,
    bass_weight     TEXT NOT NULL,
    texture_type    TEXT NOT NULL,
    spatial_depth   TEXT NOT NULL,
    bpm_override    INTEGER,
    structure_override TEXT,
    tested_bpms     TEXT NOT NULL,  -- JSON array
    proven_bpm      INTEGER,
    drift_notes     TEXT NOT NULL,  -- JSON array
    binding_kick    TEXT NOT NULL,
    binding_bass    TEXT NOT NULL,
    binding_hat     TEXT NOT NULL,
    binding_lead    TEXT NOT NULL,
    binding_texture TEXT NOT NULL
);

-- Sound Library (from knowledge/sound_library.json)
CREATE TABLE IF NOT EXISTS sound_library (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL CHECK(type IN ('one_shot','loop','preset','fx_chain','midi','vocal')),
    color_state     TEXT NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('kick','bass','hat','perc','synth','pad','texture','fx','riser','vocal','atmos')),
    intensity       INTEGER NOT NULL CHECK(intensity BETWEEN 1 AND 5),
    tags            TEXT NOT NULL,  -- JSON array
    path            TEXT NOT NULL,
    license_source  TEXT NOT NULL,
    license_usage   TEXT NOT NULL,
    license_attribution TEXT,
    notes           TEXT,
    updated_at      TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','deprecated')),
    bpm_range_min   INTEGER,
    bpm_range_max   INTEGER,
    key             TEXT,
    duration_ms     INTEGER,
    loudness_lufs   REAL,
    checksum_sha256 TEXT
);

-- Sound Map (color-to-profile mapping from domain_lock calibration_bpm_set + identity bindings)
CREATE TABLE IF NOT EXISTS sound_map (
    color           TEXT PRIMARY KEY,
    domain_model    TEXT NOT NULL,
    genre_bias      TEXT NOT NULL,
    calibration_bpm_set TEXT NOT NULL,  -- JSON array
    bpm_policy      TEXT NOT NULL,
    mode_default    TEXT NOT NULL
);

-- Works (from domain/works_manifest.json)
CREATE TABLE IF NOT EXISTS works (
    work_id         TEXT PRIMARY KEY,
    track_id        TEXT NOT NULL REFERENCES identities(track_id),
    series          TEXT NOT NULL,
    title           TEXT NOT NULL,
    volume          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    notes           TEXT
);

-- Scores (5-key scoring: mix, vocal, color, flow, replay; 0-10 each, total 50)
CREATE TABLE IF NOT EXISTS scores (
    score_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id         TEXT NOT NULL REFERENCES works(work_id),
    mix             INTEGER NOT NULL CHECK(mix BETWEEN 0 AND 10),
    vocal           INTEGER NOT NULL CHECK(vocal BETWEEN 0 AND 10),
    color           INTEGER NOT NULL CHECK(color BETWEEN 0 AND 10),
    flow            INTEGER NOT NULL CHECK(flow BETWEEN 0 AND 10),
    replay          INTEGER NOT NULL CHECK(replay BETWEEN 0 AND 10),
    total           INTEGER GENERATED ALWAYS AS (mix + vocal + color + flow + replay) STORED,
    scored_at       TEXT NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

-- Audio Files (wav/mp3 paths + suno references)
CREATE TABLE IF NOT EXISTS audio_files (
    file_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id         TEXT NOT NULL REFERENCES works(work_id),
    file_path       TEXT NOT NULL,
    file_type       TEXT NOT NULL CHECK(file_type IN ('wav','mp3','flac','aac')),
    suno_ref        TEXT,
    version_tag     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

-- Prompts (suno prompt exports)
CREATE TABLE IF NOT EXISTS prompts (
    prompt_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id        TEXT NOT NULL REFERENCES identities(track_id),
    prompt_text     TEXT NOT NULL,
    variation       TEXT NOT NULL CHECK(variation IN ('v0','v1','v2')),
    seed_hash_hex   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

-- Lyrics
CREATE TABLE IF NOT EXISTS lyrics (
    lyric_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id         TEXT NOT NULL REFERENCES works(work_id),
    track_id        TEXT NOT NULL REFERENCES identities(track_id),
    content         TEXT NOT NULL,
    bar_count       INTEGER,
    language        TEXT NOT NULL DEFAULT 'tr',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

-- Delta Events (revision/change log)
CREATE TABLE IF NOT EXISTS delta_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type     TEXT NOT NULL CHECK(target_type IN ('track','work','prompt','score','audio','identity')),
    target_id       TEXT NOT NULL,
    action          TEXT NOT NULL CHECK(action IN ('create','update','delete','score','revision')),
    delta_payload   TEXT NOT NULL,  -- JSON diff
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    actor           TEXT NOT NULL DEFAULT 'system'
);

-- Runs (from run_manifest schema)
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    mode            TEXT NOT NULL CHECK(mode IN ('production','calibration')),
    track_id        TEXT NOT NULL REFERENCES identities(track_id),
    bpm             INTEGER NOT NULL,
    prompt_files    TEXT NOT NULL,  -- JSON array
    notes           TEXT,
    -- run_results fields (nullable, filled after run completes)
    stability_score INTEGER CHECK(stability_score BETWEEN 1 AND 5),
    drift_type      TEXT CHECK(drift_type IN ('none','vocal','rhythm','structure','genre','texture')),
    drift_severity  TEXT CHECK(drift_severity IN ('none','minor','moderate','critical')),
    drift_notes     TEXT,
    suno_refs       TEXT,  -- JSON array
    corrective_adjustment TEXT,
    result_after_adjustment TEXT
);

-- Revision Rules (from domain/revision_rules.json)
CREATE TABLE IF NOT EXISTS revision_rules (
    key             TEXT PRIMARY KEY,
    when_below      INTEGER NOT NULL,
    prompt_append_tr TEXT NOT NULL,
    tighten         TEXT NOT NULL,  -- JSON object
    loosen          TEXT
);

-- Freeze State (from domain/phase_freeze_album5.json)
CREATE TABLE IF NOT EXISTS freeze_state (
    phase           TEXT PRIMARY KEY,
    status          TEXT NOT NULL CHECK(status IN ('frozen','active','archived')),
    frozen_at       TEXT,
    notes           TEXT,
    components      TEXT NOT NULL,  -- JSON object
    python_components TEXT NOT NULL,  -- JSON object
    engine_state    TEXT NOT NULL   -- JSON object
);
