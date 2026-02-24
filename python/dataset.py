import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
OUT_DIR = ROOT / "python" / "out"
OUT_FILE = OUT_DIR / "dataset.jsonl"
SUGGESTIONS_DIR = ROOT / "python" / "out" / "suggestions"

MANIFEST = "manifest.json"
RESULTS = "results.json"


def _load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _suggestion_extra(track_id: str, run_bpm: Optional[int]) -> Dict[str, Any]:
    """Load suggestion for track_id and return suggestion_version, suggestion_hash, sound_class, color, emotion_core, bpm_override. Nulls if missing."""
    path = SUGGESTIONS_DIR / f"{track_id}.suggestion.json"
    sug = _load(path)
    if sug is None:
        return {
            "suggestion_version": None,
            "suggestion_hash": None,
            "sound_class": None,
            "color": None,
            "emotion_core": None,
            "bpm_override": run_bpm,
        }
    prompt_text = sug.get("prompt_text") or ""
    constraints = sug.get("constraints") or {}
    bpm_override = constraints.get("bpm_override") if constraints.get("bpm_override") is not None else run_bpm
    resolved = sug.get("resolved") or {}
    sound_class = resolved.get("sound_class") or ""
    color = resolved.get("color") or ""
    emotion_core = resolved.get("emotion_core") or ""
    payload = f"{prompt_text}\n{bpm_override}\n{sound_class}\n{color}\n{emotion_core}"
    suggestion_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "suggestion_version": sug.get("version") or None,
        "suggestion_hash": suggestion_hash,
        "sound_class": sound_class or None,
        "color": color or None,
        "emotion_core": emotion_core or None,
        "bpm_override": bpm_override,
    }


def _row(manifest: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    drift = results.get("drift") or {}
    track_id = results.get("track_id") or manifest.get("track_id") or None
    bpm = results.get("bpm") if results.get("bpm") is not None else manifest.get("bpm") or None
    extra = _suggestion_extra(track_id or "", bpm) if track_id else _suggestion_extra("", bpm)

    return {
        "run_id": results.get("run_id") or manifest.get("run_id") or None,
        "timestamp": manifest.get("timestamp") or None,
        "mode": manifest.get("mode") or None,
        "track_id": track_id,
        "bpm": bpm,
        "stability_score": results.get("stability_score") if results.get("stability_score") is not None else None,
        "drift_type": drift.get("type") or None,
        "drift_severity": drift.get("severity") or None,
        "drift_notes": drift.get("notes") or None,
        "suno_refs": results.get("suno_refs") if results.get("suno_refs") is not None else None,
        "corrective_adjustment": results.get("corrective_adjustment") if results.get("corrective_adjustment") is not None else None,
        "result_after_adjustment": results.get("result_after_adjustment") if results.get("result_after_adjustment") is not None else None,
        "suggestion_version": extra["suggestion_version"],
        "suggestion_hash": extra["suggestion_hash"],
        "sound_class": extra["sound_class"],
        "color": extra["color"],
        "emotion_core": extra["emotion_core"],
        "bpm_override": extra["bpm_override"],
    }


def build() -> Tuple[int, int]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RUNS_DIR.exists():
        OUT_FILE.write_text("", encoding="utf-8")
        return 0, 0

    run_dirs = sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()])
    written = 0
    skipped = 0

    with OUT_FILE.open("w", encoding="utf-8") as out:
        for d in run_dirs:
            m = _load(d / MANIFEST)
            r = _load(d / RESULTS)
            if m is None or r is None:
                skipped += 1
                continue
            out.write(json.dumps(_row(m, r), ensure_ascii=False) + "\n")
            written += 1

    return written, skipped


def main() -> None:
    written, skipped = build()
    print(json.dumps({
        "dataset_path": str(OUT_FILE).replace("\\", "/"),
        "runs_written": written,
        "runs_skipped": skipped
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
