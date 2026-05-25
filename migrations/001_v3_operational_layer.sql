-- migrations/001_v3_operational_layer.sql
-- REST ENGINE — v3 operational layer
-- Adds beats, daily_queue, pipeline_log, suno_prompts, uploads, albums, identities_v3
-- Does NOT touch M2 tables. Idempotent (uses IF NOT EXISTS).

PRAGMA foreign_keys = ON;

-- v3 identity matrix (5-color hybrid). Separate from M2 identities table.
CREATE TABLE IF NOT EXISTS identities_v3 (
    color               TEXT PRIMARY KEY CHECK (color IN ('green','grey','blue','cream','black')),
    surname             TEXT NOT NULL,
    rap_genre           TEXT NOT NULL,
    techno_genre       TEXT NOT NULL,
    hybrid_label        TEXT NOT NULL,
    bpm_min             INTEGER NOT NULL,
    bpm_max             INTEGER NOT NULL,
    mood                TEXT,
    energy              TEXT,
    vocal_character     TEXT,
    key_signatures      TEXT,    -- JSON array
    instrumentation_rap     TEXT, -- JSON array
    instrumentation_techno  TEXT, -- JSON array
    instrumentation_shared  TEXT, -- JSON array
    mix_character       TEXT,
    stereo_width        TEXT,
    reverb_profile      TEXT,
    low_end             TEXT,
    high_end            TEXT,
    compression_style   TEXT,
    suno_base_prompt    TEXT NOT NULL,
    negative_prompt     TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Albums (containers for tracks).
CREATE TABLE IF NOT EXISTS albums (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    color       TEXT NOT NULL REFERENCES identities_v3(color),
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'planning' CHECK (status IN ('planning','in_progress','released','shelved')),
    target_track_count INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Beats (suno-generated instrumentals, pre-track).
CREATE TABLE IF NOT EXISTS beats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    color           TEXT NOT NULL REFERENCES identities_v3(color),
    suno_prompt     TEXT NOT NULL,
    negative_prompt TEXT,
    bpm             INTEGER,
    key_sig         TEXT,
    suno_url        TEXT,
    suno_audio_id   TEXT,
    duration_sec    INTEGER,
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','generated','reviewed','approved','rejected','archived')),
    reject_reason   TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_beats_color_status ON beats(color, status);
CREATE INDEX IF NOT EXISTS idx_beats_status ON beats(status);

-- Tracks v3 (full songs: beat + lyrics + vocals).
-- Named tracks_v3 to avoid collision with existing M2 tracks table.
CREATE TABLE IF NOT EXISTS tracks_v3 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    color           TEXT NOT NULL REFERENCES identities_v3(color),
    album_id        INTEGER REFERENCES albums(id),
    beat_id         INTEGER REFERENCES beats(id),
    title           TEXT NOT NULL,
    lyrics          TEXT,
    suno_url        TEXT,
    duration_sec    INTEGER,
    status          TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','generated','reviewed','approved','released','archived')),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tracks_v3_color_status ON tracks_v3(color, status);
CREATE INDEX IF NOT EXISTS idx_tracks_v3_album ON tracks_v3(album_id);

-- Daily queue (5 entries per day, one per identity).
CREATE TABLE IF NOT EXISTS daily_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_date      TEXT NOT NULL,                 -- YYYY-MM-DD
    color           TEXT NOT NULL REFERENCES identities_v3(color),
    beat_id         INTEGER REFERENCES beats(id),  -- filled when beat created
    suno_prompt     TEXT,                          -- prompt staged for the day
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','generated','reviewed','done','skipped')),
    skip_reason     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(queue_date, color)
);
CREATE INDEX IF NOT EXISTS idx_daily_queue_date ON daily_queue(queue_date);
CREATE INDEX IF NOT EXISTS idx_daily_queue_status ON daily_queue(status);

-- Suno prompt templates / variations log.
CREATE TABLE IF NOT EXISTS suno_prompts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    color           TEXT NOT NULL REFERENCES identities_v3(color),
    prompt_type     TEXT NOT NULL CHECK (prompt_type IN ('beat','track')),
    variation_type  TEXT,  -- bpm_shift, mood_shift, instrument_swap, energy_shift, base
    style_prompt    TEXT NOT NULL,
    negative_prompt TEXT,
    times_used      INTEGER NOT NULL DEFAULT 0,
    last_used_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_suno_prompts_color_type ON suno_prompts(color, prompt_type);

-- Uploads (track files pushed to distribution).
CREATE TABLE IF NOT EXISTS uploads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id        INTEGER NOT NULL REFERENCES tracks_v3(id),
    platform        TEXT NOT NULL,    -- spotify, soundcloud, youtube, etc.
    url             TEXT,
    upload_status   TEXT NOT NULL DEFAULT 'pending'
        CHECK (upload_status IN ('pending','uploading','live','failed','removed')),
    uploaded_at     TEXT,
    error_message   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_uploads_track ON uploads(track_id);

-- Pipeline log (single audit trail for all v3 operational writes).
CREATE TABLE IF NOT EXISTS pipeline_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL DEFAULT (datetime('now')),
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('beat','track','album','daily_queue','prompt','upload','identity_v3')),
    entity_id       INTEGER,
    action          TEXT NOT NULL,    -- e.g. 'create','status_change','approve','reject','upload_start'
    details         TEXT              -- JSON blob, free-form
);
CREATE INDEX IF NOT EXISTS idx_pipeline_log_entity ON pipeline_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_log_ts ON pipeline_log(ts);

-- Triggers to keep updated_at fresh on row update.
CREATE TRIGGER IF NOT EXISTS trg_identities_v3_updated
AFTER UPDATE ON identities_v3 FOR EACH ROW
BEGIN
    UPDATE identities_v3 SET updated_at = datetime('now') WHERE color = NEW.color;
END;

CREATE TRIGGER IF NOT EXISTS trg_albums_updated
AFTER UPDATE ON albums FOR EACH ROW
BEGIN
    UPDATE albums SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_beats_updated
AFTER UPDATE ON beats FOR EACH ROW
BEGIN
    UPDATE beats SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_tracks_v3_updated
AFTER UPDATE ON tracks_v3 FOR EACH ROW
BEGIN
    UPDATE tracks_v3 SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_queue_updated
AFTER UPDATE ON daily_queue FOR EACH ROW
BEGIN
    UPDATE daily_queue SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_uploads_updated
AFTER UPDATE ON uploads FOR EACH ROW
BEGIN
    UPDATE uploads SET updated_at = datetime('now') WHERE id = NEW.id;
END;
