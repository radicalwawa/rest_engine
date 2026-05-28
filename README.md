# rest_engine

Deterministic JSON-driven rap-techno production engine with a 5-color consciousness model and structured Suno prompt pipeline.

## Quickstart — Validation

From repo root:

- **Windows:** `py -X faulthandler python/validate.py`  
  If `python` hangs, disable Windows Store "App execution aliases" for python.exe/python3.exe (see GOVERNANCE.md).
- **Scripts:** `scripts\validate.cmd` or `scripts\validate.ps1` (Windows) for a deterministic entrypoint.

Policy: GOVERNANCE.md, docs/PRODUCTION_LOCK.md. Claude entry: `claude/README.md`.

## Repository layers

- **JSON / Schemas:** Single source of truth. Schemas in `schemas/`. Null instead of omission.
- **Python:** Tooling only. `python/validate.py`, production scripts under `python/production/`.
- **Suno:** Export and prompt pipeline; references tracks and sound library.

## v2.0 — SQL Operational Layer (Phase 1+2)

- **rest_engine.db** — SQLite operational state. Schema in `migrations/`, seeded from
  `domain/identities_v3_seed.json`.
- **db_manager.py** — CRUD layer over `rest_engine.db`. All DB access goes through this.
- **prompt_engine.py** — Suno prompt variations (base, bpm_shift, mood_shift,
  instrument_swap, energy_shift, track). DB-backed.
- **daily_pipeline.py** — Operational flow: `init_daily_queue` → `stage_prompts` →
  `process_queue_item` → `review_beat`.
- **tui.py** — Textual dashboard. 5-color identity panels, rating + notes UI, MP3
  archive workflow.
- **sdm_tool.py** — Successor Document Memo (MIRAS) bookkeeping. Commands:
  `touch <sdm.json>`, `event`, `mission`.

### Workflow: Suno → archive → rate
1. Generate track in Suno from prompt.
2. Download mp3 to `rest_inbox/`.
3. Call `register_beat_mp3(color, track_name)` (or via TUI). MP3 is copied to
   `archive/beats/<color>/<track>/<track>_vN.mp3`, beats row inserted.
4. Rate 5 dimensions (id, flow, beat, energy, replay) on 1–5 scale + free-form note.
5. notes table stores color-scoped feedback that `prompt_engine` reads on next generation.

### Tests
Full 10/10 validation suite in `tests/validation_phase1.py` and
`tests/validation_phase2_step_{a,a2,b,b2,c,d,e,f,g}.py`. All idempotent.

## Sound library

- `knowledge/sound_library.json` — asset catalog (schema: `schemas/sound_library.schema.json`).
- Each active track must have `library_binding` with keys: kick, bass, hat, lead, texture (asset ids from the library).
- Validation enforces binding integrity and color_state match.

## Duration policy

- `domain/album_5_manifest.json` — `release_format` defines radio and extended version targets (sec), min/target/max, and release strategy.
- Validation enforces numeric ranges and separation rule (radio max < extended min).

## Governance

One scope per commit. Validate before commit. No spontaneous refactors. See GOVERNANCE.md and docs/PRODUCTION_LOCK.md.
