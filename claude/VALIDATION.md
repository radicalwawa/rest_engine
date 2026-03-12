# Validation and stop/proceed

## What validate.py actually validates

Run from repo root: `python python/validate.py`. It checks:

- **Schemas:** Presence and structure of `schemas/*.schema.json`; `$id` and `version` when present must not be null.
- **Tracks:** Exactly five JSON files in `tracks/`, each with `id` in the enum (radical.grey, radical.blue, radical.green, radical.cream, radical.black); no active track under tracks_deprecated.
- **Registry:** `knowledge/registry.json` must have run_ids (array), updated_at (null or string), notes (null or string).
- **Sound library:** `knowledge/sound_library.json` schema_version and assets; asset color_state in the five states; notes and updated_at per asset; unique asset ids.
- **Track–library binding:** Each active track must have `library_binding` with keys kick, bass, hat, lead, texture; each value an asset id present in the library with matching color_state for that track.
- **Album duration:** `domain/album_5_manifest.json` must have `release_format` with the required keys and integer constraints; radio_version_max_sec < extended_version_min_sec.
- **Schema validation:** Tracks are validated against `schemas/track.schema.json` via jsonschema.

It does **not** validate suggestion outputs (e.g. `python/out/suggestions/*.suggestion.json`). Source of truth for validation behavior is `python/validate.py`.

## PASS / FAIL

- **PASS:** Script exits 0, prints SYSTEM STATUS: PASS. Safe to proceed with the requested scope.
- **FAIL:** Script exits non-zero, prints SYSTEM STATUS: FAIL and violation lines (path + reason). Do not fix unless explicitly instructed; report and stop.

## When to stop

Stop after reporting FAIL. Stop after a successful commit (output commit hash, then wait). Do not suggest next action or enhancements after completion.

## CI

`.github/workflows/validate.yml` runs on push and pull_request to master/main: checkout, setup-python from `.python-version`, install `python/requirements.txt`, run `python python/validate.py`. The same validation is the gate.
