#!/usr/bin/env python3
"""
Scan runs/ and update knowledge/registry.json (run index).
Usage: run from repo root (rest_engine): python python/run_index.py
Reads: runs/<run_id>/manifest.json, runs/<run_id>/results.json
Writes: knowledge/registry.json (deterministic: run_ids + updated_at)
"""
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS = REPO_ROOT / "runs"
REGISTRY_PATH = REPO_ROOT / "knowledge" / "registry.json"


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    run_ids = []
    if RUNS.exists():
        for run_dir in sorted(RUNS.iterdir()):
            if not run_dir.is_dir():
                continue
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = load_json(manifest_path)
                run_id = manifest.get("run_id") or run_dir.name
            except (json.JSONDecodeError, OSError):
                run_id = run_dir.name
            run_ids.append(run_id)

    registry = {
        "run_ids": run_ids,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    print(f"registry: {len(run_ids)} run(s)")


if __name__ == "__main__":
    main()
