import json
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
OUT_DIR = ROOT / "python" / "out"
OUT_FILE = OUT_DIR / "dataset.jsonl"

MANIFEST = "manifest.json"
RESULTS = "results.json"


def _load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _row(manifest: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    drift = results.get("drift") or {}
    return {
        "run_id": results.get("run_id") or manifest.get("run_id") or None,
        "timestamp": manifest.get("timestamp") or None,
        "mode": manifest.get("mode") or None,
        "track_id": results.get("track_id") or manifest.get("track_id") or None,
        "bpm": results.get("bpm") if results.get("bpm") is not None else manifest.get("bpm") or None,
        "stability_score": results.get("stability_score") if results.get("stability_score") is not None else None,
        "drift_type": drift.get("type") or None,
        "drift_severity": drift.get("severity") or None,
        "drift_notes": drift.get("notes") or None,
        "suno_refs": results.get("suno_refs") if results.get("suno_refs") is not None else None,
        "corrective_adjustment": results.get("corrective_adjustment") if results.get("corrective_adjustment") is not None else None,
        "result_after_adjustment": results.get("result_after_adjustment") if results.get("result_after_adjustment") is not None else None,
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
