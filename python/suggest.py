"""
Generate deterministic prompt suggestions from sound_map + sound_library + tracks.
Output: python/out/suggestions/<track_id>.suggestion.json and _bundle.json.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SOUND_MAP_PATH = ROOT / "domain" / "sound_map.json"
SOUND_LIBRARY_PATH = ROOT / "knowledge" / "sound_library.json"
TRACKS_DIR = ROOT / "tracks"
DEFAULT_OUT = ROOT / "python" / "out" / "suggestions"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        sys.exit(2)


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _build_library_index(library: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for item in library.get("items") or []:
        sc = item.get("sound_class")
        if sc is not None:
            index[sc] = item
    return index


def _build_color_emotion_lookup(sound_map: Dict[str, Any]) -> Dict[str, str]:
    """Map color -> emotion_core from sound_map colors array."""
    lookup: Dict[str, str] = {}
    for c in sound_map.get("colors") or []:
        color = c.get("color")
        core = c.get("emotion_core")
        if color is not None:
            lookup[color] = core if core is not None else ""
    return lookup


def _variant_from_seed(
    prompt_text: str,
    bpm_override: int,
    sound_class: str,
    color: str,
    emotion_core: str,
    color_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """Deterministic kit/flow/template selection. Seed = same payload order as dataset hash."""
    payload = f"{prompt_text}\n{bpm_override}\n{sound_class}\n{color}\n{emotion_core}"
    seed_hash_hex = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    h = int(seed_hash_hex, 16)
    kits = color_profile.get("kits") or []
    flows = color_profile.get("flows") or []
    templates = color_profile.get("templates") or []
    t_i = (h % len(templates)) if templates else 0
    f_i = ((h // 7) % len(flows)) if flows else 0
    k_i = ((h // 13) % len(kits)) if kits else 0
    return {
        "template_id": templates[t_i]["id"] if t_i < len(templates) else None,
        "flow_id": flows[f_i]["id"] if f_i < len(flows) else None,
        "kit_id": kits[k_i]["id"] if k_i < len(kits) else None,
        "template_index": t_i,
        "flow_index": f_i,
        "kit_index": k_i,
        "seed_hash_hex": seed_hash_hex,
    }


def _prompt_text_from_skeleton(
    skeleton: str,
    color: str,
    emotion_core: str,
    bpm: int,
    sound_class_used: str,
) -> str:
    """Replace placeholders in template skeleton. Deterministic."""
    return (
        skeleton.replace("{{color}}", color)
        .replace("{{emotion}}", emotion_core)
        .replace("{{bpm}}", str(bpm))
        .replace("{{sound_class}}", sound_class_used)
    )


def _get_bpm_from_track(track: Dict[str, Any]) -> Optional[int]:
    """proven_bpm, bpm_lock, or constraints.bpm_override."""
    cal = track.get("calibration") or {}
    proven = cal.get("proven_bpm")
    if proven is not None and isinstance(proven, int):
        return proven
    lock = track.get("bpm_lock")
    if lock is not None and isinstance(lock, int):
        return lock
    constraints = track.get("constraints") or {}
    ov = constraints.get("bpm_override")
    if ov is not None and isinstance(ov, int):
        return ov
    return None


def _build_suggestion(
    track_id: str,
    mode: str,
    bpm_override: int,
    bpm_source: str,
    color: str,
    emotion_core: str,
    sound_class: str,
    prompt_pack: Dict[str, Any],
    color_tone: str,
) -> Dict[str, Any]:
    style_core = prompt_pack.get("style_core") or ""
    sound_tokens = list(prompt_pack.get("sound_tokens") or [])
    negative_tokens = list(prompt_pack.get("negative_tokens") or [])
    structure_hint = prompt_pack.get("structure_hint") or ""
    lyric_hint = prompt_pack.get("lyric_hint") or ""

    prompt_text = (
        style_core
        + " Tokens: "
        + ", ".join(sound_tokens)
        + " Avoid: "
        + ", ".join(negative_tokens)
        + " Structure: "
        + structure_hint
        + " Lyrics: "
        + lyric_hint
        + " Color: "
        + color_tone
    )

    return {
        "version": "1.0",
        "track_id": track_id,
        "mode": mode,
        "constraints": {"bpm_override": bpm_override},
        "prompt": {
            "style_core": style_core,
            "sound_tokens": sound_tokens,
            "negative_tokens": negative_tokens,
            "structure_hint": structure_hint,
            "lyric_hint": lyric_hint,
            "composer_notes": None,
        },
        "resolved": {
            "color": color,
            "emotion_core": emotion_core,
            "sound_class": sound_class,
            "bpm_source": bpm_source,
        },
        "prompt_text": prompt_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic prompt suggestions")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory for suggestion JSONs")
    parser.add_argument("--track-id", default=None, help="Generate only this track (e.g. radical.grey)")
    parser.add_argument("--mode", choices=["calibration", "production"], default=None, help="Override mode")
    parser.add_argument("--bpm", type=int, choices=[134, 136, 138, 140], default=None, help="Override BPM (calibration only)")
    args = parser.parse_args()

    out_dir = (ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir = out_dir.resolve()

    sound_map = _load_json(SOUND_MAP_PATH)
    library = _load_json(SOUND_LIBRARY_PATH)
    library_index = _build_library_index(library)
    color_emotion = _build_color_emotion_lookup(sound_map)
    color_profiles = library.get("color_profiles") or {}
    bpm_calibration_set = library.get("bpm_calibration_set")
    if not bpm_calibration_set or not isinstance(bpm_calibration_set, list):
        bpm_calibration_set = [134, 136, 138, 140]
    default_bpm = int(bpm_calibration_set[0]) if bpm_calibration_set else 134

    mappings: List[Dict[str, Any]] = sound_map.get("mappings") or []
    if args.track_id:
        mappings = [m for m in mappings if m.get("track_id") == args.track_id]
        if not mappings:
            print(f"Track not in sound_map: {args.track_id}", file=sys.stderr)
            sys.exit(2)

    suggestions: List[Dict[str, Any]] = []

    for m in mappings:
        track_id = m.get("track_id")
        if not track_id:
            continue
        color = m.get("color") or ""
        sound_class = m.get("sound_class")
        emotion_core = color_emotion.get(color) or ""
        color_tone = (color_profiles.get(color) or {}).get("tone") or ""

        if sound_class not in library_index:
            print(f"sound_class not in library: {sound_class}", file=sys.stderr)
            sys.exit(2)

        track_path = TRACKS_DIR / f"{track_id}.json"
        if not track_path.exists():
            print(f"Track file missing for {track_id}: {track_path}", file=sys.stderr)
            sys.exit(2)

        track = _load_json(track_path)
        lib_item = library_index[sound_class]
        prompt_pack = lib_item.get("prompt_pack") or {}

        mode = args.mode
        if mode is None:
            mode = track.get("mode")
        if mode not in ("calibration", "production"):
            mode = "calibration"

        bpm_override: int
        bpm_source: str

        track_bpm = _get_bpm_from_track(track)
        if mode == "production" and track_bpm is not None:
            bpm_override = track_bpm
            bpm_source = "proven_bpm"
        else:
            if args.bpm is not None and mode == "calibration":
                bpm_override = args.bpm
                bpm_source = "calibration_set"
            elif track_bpm is not None:
                bpm_override = track_bpm
                bpm_source = "calibration_set"
            else:
                bpm_override = default_bpm
                bpm_source = "calibration_set"

        sug = _build_suggestion(
            track_id=track_id,
            mode=mode,
            bpm_override=bpm_override,
            bpm_source=bpm_source,
            color=color,
            emotion_core=emotion_core,
            sound_class=sound_class,
            prompt_pack=prompt_pack,
            color_tone=color_tone,
        )
        color_profile = color_profiles.get(color) or {}
        variant = _variant_from_seed(
            prompt_text=sug["prompt_text"],
            bpm_override=bpm_override,
            sound_class=sound_class,
            color=color,
            emotion_core=emotion_core,
            color_profile=color_profile,
        )
        sug["resolved"]["variant"] = variant
        effective_bpm = bpm_override
        kits = color_profile.get("kits") or []
        templates = color_profile.get("templates") or []
        t_i = variant.get("template_index", 0)
        k_i = variant.get("kit_index", 0)
        selected_template = templates[t_i] if t_i < len(templates) else {}
        selected_kit = kits[k_i] if k_i < len(kits) else {}
        skeleton = selected_template.get("prompt_skeleton") if selected_template else None
        effective_sound_class = selected_kit.get("sound_class") if selected_kit else sound_class
        if skeleton:
            sug["prompt_text"] = _prompt_text_from_skeleton(
                skeleton, color, emotion_core, effective_bpm, effective_sound_class or sound_class
            )
            sug["resolved"]["template_applied"] = True
            sug["resolved"]["bpm_used"] = effective_bpm
            sug["resolved"]["sound_class_used"] = effective_sound_class or sound_class
        else:
            sug["resolved"]["template_applied"] = False
        suggestions.append(sug)

        out_path = out_dir / f"{track_id}.suggestion.json"
        _write_json(out_path, sug)

    bundle = {
        "version": "1.0",
        "out_dir": str(out_dir).replace("\\", "/"),
        "tracks": [s["track_id"] for s in suggestions],
        "suggestions": suggestions,
    }
    _write_json(out_dir / "_bundle.json", bundle)

    return 0


if __name__ == "__main__":
    sys.exit(main())
