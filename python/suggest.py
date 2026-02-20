import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_LOCK = ROOT / "domain" / "domain_lock.json"
TRACKS_DIR = ROOT / "tracks"
OUT_DIR = ROOT / "python" / "out" / "suggestions"

BPM_SET_DEFAULT = [134, 136, 138, 140]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _get_bpm_set() -> List[int]:
    if DOMAIN_LOCK.exists():
        d = _load_json(DOMAIN_LOCK)
        bpms = d.get("calibration_bpm_set")
        if isinstance(bpms, list) and all(isinstance(x, int) for x in bpms) and len(bpms) > 0:
            return bpms
    return BPM_SET_DEFAULT


def _next_bpm(tested: List[int], bpm_set: List[int]) -> Optional[int]:
    for bpm in bpm_set:
        if bpm not in tested:
            return bpm
    return None


def _read_track(track_id: str) -> Tuple[Path, Dict[str, Any]]:
    p = TRACKS_DIR / f"{track_id}.json"
    return p, _load_json(p)


def _suggest_for_track(track_id: str) -> Dict[str, Any]:
    bpm_set = _get_bpm_set()
    track_path, track = _read_track(track_id)

    constraints = track.get("constraints") or {}
    calibration = track.get("calibration") or {}

    bpm_override = constraints.get("bpm_override")
    tested_bpms = calibration.get("tested_bpms") or []
    proven_bpm = calibration.get("proven_bpm")

    # Deterministic, JSON-only, single-variable suggestion:
    # Priority:
    # 1) If proven_bpm exists -> Production suggestion to set bpm_override = proven_bpm (explicit override).
    # 2) Else -> Calibration suggestion to set bpm_override to next untested bpm in bpm_set.
    # 3) If all tested -> no suggestion.

    if proven_bpm is not None:
        from_val = bpm_override
        to_val = proven_bpm
        return {
            "track_id": track_id,
            "track_file": str(track_path).replace("\\", "/"),
            "mode": "production",
            "single_variable_change": {
                "path": "constraints.bpm_override",
                "from": from_val if from_val is not None else None,
                "to": to_val
            },
            "reason": "proven_bpm is set; production requires explicit BPM anchoring",
            "expected": {
                "stability_score": None,
                "drift_risk": { "type": "none", "severity": "none" }
            }
        }

    nxt = _next_bpm(tested_bpms, bpm_set)
    if nxt is None:
        return {
            "track_id": track_id,
            "track_file": str(track_path).replace("\\", "/"),
            "mode": "calibration",
            "single_variable_change": None,
            "reason": "all bpms in bpm_calibration_set are already tested; set proven_bpm based on results before further tests",
            "expected": {
                "stability_score": None,
                "drift_risk": { "type": None, "severity": None }
            }
        }

    # If bpm_override is null, start at the next untested (usually 134 first).
    # If bpm_override already equals nxt, still return deterministic (no-op avoided by selecting next untested).
    return {
        "track_id": track_id,
        "track_file": str(track_path).replace("\\", "/"),
        "mode": "calibration",
        "single_variable_change": {
            "path": "constraints.bpm_override",
            "from": bpm_override if bpm_override is not None else None,
            "to": nxt
        },
        "reason": "proven_bpm is null; calibration must test single BPM from bpm_calibration_set",
        "expected": {
            "stability_score": None,
            "drift_risk": { "type": None, "severity": None }
        }
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Tracks directory contains filenames like radical.envy.json
    track_ids = sorted([p.stem for p in TRACKS_DIR.glob("*.json")])

    summary = {
        "suggestions_written": 0,
        "out_dir": str(OUT_DIR).replace("\\", "/"),
        "tracks": []
    }

    for tid in track_ids:
        s = _suggest_for_track(tid)
        out_path = OUT_DIR / f"{tid}.json"
        _write_json(out_path, s)
        summary["suggestions_written"] += 1
        summary["tracks"].append({"track_id": tid, "suggestion_file": str(out_path).replace("\\", "/")})

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
