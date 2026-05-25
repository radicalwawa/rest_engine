PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- pipeline_log tablosunu yeniden oluştur: entity_type CHECK'e 'notes' eklendi
CREATE TABLE pipeline_log_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL DEFAULT (datetime('now')),
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('beat','track','album','daily_queue','prompt','upload','identity_v3','notes')),
    entity_id       INTEGER,
    action          TEXT NOT NULL,
    details         TEXT
);

INSERT INTO pipeline_log_new SELECT * FROM pipeline_log;

-- satır sayısı doğrulama (uygulama katmanında kontrol edilecek)

DROP TABLE pipeline_log;
ALTER TABLE pipeline_log_new RENAME TO pipeline_log;

-- Mevcut indexleri yeniden oluştur
CREATE INDEX idx_pipeline_log_entity ON pipeline_log(entity_type, entity_id);
CREATE INDEX idx_pipeline_log_ts ON pipeline_log(ts);

COMMIT;
PRAGMA foreign_keys=ON;
