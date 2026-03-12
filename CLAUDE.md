# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

REST Engine is a deterministic JSON-driven rap-techno production system for the Radical Noface project. It manages a 5-color consciousness model (grey, blue, green, cream, black) with structured Suno prompt pipelines. Current version: v1.1.0. Album 5 preproduction is frozen — see `domain/phase_freeze_album5.json`.

## Commands

**Validate (must pass before any change):**
```
python python/validate.py
```
Windows shorthand: `py -X faulthandler python/validate.py`
Batch/PS1 wrappers: `scripts\validate.cmd` or `scripts\validate.ps1`

**Dashboard UI:**
```
python python/dashboard.py
```

**Generate suggestions:**
```
python python/suggest.py
```

**Export Suno prompts:**
```
python python/suno_export.py
```

**Dependencies:** `pip install -r python/requirements.txt` (jsonschema>=4, textual>=0.40)
**Python version:** 3.12.6 (set in `.python-version`)

## Architecture

**JSON is the single source of truth.** Python is tooling only — it reads/validates/exports but never owns state.

### Layer map

| Layer | Path | Role |
|-------|------|------|
| Domain config | `domain/` | Locked structures: identities, manifest, sound map, scoring, prompt format |
| Schemas | `schemas/` | JSON Schema definitions for tracks, suggestions, sound library, runs |
| Tracks | `tracks/` | Exactly 5 active track files (`radical.{color}.json`), each bound to sound library assets |
| Sound library | `knowledge/sound_library.json` | 30 assets (5 per color: kick, bass, hat, pad, texture) |
| Registry | `knowledge/registry.json` | Track count and run tracking |
| Python tooling | `python/` | validate, suggest, export, dashboard, UI |
| Claude docs | `claude/` | Identity, handoff, validation, reference, status |
| Legacy (read-only) | `chatgpt/rest/_quarantine_legacy_7id/` | Deprecated 7-sin tracks, never modify |

### Validation pipeline

`validate.py` checks: schema integrity, exactly 5 tracks, registry consistency, sound library binding (each track's `library_binding` keys map to matching `color_state` assets), album duration policy, and jsonschema conformance. Exit 0 = PASS, exit 1 = FAIL with violations. CI runs this on every push/PR via `.github/workflows/validate.yml`.

### Deterministic hashing

Prompt generation follows a deterministic chain: `work_id` -> `prompt_version` -> `suggestion_hash` (SHA256 of payload: prompt_text | bpm_override | sound_class | color | emotion_core) -> `seed_hash_hex` -> `export_path`. No randomness or timestamps in config.

### Track-to-sound binding

Each track's `library_binding` (kick/bass/hat/lead/texture) must reference assets in `knowledge/sound_library.json` whose `color_state` matches the track color. Validation enforces this.

## Core Rules

- **Null instead of omission:** Always use explicit `null` for absent optional fields in JSON; never omit the key.
- **One scope per commit:** Each commit touches one directory or one logical unit. No batched multi-scope edits.
- **EXECUTE -> VALIDATE -> COMMIT -> STOP:** Run validation before committing. If validation fails, report violations and stop.
- **No randomness in config:** All state must be explicit and reproducible.
- **Phase freeze:** `domain/phase_freeze_album5.json` is frozen. Do not edit frozen domain files unless explicitly instructed.
- **Legacy is read-only:** Never modify files under `chatgpt/rest/_quarantine_legacy_7id/` or `tracks_deprecated/`.
- **5 colors only:** grey, blue, green, cream, black. Never introduce new colors or revert to the old 7-identity system.

## Governance

Full behavioral rules and identity definition live in `GOVERNANCE.md`. Cursor execution rules in `.cursor/rules/`. Claude-specific onboarding sequence in `claude/README.md` (read order: IDENTITY -> HANDOFF -> VALIDATION -> REFERENCE).
