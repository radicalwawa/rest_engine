#!/usr/bin/env python3
# REST Engine — Terminal UI (MVP)
# Scope: python/ only. Deterministic. No randomness.

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = ROOT / "domain"
TRACKS_DIR = ROOT / "tracks"
OUT_DIR = ROOT / "python" / "out"
EVALS_DIR = OUT_DIR / "evals"

WORKS_MANIFEST = DOMAIN_DIR / "works_manifest.json"
SCORE_SCHEMA = DOMAIN_DIR / "score_schema.json"
ALBUM5_IDENTITIES = DOMAIN_DIR / "album5_identities.json"
SOUND_MAP = DOMAIN_DIR / "sound_map.json"
SUNO_EXPORT = ROOT / "python" / "suno_export.py"
VALIDATE_SCRIPT = ROOT / "python" / "validate.py"

TRACK_IDS = ["radical.grey", "radical.blue", "radical.green", "radical.cream", "radical.black"]


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _deterministic_work_id(track_id: str, series: str, title: str, volume: str) -> str:
    # Deterministic, cross-platform safe
    base = f"{track_id}|{series}|{title}|{volume}".encode("utf-8")
    h = hashlib.sha256(base).hexdigest()
    return f"work_{h[:16]}"


def _load_works_manifest() -> Dict[str, Any]:
    if not WORKS_MANIFEST.exists():
        # If missing, fail loudly (domain should have created it)
        raise FileNotFoundError(str(WORKS_MANIFEST))
    return _read_json(WORKS_MANIFEST)


def _save_works_manifest(m: Dict[str, Any]) -> None:
    _write_json(WORKS_MANIFEST, m)


def _ensure_score_contract() -> Dict[str, Any]:
    schema = _read_json(SCORE_SCHEMA)
    # minimal sanity
    keys = schema.get("score_keys")
    if not isinstance(keys, list) or len(keys) != 5:
        raise ValueError("score_schema.json invalid: score_keys must be list of 5")
    return schema


def _mapping_for_track(track_id: str) -> Dict[str, Any]:
    if not SOUND_MAP.exists():
        return {}
    m = _read_json(SOUND_MAP)
    for entry in m.get("mappings") or []:
        if entry.get("track_id") == track_id:
            return entry
    return {}


