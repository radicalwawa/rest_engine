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
SUGGESTIONS_DIR = REPO_ROOT / "python" / "out" / "suggestions"


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    errors = []

    # Load schemas
    track_schema = load_json(SCHEMAS / "track.schema.json")
    manifest_schema = load_json(SCHEMAS / "run_manifest.schema.json")
    results_schema = load_json(SCHEMAS / "run_results.schema.json")
    suggestion_schema = load_json(SCHEMAS / "suggestion.schema.json")

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

    # Validate suggestions (subset matching suggestion.schema.json; only active 5-color track_ids)
    SUGGESTION_TRACK_IDS = {"radical.grey", "radical.blue", "radical.green", "radical.cream", "radical.black"}
    if SUGGESTIONS_DIR.exists():
        for p in sorted(SUGGESTIONS_DIR.glob("*.suggestion.json")):
            track_id = p.stem.removesuffix(".suggestion") if p.suffix == ".json" else p.stem
            if track_id not in SUGGESTION_TRACK_IDS:
                continue
            try:
                data = load_json(p)
                r = data.get("resolved") or {}
                v = r.get("variant") or {}
                subset = {
                    "track_id": data.get("track_id"),
                    "prompt_text": data.get("prompt_text"),
                    "resolved": {
                        "color": r.get("color"),
                        "emotion_core": r.get("emotion_core"),
                        "sound_class": r.get("sound_class"),
                        "bpm_source": r.get("bpm_source"),
                        "variant": {
                            "template_id": v.get("template_id"),
                            "flow_id": v.get("flow_id"),
                            "kit_id": v.get("kit_id"),
                            "template_index": v.get("template_index"),
                            "flow_index": v.get("flow_index"),
                            "kit_index": v.get("kit_index"),
                            "seed_hash_hex": v.get("seed_hash_hex"),
                        },
                    },
                }
                jsonschema.validate(subset, suggestion_schema)
            except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                errors.append(f"{p.relative_to(REPO_ROOT)} ({SCHEMAS.relative_to(REPO_ROOT) / 'suggestion.schema.json'}): {e}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print("OK: all validated")
    if SUGGESTIONS_DIR.exists() and list(SUGGESTIONS_DIR.glob("*.suggestion.json")):
        print("OK: suggestions validated")
    sys.exit(0)


if __name__ == "__main__":
    main()
