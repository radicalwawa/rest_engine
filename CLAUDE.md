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
Dashboard commands: `/build` or `/b` (build Suno prompt), `/validate` or `/v`, `/export` or `/e`, `/color [name|1-5]` (switch track), `/works` or `/w`, `/save` (save lyrics). Keys: 1-5 (color select), Ctrl+B (build), Ctrl+R (validate), Tab (cycle focus).

**Generate suggestions:**
```
python python/suggest.py
```
CLI flags: `--track-id`, `--mode` (calibration|production), `--bpm`, `--out`

**Export Suno prompts:**
```
python python/suno_export.py
```
CLI flags: `--track_id` (default: radical.grey), `--variation` (v0/v1/v2)

**Build dataset from runs:**
```
python python/dataset.py
```

**Dependencies:** `pip install -r python/requirements.txt` (jsonschema>=4, textual>=0.40)
**Python version:** 3.12.6 (set in `.python-version`)
**CI:** `.github/workflows/validate.yml` runs `validate.py` on push/PR to master/main.

## Architecture

**JSON is the single source of truth.** Python is tooling only — it reads/validates/exports but never owns state.

### Layer map

| Layer | Path | Role |
|-------|------|------|
| Domain config | `domain/` | Locked structures: identities, manifest, sound map, scoring, prompt format, phase freeze |
| Schemas | `schemas/` | JSON Schema definitions (draft 2020-12) for tracks, suggestions, sound library, runs |
| Tracks | `tracks/` | Exactly 5 active track files (`radical.{color}.json`), each bound to sound library assets |
| Sound library | `knowledge/sound_library.json` | 30 assets (5 per color: kick, bass, hat, pad, texture) with color_profiles (kits, flows, templates) |
| Registry | `knowledge/registry.json` | Track count, run tracking, active_tracks list |
| Python tooling | `python/` | validate, suggest, export, dashboard, dataset, UI |
| Claude docs | `claude/` | Identity, handoff, validation, reference (read order: IDENTITY → HANDOFF → VALIDATION → REFERENCE) |
| SDM handoff | `sdm/MIRAS.txt` | State continuity; canonical state in external `%USERPROFILE%\Desktop\SDM\sdm.json` |
| Legacy (read-only) | `chatgpt/rest/_quarantine_legacy_7id/` | Deprecated 7-sin tracks, never modify |

### Validation pipeline

`validate.py` checks: schema integrity, exactly 5 tracks, registry consistency, sound library binding (each track's `library_binding` keys map to matching `color_state` assets), album duration policy (radio max < extended min), and jsonschema conformance. Exit 0 = PASS, exit 1 = FAIL with violations.

### Deterministic hashing

Prompt generation follows a deterministic chain: `work_id` → `prompt_version` → `suggestion_hash` (SHA256 of payload: prompt_text | bpm_override | sound_class | color | emotion_core) → `seed_hash_hex` → `export_path`. No randomness or timestamps in config.

### Track-to-sound binding

Each track's `library_binding` (kick/bass/hat/lead/texture) must reference assets in `knowledge/sound_library.json` whose `color_state` matches the track color. Validation enforces this.

### 5-Color model

| Color | Track ID | Emotion Core |
|-------|----------|-------------|
| Grey | radical.grey | Concrete Rage |
| Blue | radical.blue | Blue Sorrow |
| Green | radical.green | Saturated Growth |
| Cream | radical.cream | Intimate Heat |
| Black | radical.black | Divine Smoke |

### Output paths

- Suggestions: `python/out/suggestions/<track_id>.suggestion.json` and `_bundle.json`
- Suno prompts: `python/out/suno/<track_id>__<variation>__suno_prompt.txt` (variations: v0 base, v1 minimal, v2 percussion+sub)
- Prompts: `python/out/prompts/`
- Lyrics: `python/out/lyrics/`
- Dataset: `python/out/dataset.jsonl`

## Core Rules

- **Null instead of omission:** Always use explicit `null` for absent optional fields in JSON; never omit the key.
- **One scope per commit:** Each commit touches one directory or one logical unit. No batched multi-scope edits.
- **EXECUTE → VALIDATE → COMMIT → STOP:** Run validation before committing. If validation fails, report violations and stop.
- **No randomness in config:** All state must be explicit and reproducible.
- **Phase freeze:** `domain/phase_freeze_album5.json` is frozen. Do not edit frozen domain files unless explicitly instructed.
- **Legacy is read-only:** Never modify files under `chatgpt/rest/_quarantine_legacy_7id/`.
- **5 colors only:** grey, blue, green, cream, black. Never introduce new colors or revert to the old 7-identity system.
- **Schema breaking changes:** Removing required fields, narrowing enums, or changing types requires explicit approval and version bump. Additive changes (new optional fields, new enum values) are allowed with version bump.
- **No spontaneous refactors:** No renaming of established structures. No aesthetic drift.

## Governance

Full behavioral rules and identity definition live in `GOVERNANCE.md`. Cursor execution rules in `.cursor/rules/` (execution-mode.mdc, rest-execution-core.mdc). Claude-specific onboarding sequence in `claude/README.md` (read order: IDENTITY → HANDOFF → VALIDATION → REFERENCE). Scoring: 5 keys (mix, vocal, color, flow, replay), 0-10, total 50.
