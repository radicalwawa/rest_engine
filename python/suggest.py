"""
Generate deterministic prompt suggestions from sound_map + sound_library + tracks.
Output: python/out/suggestions/<track_id>.suggestion.json and _bundle.json.
"""
import argparse
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
    sound_class: str,
    emotion_profile: str,
    prompt_pack: Dict[str, Any],
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
            "sound_class": sound_class,
            "emotion_profile": emotion_profile,
            "bpm_source": bpm_source,
        },
        "prompt_text": prompt_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic prompt suggestions")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory for suggestion JSONs")
    parser.add_argument("--track-id", default=None, help="Generate only this track (e.g. radical.wrath)")
    parser.add_argument("--mode", choices=["calibration", "production"], default=None, help="Override mode")
    parser.add_argument("--bpm", type=int, choices=[134, 136, 138, 140], default=None, help="Override BPM (calibration only)")
    args = parser.parse_args()

    out_dir = (ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir = out_dir.resolve()

    sound_map = _load_json(SOUND_MAP_PATH)
    library = _load_json(SOUND_LIBRARY_PATH)
    library_index = _build_library_index(library)
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
        sound_class = m.get("sound_class")
        emotion_profile = m.get("emotion_profile") or ""

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
            sound_class=sound_class,
            emotion_profile=emotion_profile,
            prompt_pack=prompt_pack,
        )
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
