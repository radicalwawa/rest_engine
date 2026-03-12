# Handoff — Claude-readable

## Existing SDM handoff material

Handoff state is recorded in `sdm/SDM_REST_SUCCESSOR.txt`. It is human/maintainer-oriented. Canonical SDM lives outside the repo at `%USERPROFILE%\Desktop\SDM\sdm.json`. The file in the repo summarizes repo rules, successor identity, state (repo_head, modules, delta, mission), and hash history.

## repo_head / freeze / mission logic

- **repo_head:** In SDM_REST_SUCCESSOR.txt, `state.repo_head` is a git commit hash. If you are under SDM discipline: verify `git rev-parse HEAD` equals that value. Mismatch → stop and request baseline recapture before making changes.
- **Freeze pointer:** The path `domain/phase_freeze_album5.json` must exist. Do not edit it. It defines the frozen phase and locked components.
- **mission.current:** If the external sdm.json has mission.current with status `todo`, execute one single-scope task, then set done and touch. If status is `done` or null, there is no active task.

## Safe inheritance sequence

1. Run `python python/validate.py`. PASS required to proceed.
2. If using SDM: verify repo_head and freeze path; read mission.current.
3. Execute at most one scope (one directory or one logical unit).
4. After changes: validate again, commit, stop. Wait for next instruction.

## Single-scope continuity rule

One commit must not span multiple directories or unrelated logical units. No refactor, no edits to the freeze file, no UI/TUI changes in the same commit as domain/schema changes. Active tracks only: the five listed in schemas/track.schema.json. Legacy artifacts under `chatgpt/rest/_quarantine_legacy_7id/` are read-only.
