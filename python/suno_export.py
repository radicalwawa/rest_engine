#!/usr/bin/env python3
"""
Export Suno v5.5 prompt for a track from Album 5 kit and voice profiles.
Input: track_id (default: radical.grey), variation (v0/v1/v2)
Reads: domain/suno_kits.json, domain/suno_voices.json, domain/album5_identities.json
Output:
  python/out/suno/{track_id}__{variation}__style.txt       (Style of Music field)
  python/out/suno/{track_id}__{variation}__structure.txt    (Lyrics field / metatags)
  python/out/suno/{track_id}__{variation}__suno_prompt.txt  (combined reference)
"""
import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOMAIN = REPO_ROOT / "domain"
OUT_DIR = Path(__file__).resolve().parent / "out" / "suno"

SUNO_KITS_PATH = DOMAIN / "suno_kits.json"
SUNO_VOICES_PATH = DOMAIN / "suno_voices.json"
IDENTITIES_PATH = DOMAIN / "album5_identities.json"

STYLE_CHAR_LIMIT = 1000


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_by_track_id(items: list, track_id: str) -> dict | None:
    for item in items:
        if item.get("track_id") == track_id:
            return item
    return None


VARIATION_MODIFIERS = {
    "v0": [],
    "v1": ["stripped back", "more minimal", "less layers", "sparse"],
    "v2": ["heavy percussion", "deep sub bass", "more percussive", "layered drums"],
}


def build_style_prompt(kit: dict, voice: dict, variation: str) -> str:
    """Build Suno Style of Music field from kit + voice + variation."""
    tags = list(kit.get("style_tags_ordered") or [])

    modifiers = VARIATION_MODIFIERS.get(variation) or []
    if modifiers:
        # Remove "instrumental" temporarily, add modifiers, re-add at end
        has_instrumental = "instrumental" in tags
        if has_instrumental:
            tags.remove("instrumental")
        tags.extend(modifiers)
        if has_instrumental:
            tags.append("instrumental")

    prompt = ", ".join(tags)

    if len(prompt) > STYLE_CHAR_LIMIT:
        # Truncate from end preserving whole tags
        while len(prompt) > STYLE_CHAR_LIMIT and tags:
            tags.pop()
            prompt = ", ".join(tags)

    return prompt


def build_structure(kit: dict, voice: dict, variation: str) -> str:
    """Build Suno Lyrics field (metatag structure) from kit template."""
    structure = kit.get("structure_template") or ""
    return structure


def build_combined_reference(
    track_id: str,
    kit: dict,
    voice: dict,
    identity: dict,
    style_prompt: str,
    structure: str,
    variation: str,
) -> str:
    """Build combined human-readable reference with all three layers."""
    lines = []

    # Header
    state_label = kit.get("state_label") or ""
    lines.append(f"=== {track_id} / {state_label} / {variation} ===")
    lines.append(f"Suno v5.5 | Kit + Voice Export")
    lines.append("")

    # Style field (copy-paste ready)
    lines.append("--- STYLE OF MUSIC (paste into Suno Style field) ---")
    lines.append(style_prompt)
    lines.append(f"[{len(style_prompt)}/{STYLE_CHAR_LIMIT} chars]")
    lines.append("")

    # Structure / Lyrics field (copy-paste ready)
    lines.append("--- LYRICS / STRUCTURE (paste into Suno Lyrics field) ---")
    lines.append(structure)
    lines.append("")

    # Voice reference
    lines.append("--- VOICE PROFILE (for Suno Voices selection) ---")
    lines.append(f"character: {voice.get('voice_character', '')}")
    lines.append(f"anchor: {voice.get('delivery_anchor', '')}")
    lines.append(f"register: {voice.get('register', '')}")
    lines.append(f"intensity: {voice.get('intensity', '')}")
    lines.append(f"vocal_tags: {', '.join(voice.get('suno_vocal_tags') or [])}")
    lines.append(f"persona: {voice.get('persona_notes', '')}")
    lines.append("")

    # Kit metadata
    lines.append("--- KIT METADATA ---")
    lines.append(f"bpm_target: {kit.get('bpm_target', '')}")
    lines.append(f"bpm_range: {kit.get('bpm_range', '')}")
    lines.append(f"energy_curve: {kit.get('energy_curve', '')}")
    lines.append(f"groove: {kit.get('groove', '')}")
    lines.append("")

    # Crowding strategy (negative prompt workaround)
    crowding = kit.get("crowding_tags") or []
    if crowding:
        lines.append("--- CROWDING TAGS (add if unwanted elements appear) ---")
        lines.append(", ".join(crowding))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Export Suno v5.5 prompt for Album 5 track"
    )
    parser.add_argument(
        "--track_id",
        default="radical.grey",
        help="Track id (default: radical.grey)",
    )
    parser.add_argument(
        "--variation",
        choices=["v0", "v1", "v2"],
        default="v0",
        help="v0=base, v1=more minimal, v2=more percussion + sub",
    )
    args = parser.parse_args()
    track_id = args.track_id
    variation = args.variation

    # Load sources
    kits_data = load_json(SUNO_KITS_PATH)
    voices_data = load_json(SUNO_VOICES_PATH)
    identities_data = load_json(IDENTITIES_PATH)

    kit = find_by_track_id(kits_data.get("kits") or [], track_id)
    if not kit:
        raise SystemExit(f"Kit not found: {track_id}")

    voice = find_by_track_id(voices_data.get("voices") or [], track_id)
    if not voice:
        raise SystemExit(f"Voice not found: {track_id}")

    identity = find_by_track_id(
        identities_data.get("identities") or [], track_id
    )
    if not identity:
        raise SystemExit(f"Identity not found: {track_id}")

    # Build outputs
    style_prompt = build_style_prompt(kit, voice, variation)
    structure = build_structure(kit, voice, variation)
    combined = build_combined_reference(
        track_id, kit, voice, identity, style_prompt, structure, variation
    )

    # Write files
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    style_path = OUT_DIR / f"{track_id}__{variation}__style.txt"
    structure_path = OUT_DIR / f"{track_id}__{variation}__structure.txt"
    combined_path = OUT_DIR / f"{track_id}__{variation}__suno_prompt.txt"

    style_path.write_text(style_prompt, encoding="utf-8")
    structure_path.write_text(structure, encoding="utf-8")
    combined_path.write_text(combined, encoding="utf-8")

    # Print paths relative to repo root
    for p in [style_path, structure_path, combined_path]:
        print(p.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
