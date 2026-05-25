BEGIN TRANSACTION;

ALTER TABLE beats ADD COLUMN track_name  TEXT NULL;
ALTER TABLE beats ADD COLUMN version_num INTEGER NULL CHECK (version_num IS NULL OR version_num >= 1);

CREATE INDEX idx_beats_color_track ON beats(color, track_name);
CREATE UNIQUE INDEX idx_beats_color_track_version_uniq
    ON beats(color, track_name, version_num)
    WHERE track_name IS NOT NULL;

COMMIT;
