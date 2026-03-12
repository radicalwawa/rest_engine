# Handoff — Claude-readable

## Miras

Handoff state is recorded in `sdm/MIRAS.txt`. Canonical SDM lives outside the repo at `%USERPROFILE%\Desktop\SDM\sdm.json`. SDM has three blocks: state, artist, engine.

## SDM blocks

- **state:** freeze pointer, active work/track, radical_path (song storage outside repo)
- **artist:** REST's observations about Radical Noface. Written only by REST. Artist does not read this.
- **engine:** REST's self-notes — prompt patterns, revision performance. Written only by REST.

## Freeze

The path `domain/phase_freeze_album5.json` must exist. Do not edit it.

## Safe inheritance sequence

1. Read `sdm/MIRAS.txt` and `%USERPROFILE%\Desktop\SDM\sdm.json`.
2. Run `python python/validate.py`. PASS required to proceed.
3. Execute at most one scope (one directory or one logical unit).
4. After changes: validate again, commit, stop.

## Single-scope continuity rule

One commit per directory or logical unit. Active tracks only: the five in schemas/track.schema.json. Legacy artifacts under `chatgpt/rest/_quarantine_legacy_7id/` are read-only.
