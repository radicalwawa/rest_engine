#!/usr/bin/env python3
"""
Validate REST JSON files against schemas and V1.1 structural rules.
Usage: run from repo root (rest_engine): python python/validate.py
Bounded scan: only schemas/, tracks/, domain/tracks/, knowledge/registry.json.
"""
import json
import sys
from pathlib import Path

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
            if "tracks_deprecated" in p.parts:
                errors.append(f"{p.relative_to(REPO_ROOT)}: active track must not be under tracks_deprecated/")

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

    # --- Schema validation: bounded to schemas/ + tracks/ only (no repo walk) ---
    if not errors and SCHEMAS.exists():
        try:
            import jsonschema
        except ImportError:
            errors.append("python/validate.py: pip install jsonschema")
        else:
            track_schema = load_json(SCHEMAS / "track.schema.json")
            for p in sorted(TRACKS.glob("*.json")) if TRACKS.exists() else []:
                try:
                    data = load_json(p)
                    jsonschema.validate(data, track_schema)
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
