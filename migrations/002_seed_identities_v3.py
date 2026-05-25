"""
migrations/002_seed_identities_v3.py
Seed identities_v3 from domain/identities_v3_seed.json.
Idempotent: uses INSERT OR REPLACE so re-runs are safe.
Logs every insert to pipeline_log.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "rest_engine.db"
SEED_PATH = ROOT / "domain" / "identities_v3_seed.json"

JSON_ARRAY_COLS = {
    "key_signatures",
    "instrumentation_rap",
    "instrumentation_techno",
    "instrumentation_shared",
}

COLUMNS = [
    "color", "surname", "rap_genre", "techno_genre", "hybrid_label",
    "bpm_min", "bpm_max", "mood", "energy", "vocal_character",
    "key_signatures", "instrumentation_rap", "instrumentation_techno",
    "instrumentation_shared", "mix_character", "stereo_width",
    "reverb_profile", "low_end", "high_end", "compression_style",
    "suno_base_prompt", "negative_prompt",
]

def main():
    if not SEED_PATH.exists():
        print(f"ERROR: seed file not found: {SEED_PATH}", file=sys.stderr)
        sys.exit(1)
    if not DB_PATH.exists():
        print(f"ERROR: db not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    identities = data.get("identities", [])
    if len(identities) != 5:
        print(f"ERROR: expected 5 identities, got {len(identities)}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    placeholders = ",".join(["?"] * len(COLUMNS))
    sql = f"INSERT OR REPLACE INTO identities_v3 ({','.join(COLUMNS)}) VALUES ({placeholders})"

    inserted = []
    for ident in identities:
        row = []
        for col in COLUMNS:
            val = ident.get(col)
            if col in JSON_ARRAY_COLS:
                val = json.dumps(val if val is not None else [], ensure_ascii=False)
            row.append(val)
        cur.execute(sql, row)
        cur.execute(
            "INSERT INTO pipeline_log (entity_type, entity_id, action, details) VALUES (?,?,?,?)",
            ("identity_v3", None, "seed", json.dumps({"color": ident["color"], "surname": ident["surname"]}, ensure_ascii=False)),
        )
        inserted.append(ident["color"])

    conn.commit()

    cur.execute("SELECT color, surname, hybrid_label, bpm_min, bpm_max FROM identities_v3 ORDER BY color")
    rows = cur.fetchall()
    conn.close()

    print(f"seeded {len(inserted)} identities: {inserted}")
    print("identities_v3 contents:")
    for r in rows:
        print(f"  {r[0]:6s} | {r[1]:10s} | {r[2]:30s} | bpm {r[3]}-{r[4]}")

if __name__ == "__main__":
    main()
