# REST V1.1 — Versioned Governance

**Schema version:** Explicit in each schema (`$id`, `version` where applicable).

**Source of truth:** JSON. Python is tooling only.

**Null policy:** Use `null` instead of omission for optional fields in canonical JSON.

**Determinism:** No randomness. No timestamps in deterministic chains. No state mixing.

**Lifecycle:** One scope per commit. Legacy tracks in `tracks_deprecated/` are read-only.

**Deterministic chain:** For any work iteration the linkage is explicit: `work_id` → `prompt_version` → `suggestion_hash` → `seed_hash_hex` → `export_path`. All state written in JSON.

**Structural rules:** No renaming of established structures. No aesthetic drift. No spontaneous refactors.

**Validation:** Before any modification run `python python/validate.py`. If FAIL: list violations; do not fix unless explicitly instructed.

**Active tracks:** Exactly 5. Defined in `schemas/track.schema.json` enum. `tracks/` holds only those; deprecated material in `tracks_deprecated/` only.
