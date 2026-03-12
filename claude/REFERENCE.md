# Reference — where things live

## domain

Configuration and locked structure. Paths relative to repo root.

- `domain/domain_lock.json` — 5-color model, active colors, genre/prompt/vocal policy
- `domain/phase_freeze_album5.json` — Frozen phase; do not edit
- `domain/sound_map.json` — track_to_color_v2, mappings (genre, sound_class, rap_identity)
- `domain/album5_identities.json` — Per-track identity (state_label, genre_stack, bpm, vocal_delivery)
- `domain/album_5_manifest.json` — release_format (radio/extended durations, release_strategy)
- `domain/works_manifest.json` — works list (work_id, track_id, series)
- `domain/revision_rules.json` — Score keys, thresholds, prompt_append_tr
- `domain/acapella_protocol.json` — Acapella protocol
- `domain/score_schema.json` — Score schema
- `domain/suno_prompt_format.json` — Suno prompt format

## schemas

JSON schemas. All under `schemas/`.

- `schemas/track.schema.json` — Track; id enum 5 colors; library_binding, techno_profile, etc.
- `schemas/suggestion.schema.json` — Suggestion (track_id, prompt_text, resolved)
- `schemas/sound_library.schema.json` — Sound library
- `schemas/run_manifest.schema.json` — Run manifest
- `schemas/run_results.schema.json` — Run results

## knowledge

- `knowledge/registry.json` — version, active_tracks (5), run_ids, updated_at
- `knowledge/sound_library.json` — Asset catalog, color_profiles, kits/flows/templates
- `knowledge/SUCCESSOR_PROMPT.md` — Successor identity and first action
- `knowledge/OPSLOG.md` — Migration and conventions log

## python

Tooling only. Entry: `python/validate.py`. Scripts: `python/ui.py`, `python/dashboard.py`, `python/suggest.py`, `python/suno_export.py`, `python/run_index.py`, `python/dataset.py`. Production: `python/production/` (e.g. `sydbkh.py`). Config: `python/requirements.txt`. Outputs under `python/out/` are gitignored except `python/out/suggestions_deprecated/`.

## docs

- `docs/PRODUCTION_LOCK.md` — Production phase policy
- `docs/RELEASE_NOTES.md` — Version notes

## sdm

- `sdm/MIRAS.txt` — Handoff: structure, rules, identity. Canonical SDM is outside repo at `%USERPROFILE%\Desktop\SDM\sdm.json`.

## legacy quarantine

Read-only. Do not modify.

- `chatgpt/rest/_quarantine_legacy_7id/` — Legacy 7-sin knowledge, suggestions_deprecated, tracks_deprecated
