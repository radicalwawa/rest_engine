#!/usr/bin/env python3
"""
Validate REST JSON files against schemas and V1.1 structural rules.
Usage: run from repo root (rest_engine): python python/validate.py
"""
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("SYSTEM STATUS: FAIL", file=sys.stderr)
    print("python/validate.py: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = REPO_ROOT / "schemas"
TRACKS = REPO_ROOT / "tracks"
RUNS = REPO_ROOT / "runs"
SUGGESTIONS_DIR = REPO_ROOT / "python" / "out" / "suggestions"
TRACKS_DEPRECATED = REPO_ROOT / "tracks_deprecated"
KNOWLEDGE = REPO_ROOT / "knowledge"
REGISTRY_JSON = KNOWLEDGE / "registry.json"

REQUIRED_STATES = {"radical.grey", "radical.blue", "radical.green", "radical.cream", "radical.black"}


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def discover_active_track_files():
    """Discovery order: tracks/*.json, then domain/tracks/*.json, then *track*.json excluding tracks_deprecated/."""
    if TRACKS.exists() and TRACKS.is_dir():
        files = sorted(TRACKS.glob("*.json"))
        if files:
            return list(files)
    domain_tracks = REPO_ROOT / "domain" / "tracks"
    if domain_tracks.exists() and domain_tracks.is_dir():
        files = sorted(domain_tracks.glob("*.json"))
        if files:
            return list(files)
    out = []
    for d in [TRACKS, domain_tracks]:
        if not d.exists() or not d.is_dir():
            continue
        for p in d.glob("*track*.json"):
            if "tracks_deprecated" not in p.parts:
                out.append(p)
    return sorted(set(out)) if out else []


def main():
    errors = []

    # --- V1.1 Schema integrity ---
    if not SCHEMAS.exists() or not SCHEMAS.is_dir():
        errors.append(f"{SCHEMAS.relative_to(REPO_ROOT)}: schemas directory must exist")
    else:
        for p in sorted(SCHEMAS.glob("*.schema.json")):
            try:
                data = load_json(p)
                if isinstance(data, dict):
                    if "$id" in data and data.get("$id") is None:
                        errors.append(f"{p.relative_to(REPO_ROOT)}: $id must not be null")
                    if "version" in data and data.get("version") is None:
                        errors.append(f"{p.relative_to(REPO_ROOT)}: version must not be null when present")
            except json.JSONDecodeError as e:
                errors.append(f"{p.relative_to(REPO_ROOT)}: {e}")

    # --- V1.1 Track inventory ---
    active_track_files = discover_active_track_files()
    for p in active_track_files:
        rel = p.relative_to(REPO_ROOT)
        if str(TRACKS_DEPRECATED) in str(p) or rel.parts[0] == "tracks_deprecated":
            errors.append(f"{rel}: active track must not be under tracks_deprecated/")
    try:
        ids_seen = []
        for p in active_track_files:
            data = load_json(p)
            tid = data.get("id") if isinstance(data, dict) else None
            if tid not in REQUIRED_STATES:
                errors.append(f"{p.relative_to(REPO_ROOT)}: track id must be one of {REQUIRED_STATES}")
            else:
                ids_seen.append(tid)
        if len(active_track_files) != 5:
            errors.append(f"tracks: expected exactly 5 active tracks, got {len(active_track_files)}")
        if set(ids_seen) != REQUIRED_STATES:
            missing = REQUIRED_STATES - set(ids_seen)
            extra = set(ids_seen) - REQUIRED_STATES
            if missing:
                errors.append(f"tracks: missing states {missing}")
            if extra or len(ids_seen) != len(set(ids_seen)):
                errors.append(f"tracks: all five states must appear exactly once; ids_seen={ids_seen}")
    except (json.JSONDecodeError, OSError) as e:
        errors.append(f"tracks: {e}")
    print("Active tracks (counted):", [str(p.relative_to(REPO_ROOT)) for p in active_track_files], file=sys.stderr)

    # --- V1.1 Legacy isolation ---
    if TRACKS_DEPRECATED.exists():
        for p in active_track_files:
            try:
                p.resolve().relative_to(TRACKS_DEPRECATED.resolve())
                errors.append(f"{p.relative_to(REPO_ROOT)}: active track must not be under tracks_deprecated/")
            except ValueError:
                pass

    # --- V1.1 Null instead of omission (registry.json) ---
    if REGISTRY_JSON.exists():
        try:
            data = load_json(REGISTRY_JSON)
            if not isinstance(data, dict):
                errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: must be a JSON object")
            else:
                if "run_ids" not in data:
                    errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: run_ids must exist (array)")
                elif not isinstance(data.get("run_ids"), list):
                    errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: run_ids must be an array")
                if "updated_at" not in data:
                    errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: updated_at must exist (null or string)")
                elif data.get("updated_at") is not None and not isinstance(data.get("updated_at"), str):
                    errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: updated_at must be null or string")
                if "notes" not in data:
                    errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: notes must exist (null or string)")
                elif data.get("notes") is not None and not isinstance(data.get("notes"), str):
                    errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: notes must be null or string")
        except json.JSONDecodeError as e:
            errors.append(f"{REGISTRY_JSON.relative_to(REPO_ROOT)}: {e}")

    # --- Existing schema validation ---
    if not errors and SCHEMAS.exists():
        track_schema = load_json(SCHEMAS / "track.schema.json")
        manifest_schema = load_json(SCHEMAS / "run_manifest.schema.json")
        results_schema = load_json(SCHEMAS / "run_results.schema.json")
        suggestion_schema = load_json(SCHEMAS / "suggestion.schema.json")

        for p in sorted(TRACKS.glob("*.json")) if TRACKS.exists() else []:
            try:
                data = load_json(p)
                jsonschema.validate(data, track_schema)
            except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                errors.append(f"{p.relative_to(REPO_ROOT)}: {e}")

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
                    errors.append(f"{p.relative_to(REPO_ROOT)}: {e}")

    if errors:
        print("SYSTEM STATUS: FAIL", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print("SYSTEM STATUS: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
