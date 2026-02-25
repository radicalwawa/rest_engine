#!/usr/bin/env python3
"""
Export Suno prompt for a track from Album 5 identities.
Input: track_id (default: radical.grey)
Reads: domain/album5_identities.json, tracks/{track_id}.json
Output: python/out/suno/{track_id}__{variation}__suno_prompt.txt
"""
import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOMAIN = REPO_ROOT / "domain"
TRACKS = REPO_ROOT / "tracks"
OUT_DIR = Path(__file__).resolve().parent / "out" / "suno"
SUNO_FORMAT_PATH = DOMAIN / "suno_prompt_format.json"


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_identity(identities: list, track_id: str) -> dict | None:
    for i in identities:
        if i.get("track_id") == track_id:
            return i
    return None


def format_fx_policy(fx: dict) -> str:
    if not fx:
        return ""
    parts = [f"{k}: {v}" for k, v in fx.items()]
    return ", ".join(parts)


def build_vocal_dna(vd: dict) -> str:
    if not vd:
        return ""
    reg = vd.get("register")
    char = vd.get("character") or ""
    line = f"{char} {reg} register".strip() if reg else char
    if vd.get("adlibs") is not None:
        line += f", adlibs={vd['adlibs']}"
    if vd.get("hook_last_word_repeat") is not None:
        line += f", hook_last_word_repeat={vd['hook_last_word_repeat']}"
    return line


VARIATION_SUFFIX = {
    "v0": "",
    "v1": "daha minimal",
    "v2": "daha perküsyon + daha sub",
}


def main():
    parser = argparse.ArgumentParser(description="Export Suno prompt for Album 5 track")
    parser.add_argument("--track_id", default="radical.grey", help="Track id (default: radical.grey)")
    parser.add_argument("--variation", choices=["v0", "v1", "v2"], default="v0", help="v0=base, v1=daha minimal, v2=daha perküsyon + daha sub")
    args = parser.parse_args()
    track_id = args.track_id
    variation = args.variation

    identities_path = DOMAIN / "album5_identities.json"
    data = load_json(identities_path)
    identities = data.get("identities") or []
    identity = find_identity(identities, track_id)
    if not identity:
        raise SystemExit(f"Track not found in identities: {track_id}")

    track_path = TRACKS / f"{track_id}.json"
    if track_path.exists():
        load_json(track_path)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{track_id}__{variation}__suno_prompt.txt"

    fmt = load_json(SUNO_FORMAT_PATH) if SUNO_FORMAT_PATH.exists() else {}
    prod_key_order = fmt.get("prod_dna_key_order") or [
        "drum_language", "bass_language", "harmony_policy", "ambience_policy", "fx_policy", "energy_curve"
    ]
    title = f"{identity['track_id']} — {identity['state_label']}"
    bpm_feel = f"{identity['bpm_min']}–{identity['bpm_max']} BPM feel"

    key_to_label = {"drum_language": "drum", "bass_language": "bass", "harmony_policy": "harmony", "ambience_policy": "ambience", "energy_curve": "energy_curve"}
    prod_parts = []
    for key in prod_key_order:
        if key == "fx_policy":
            prod_parts.append(f"fx: {format_fx_policy(identity.get('fx_policy') or {})}")
        else:
            label = key_to_label.get(key, key)
            prod_parts.append(f"{label}: {identity.get(key, '')}")
    prod_dna = "\n".join(prod_parts)

    vocal_dna = build_vocal_dna(identity.get("vocal_delivery") or {})

    guidelines = identity.get("suno_prompt_guidelines") or {}
    allow_drop = guidelines.get("allow_drop", False)
    avoid = guidelines.get("avoid") or []
    focus = guidelines.get("focus") or []
    constraints_lines = [f"allow_drop {str(allow_drop).lower()}"]
    if avoid:
        constraints_lines.append("avoid: " + ", ".join(avoid))
    if focus:
        constraints_lines.append("focus: " + ", ".join(focus))
    constraints = "\n".join(constraints_lines)

    lines = [
        f"TITLE: {title}",
        f"BPM_FEEL: {bpm_feel}",
        "PROD_DNA:",
        prod_dna,
        "VOCAL_DNA:",
        vocal_dna,
        "CONSTRAINTS:",
        constraints,
    ]
    if VARIATION_SUFFIX.get(variation):
        lines.append("VARIATION: " + VARIATION_SUFFIX[variation])
    text = "\n".join(lines)

    out_path.write_text(text, encoding="utf-8")
    print(out_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
