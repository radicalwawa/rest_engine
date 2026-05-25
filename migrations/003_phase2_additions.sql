BEGIN TRANSACTION;

-- notes tablosu: kimlik bazlı append-only not defteri
CREATE TABLE notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    color       TEXT NOT NULL REFERENCES identities_v3(color),
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_notes_color ON notes(color);

-- beats: 5 boyutlu rating sistemi + rating_note + mp3_path
ALTER TABLE beats ADD COLUMN rating_id     INTEGER NULL CHECK (rating_id     IS NULL OR rating_id     BETWEEN 1 AND 5);
ALTER TABLE beats ADD COLUMN rating_flow   INTEGER NULL CHECK (rating_flow   IS NULL OR rating_flow   BETWEEN 1 AND 5);
ALTER TABLE beats ADD COLUMN rating_beat   INTEGER NULL CHECK (rating_beat   IS NULL OR rating_beat   BETWEEN 1 AND 5);
ALTER TABLE beats ADD COLUMN rating_energy INTEGER NULL CHECK (rating_energy IS NULL OR rating_energy BETWEEN 1 AND 5);
ALTER TABLE beats ADD COLUMN rating_replay INTEGER NULL CHECK (rating_replay IS NULL OR rating_replay BETWEEN 1 AND 5);
ALTER TABLE beats ADD COLUMN rating_note   TEXT NULL;
ALTER TABLE beats ADD COLUMN mp3_path      TEXT NULL;

COMMIT;
