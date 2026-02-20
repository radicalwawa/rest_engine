#!/usr/bin/env python3
"""
Validate REST JSON files against their schemas.
Usage: run from repo root (rest_engine): python python/validate.py
Reads: schemas/*.json, tracks/*.json, runs/<run_id>/manifest.json, runs/<run_id>/results.json
"""
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("pip install jsonschema", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = REPO_ROOT / "schemas"
TRACKS = REPO_ROOT / "tracks"
RUNS = REPO_ROOT / "runs"


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    errors = []

    # Load schemas
    track_schema = load_json(SCHEMAS / "track.schema.json")
    manifest_schema = load_json(SCHEMAS / "run_manifest.schema.json")
    results_schema = load_json(SCHEMAS / "run_results.schema.json")

    # Validate tracks
    for p in sorted(TRACKS.glob("*.json")):
        try:
            data = load_json(p)
            jsonschema.validate(data, track_schema)
        except (json.JSONDecodeError, jsonschema.ValidationError) as e:
            errors.append(f"{p.relative_to(REPO_ROOT)}: {e}")

    # Validate runs (manifest + results per run_id)
    if RUNS.exists():
        for run_dir in sorted(RUNS.iterdir()):
            if not run_dir.is_dir():
                continue
            manifest_path = run_dir / "manifest.json"
            results_path = run_dir / "results.json"
            if manifest_path.exists():
                try:
                    jsonschema.validate(load_json(manifest_path), manifest_schema)
                except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                    errors.append(f"{manifest_path.relative_to(REPO_ROOT)}: {e}")
            if results_path.exists():
                try:
                    jsonschema.validate(load_json(results_path), results_schema)
                except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                    errors.append(f"{results_path.relative_to(REPO_ROOT)}: {e}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print("OK: all validated")
    sys.exit(0)


if __name__ == "__main__":
    main()
