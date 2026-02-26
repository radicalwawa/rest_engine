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
SOUND_LIBRARY_SCHEMA = SCHEMAS / "sound_library.schema.json"
SOUND_LIBRARY_JSON = KNOWLEDGE / "sound_library.json"
ALBUM_5_MANIFEST = REPO_ROOT / "domain" / "album_5_manifest.json"

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

    # --- Sound library v1 integrity (only read sound_library schema + JSON) ---
    if SOUND_LIBRARY_SCHEMA.exists() and SOUND_LIBRARY_JSON.exists():
        try:
            data = load_json(SOUND_LIBRARY_JSON)
            if not isinstance(data, dict):
                errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: must be a JSON object")
            else:
                sv = data.get("schema_version")
                if sv is None or (isinstance(sv, str) and not sv.strip()):
                    errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: schema_version must exist and not be null or empty")
                if "assets" not in data:
                    errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: assets must exist")
                elif not isinstance(data.get("assets"), list):
                    errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: assets must be an array")
                else:
                    ids_seen = []
                    for i, asset in enumerate(data["assets"]):
                        if not isinstance(asset, dict):
                            errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: assets[{i}] must be an object")
                            continue
                        color = asset.get("color_state")
                        if color not in REQUIRED_STATES:
                            errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: assets[{i}].color_state must be one of {REQUIRED_STATES}")
                        if "notes" not in asset:
                            errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: assets[{i}].notes must exist (null or string)")
                        if "updated_at" not in asset:
                            errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: assets[{i}].updated_at must exist (null or string)")
                        aid = asset.get("id")
                        if aid is not None:
                            if aid in ids_seen:
                                errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: assets[{i}].id must be unique; duplicate id={aid!r}")
                            else:
                                ids_seen.append(aid)
        except json.JSONDecodeError as e:
            errors.append(f"{SOUND_LIBRARY_JSON.relative_to(REPO_ROOT)}: {e}")

    # --- Track-to-library binding integrity ---
    LIBRARY_BINDING_KEYS = ["kick", "bass", "hat", "lead", "texture"]
    asset_to_color = {}
    if SOUND_LIBRARY_JSON.exists():
        try:
            lib_data = load_json(SOUND_LIBRARY_JSON)
            if isinstance(lib_data, dict) and isinstance(lib_data.get("assets"), list):
                for asset in lib_data["assets"]:
                    if isinstance(asset, dict):
                        aid = asset.get("id")
                        color = asset.get("color_state")
                        if aid is not None and color is not None:
                            asset_to_color[aid] = color
        except (json.JSONDecodeError, OSError):
            pass
    for p in active_track_files:
        try:
            data = load_json(p)
            if not isinstance(data, dict):
                continue
            track_id = data.get("id")
            if track_id not in REQUIRED_STATES:
                continue
            binding = data.get("library_binding")
            if binding is None:
                errors.append(f"{p.relative_to(REPO_ROOT)}: library_binding must exist")
                continue
            if not isinstance(binding, dict):
                errors.append(f"{p.relative_to(REPO_ROOT)}: library_binding must be an object")
                continue
            for key in LIBRARY_BINDING_KEYS:
                if key not in binding:
                    errors.append(f"{p.relative_to(REPO_ROOT)}: library_binding must have key {key!r}")
                    continue
                aid = binding.get(key)
                if not isinstance(aid, str):
                    errors.append(f"{p.relative_to(REPO_ROOT)}: library_binding.{key} must be a string asset id")
                    continue
                if aid not in asset_to_color:
                    errors.append(f"{p.relative_to(REPO_ROOT)}: library_binding.{key} asset id {aid!r} not in sound library")
                    continue
                if asset_to_color[aid] != track_id:
                    errors.append(f"{p.relative_to(REPO_ROOT)}: library_binding.{key} asset {aid!r} color_state does not match track {track_id!r}")
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"{p.relative_to(REPO_ROOT)}: {e}")

    # --- Album duration policy (domain/album_5_manifest.json) ---
    RELEASE_FORMAT_KEYS = [
        "radio_version_target_sec", "radio_version_min_sec", "radio_version_max_sec",
        "extended_version_target_sec", "extended_version_min_sec", "extended_version_max_sec",
        "release_strategy"
    ]
    if ALBUM_5_MANIFEST.exists():
        try:
            data = load_json(ALBUM_5_MANIFEST)
            if not isinstance(data, dict):
                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: must be a JSON object")
            else:
                rf = data.get("release_format")
                if rf is None:
                    errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: release_format must exist")
                elif not isinstance(rf, dict):
                    errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: release_format must be an object")
                else:
                    for key in RELEASE_FORMAT_KEYS:
                        if key not in rf:
                            errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: release_format must have key {key!r}")
                    if not errors:
                        int_keys = [k for k in RELEASE_FORMAT_KEYS if k != "release_strategy"]
                        for key in int_keys:
                            v = rf.get(key)
                            if v is not None and not isinstance(v, int):
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: release_format.{key} must be integer")
                        if not errors:
                            r_min, r_tgt, r_max = rf.get("radio_version_min_sec"), rf.get("radio_version_target_sec"), rf.get("radio_version_max_sec")
                            e_min, e_tgt, e_max = rf.get("extended_version_min_sec"), rf.get("extended_version_target_sec"), rf.get("extended_version_max_sec")
                            if r_min is not None and r_tgt is not None and r_min > r_tgt:
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: radio_version_min_sec must be <= radio_version_target_sec")
                            if r_tgt is not None and r_max is not None and r_tgt > r_max:
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: radio_version_target_sec must be <= radio_version_max_sec")
                            if r_min is not None and r_max is not None and r_min > r_max:
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: radio_version_min_sec must be <= radio_version_max_sec")
                            if e_min is not None and e_tgt is not None and e_min > e_tgt:
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: extended_version_min_sec must be <= extended_version_target_sec")
                            if e_tgt is not None and e_max is not None and e_tgt > e_max:
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: extended_version_target_sec must be <= extended_version_max_sec")
                            if e_min is not None and e_max is not None and e_min > e_max:
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: extended_version_min_sec must be <= extended_version_max_sec")
                            if r_max is not None and e_min is not None and r_max >= e_min:
                                errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: radio_version_max_sec must be < extended_version_min_sec")
        except json.JSONDecodeError as e:
            errors.append(f"{ALBUM_5_MANIFEST.relative_to(REPO_ROOT)}: {e}")

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