def cmd_work_create(args: argparse.Namespace) -> None:
    if args.track_id not in TRACK_IDS:
        raise ValueError(f"Invalid track_id: {args.track_id}")

    manifest = _load_works_manifest()
    works: List[Dict[str, Any]] = manifest.get("works")
    if works is None:
        manifest["works"] = []
        works = manifest["works"]

    series = args.series.strip()
    title = args.title.strip()
    volume = args.volume.strip()

    work_id = _deterministic_work_id(args.track_id, series, title, volume)

    # If already exists, do not duplicate
    for w in works:
        if w.get("work_id") == work_id:
            print(work_id)
            return

    mapping = _mapping_for_track(args.track_id)
    entry: Dict[str, Any] = {
        "work_id": work_id,
        "track_id": args.track_id,
        "series": series,
        "title": title,
        "volume": volume,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
        "notes": None,
    }
    if mapping:
        if "color" in mapping:
            entry["color"] = mapping["color"]
        if "techno_genre" in mapping:
            entry["techno_genre"] = mapping["techno_genre"]
        if "rap_identity" in mapping:
            entry["rap_identity"] = mapping["rap_identity"]
    works.append(entry)

    # keep top-level null policy: do not omit required keys; works list is fine
    manifest["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"
    _save_works_manifest(manifest)

    print(work_id)


def cmd_work_list(_: argparse.Namespace) -> None:
    manifest = _load_works_manifest()
    works: List[Dict[str, Any]] = manifest.get("works", [])
    if not works:
        print("(no works)")
        return
    for w in works:
        line = f'{w.get("work_id")} | {w.get("track_id")} | {w.get("series")} | {w.get("title")} | {w.get("volume")}'
        if w.get("color") or w.get("techno_genre") or w.get("rap_identity"):
            line += f' | {w.get("color")} | {w.get("techno_genre")} | {w.get("rap_identity")}'
        print(line)


def cmd_prompt(args: argparse.Namespace) -> None:
    # Calls existing exporter deterministically
    if not SUNO_EXPORT.exists():
        raise FileNotFoundError(str(SUNO_EXPORT))
    if args.track_id not in TRACK_IDS:
        raise ValueError(f"Invalid track_id: {args.track_id}")
    if args.variation not in ["v0", "v1", "v2"]:
        raise ValueError("variation must be v0|v1|v2")

    cmd = [sys.executable, str(SUNO_EXPORT), "--track_id", args.track_id, "--variation", args.variation]
    subprocess.check_call(cmd)

    out_path = OUT_DIR / "suno" / f"{args.track_id}__{args.variation}__suno_prompt.txt"
    if not out_path.exists():
        # fallback if exporter writes elsewhere; still try to locate
        raise FileNotFoundError(str(out_path))

    text = out_path.read_text(encoding="utf-8")
    print(text)


def _score_input(keys: List[str]) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for k in keys:
        while True:
            raw = input(f"{k} (0-10): ").strip()
            try:
                v = int(raw)
            except ValueError:
                print("Tam sayı gir (0-10).")
                continue
            if v < 0 or v > 10:
                print("0 ile 10 arası olmalı.")
                continue
            scores[k] = v
            break
    return scores


def cmd_score(args: argparse.Namespace) -> None:
    _ensure_score_contract()
    schema = _read_json(SCORE_SCHEMA)
    keys: List[str] = schema["score_keys"]

    # Find work
    manifest = _load_works_manifest()
    works: List[Dict[str, Any]] = manifest.get("works", [])
    work = next((w for w in works if w.get("work_id") == args.work_id), None)
    if work is None:
        raise ValueError(f"work_id not found: {args.work_id}")

    if args.variation not in ["v0", "v1", "v2"]:
        raise ValueError("variation must be v0|v1|v2")

    print(f'WORK: {work["work_id"]} | {work["track_id"]} | {work["series"]} / {work["title"]} / {work["volume"]}')
    print(f"VARIATION: {args.variation}")
    suno_ref = (args.suno_ref or "").strip()
    if not suno_ref:
        suno_ref = input("suno_ref (link/id): ").strip()

    print("7 parametreyi 0-10 puanla:")
    scores = _score_input(keys)
    total = sum(scores.values())
    note = (args.note or "").strip()
    if not note:
        note = input("kısa not (opsiyonel): ").strip() or None

    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    # deterministic-ish run_id: timestamp is okay for logs; not used for engine determinism
    run_id = f'eval_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}_{work["work_id"]}_{args.variation}'
    payload = {
        "run_id": run_id,
        "work_id": work["work_id"],
        "track_id": work["track_id"],
        "variation": args.variation,
        "suno_ref": suno_ref,
        "scores": scores,
        "total": total,
        "total_max": schema.get("total_max", 70),
        "note": note,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
    }

    out_file = EVALS_DIR / f"{run_id}.json"
    _write_json(out_file, payload)

    print(f"TOTAL: {total}/{payload['total_max']}")
    print(f"SAVED: {out_file}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rest-ui", description="REST Engine Terminal UI (MVP)")
    sp = p.add_subparsers(dest="cmd", required=True)

    p_wc = sp.add_parser("work-create", help="Create a work entry (series/title/volume)")
    p_wc.add_argument("--track_id", required=True, choices=TRACK_IDS)
    p_wc.add_argument("--series", required=True)
    p_wc.add_argument("--title", required=True)
    p_wc.add_argument("--volume", required=True)
    p_wc.set_defaults(func=cmd_work_create)

    p_wl = sp.add_parser("work-list", help="List works")
    p_wl.set_defaults(func=cmd_work_list)

    p_pr = sp.add_parser("prompt", help="Generate and print Suno prompt for a track+variation")
    p_pr.add_argument("--track_id", required=True, choices=TRACK_IDS)
    p_pr.add_argument("--variation", default="v0", choices=["v0", "v1", "v2"])
    p_pr.set_defaults(func=cmd_prompt)

    p_sc = sp.add_parser("score", help="Score a Suno output (7 params) and save eval json")
    p_sc.add_argument("--work_id", required=True)
    p_sc.add_argument("--variation", default="v0", choices=["v0", "v1", "v2"])
    p_sc.add_argument("--suno_ref", default=None)
    p_sc.add_argument("--note", default=None)
    p_sc.set_defaults(func=cmd_score)

    p_va = sp.add_parser("validate", help="Run schema and repo validation (python/validate.py)")
    p_va.set_defaults(func=cmd_validate)

    return p


def cmd_validate(_: argparse.Namespace) -> None:
    if not VALIDATE_SCRIPT.exists():
        raise FileNotFoundError(str(VALIDATE_SCRIPT))
    subprocess.check_call([sys.executable, str(VALIDATE_SCRIPT)])


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd != "validate":
        for required in [WORKS_MANIFEST, SCORE_SCHEMA, ALBUM5_IDENTITIES]:
            if not required.exists():
                print(f"ERROR: missing required file: {required}", file=sys.stderr)
                sys.exit(2)
    args.func(args)


if __name__ == "__main__":
    main()
