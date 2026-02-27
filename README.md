# rest_engine

Deterministic JSON-driven rap-techno production engine with a 5-color consciousness model and structured Suno prompt pipeline.

## Quickstart — Validation

From repo root:

- **Windows:** `py -X faulthandler python/validate.py`  
  If `python` hangs, disable Windows Store "App execution aliases" for python.exe/python3.exe (see GOVERNANCE.md).
- **Scripts:** `scripts\validate.cmd` or `scripts\validate.ps1` (Windows) for a deterministic entrypoint.

Policy: GOVERNANCE.md, docs/PRODUCTION_LOCK.md.

## Repository layers

- **JSON / Schemas:** Single source of truth. Schemas in `schemas/`. Null instead of omission.
- **Python:** Tooling only. `python/validate.py`, production scripts under `python/production/`.
- **Cursor:** Execution discipline; rules in `.cursor/rules/`.
- **Suno:** Export and prompt pipeline; references tracks and sound library.

## Sound library

- `knowledge/sound_library.json` — asset catalog (schema: `schemas/sound_library.schema.json`).
- Each active track must have `library_binding` with keys: kick, bass, hat, lead, texture (asset ids from the library).
- Validation enforces binding integrity and color_state match.

## Duration policy

- `domain/album_5_manifest.json` — `release_format` defines radio and extended version targets (sec), min/target/max, and release strategy.
- Validation enforces numeric ranges and separation rule (radio max < extended min).

## Governance

One scope per commit. Validate before commit. No spontaneous refactors. See GOVERNANCE.md and docs/PRODUCTION_LOCK.md.
