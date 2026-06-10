#!/bin/bash
# SessionStart hook for REST Engine.
# Installs Python dependencies so validate.py, the dashboard/TUI, and the
# tests/ scripts work in Claude Code on the web sessions.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Best-effort pip upgrade; not fatal if the base image pins pip.
python -m pip install --upgrade pip || true

# Tooling deps (validate/suggest/export/dashboard): jsonschema, textual
python -m pip install -r python/requirements.txt

# Root deps (db_manager/prompt_engine/tui + tests): textual, pyperclip
python -m pip install -r requirements.txt
