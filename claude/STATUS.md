# Claude handoff status

## Current repo state

REST Engine v1.1.0. Album 5 preproduction complete; phase frozen. Five active tracks in `tracks/`. Validation passes. Claude entry layer present under `claude/`.

## Active authority files

- `GOVERNANCE.md` — Masterprompt, behavior, lifecycle, keywords
- `knowledge/SUCCESSOR_PROMPT.md` — Successor identity and first action
- `domain/domain_lock.json` — 5-color model, policies
- `domain/phase_freeze_album5.json` — Frozen; do not edit
- `python/validate.py` — Source of truth for validation behavior

## Validation entrypoint

From repo root: `python python/validate.py` (or `py -X faulthandler python/validate.py` on Windows). Scripts: `scripts/validate.cmd`, `scripts/validate.ps1`. CI: `.github/workflows/validate.yml`.

## Handoff entry order

1. `claude/README.md`
2. `claude/IDENTITY.md`
3. `claude/HANDOFF.md`
4. `claude/VALIDATION.md`
5. `claude/REFERENCE.md`

## Legacy boundary

Read-only. Do not modify. Single location: `chatgpt/rest/_quarantine_legacy_7id/` (knowledge, suggestions_deprecated, tracks_deprecated). No root-level deprecated-track folder.

## Current known minor notes

None.
