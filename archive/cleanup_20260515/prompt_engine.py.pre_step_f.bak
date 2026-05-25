"""
prompt_engine.py
REST ENGINE — Phase 1 Step 2 (MIRAS_20260320_v3).

Builds Suno prompts from v3 identity profiles. Supports variations:
  - base            : verbatim suno_base_prompt from identity row
  - bpm_shift       : nudge BPM hint up/down by ±5 within identity's bpm range
  - mood_shift      : swap mood adjective from identity-defined alternatives
  - instrument_swap : substitute one instrument from rap/techno/shared pools
  - energy_shift    : raise or lower energy hint
  - track           : adds vocal/lyrics framing on top of beat prompt

All DB access goes through db_manager. Every generated prompt is logged
to suno_prompts via db_manager.save_prompt_template().
"""

from __future__ import annotations

import random
from typing import Optional

import db_manager as dbm


# ---------------------------------------------------------------------------
# Variation vocabularies (per-color overrides could move to DB later; for now
# they live in code as deterministic, reviewable constants).
# ---------------------------------------------------------------------------

_MOOD_ALTS = {
    "green":  ["smoky", "meditative", "rooted", "dusty", "contemplative", "earthy"],
    "grey":   ["cold", "menacing", "mechanical", "claustrophobic", "urban", "bleak"],
    "blue":   ["dreamy", "melancholic", "floating", "introspective", "fragile", "suspended"],
    "cream":  ["sensual", "warm", "intimate", "golden", "smooth", "velvety"],
    "black":  ["dark", "euphoric", "ritualistic", "hypnotic", "primal", "relentless"],
}

_ENERGY_LOWER = {
    "green":  "lower the energy further, sparser drums, more space between hits",
    "grey":   "pull back the aggression slightly, more restrained, simmering tension",
    "blue":   "even more suspended, near-ambient, drums barely present",
    "cream":  "softer groove, more intimate, late-night feel",
    "black":  "build-up section energy rather than peak-time, controlled tension",
}

_ENERGY_HIGHER = {
    "green":  "more head-nod drive, busier drum fills, slight tempo push",
    "grey":   "full-throttle aggression, denser drill hats, harder kick",
    "blue":   "lift toward melodic techno club energy, more arpeggio drive",
    "cream":  "raise to house-club energy, four-on-the-floor more present",
    "black":  "full peak-time intensity, layered stabs, sustained release",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_profile(color: str) -> dict:
    prof = dbm.get_identity_profile(color)
    if prof is None:
        raise ValueError(f"no identity profile for color {color!r}")
    return prof


def _pick_bpm(prof: dict, rng: random.Random) -> int:
    lo, hi = int(prof["bpm_min"]), int(prof["bpm_max"])
    return rng.randint(lo, hi)


def _apply_bpm_shift(base: str, prof: dict, rng: random.Random) -> tuple[str, dict]:
    target = _pick_bpm(prof, rng)
    suffix = f" [bpm hint: {target}, within {prof['bpm_min']}-{prof['bpm_max']}]"
    return base + suffix, {"bpm_target": target}


def _apply_mood_shift(base: str, color: str, rng: random.Random) -> tuple[str, dict]:
    alts = _MOOD_ALTS.get(color, [])
    if not alts:
        return base, {}
    chosen = rng.choice(alts)
    suffix = f" [mood emphasis: {chosen}]"
    return base + suffix, {"mood_emphasis": chosen}


def _apply_instrument_swap(base: str, prof: dict, rng: random.Random) -> tuple[str, dict]:
    pool = []
    for key in ("instrumentation_rap", "instrumentation_techno", "instrumentation_shared"):
        items = prof.get(key) or []
        if isinstance(items, list):
            pool.extend(items)
    if not pool:
        return base, {}
    feature = rng.choice(pool)
    suffix = f" [feature instrument: {feature}]"
    return base + suffix, {"feature_instrument": feature}


def _apply_energy_shift(base: str, color: str, rng: random.Random) -> tuple[str, dict]:
    direction = rng.choice(("lower", "higher"))
    table = _ENERGY_LOWER if direction == "lower" else _ENERGY_HIGHER
    note = table.get(color)
    if not note:
        return base, {"energy_direction": direction}
    suffix = f" [energy: {note}]"
    return base + suffix, {"energy_direction": direction}


_VARIATION_DISPATCH = {
    "bpm_shift":       _apply_bpm_shift,
    "mood_shift":      _apply_mood_shift,
    "instrument_swap": _apply_instrument_swap,
    "energy_shift":    _apply_energy_shift,
}

VALID_VARIATIONS = ("base",) + tuple(_VARIATION_DISPATCH.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_beat_prompt(
    color: str,
    variation_type: Optional[str] = "base",
    seed: Optional[int] = None,
    persist: bool = True,
) -> dict:
    """Generate a beat-style Suno prompt for the given color identity.

    Returns:
        {
          "color": str,
          "prompt_type": "beat",
          "variation_type": str,
          "style_prompt": str,
          "negative_prompt": str,
          "meta": dict,          # variation-specific extras
          "prompt_id": int|None, # suno_prompts.id if persist=True else None
        }
    """
    variation_type = variation_type or "base"
    if variation_type not in VALID_VARIATIONS:
        raise ValueError(
            f"unknown variation_type: {variation_type!r}; "
            f"expected one of {VALID_VARIATIONS}"
        )

    prof = _require_profile(color)
    rng = random.Random(seed)

    base_style = prof["suno_base_prompt"]
    negative   = prof["negative_prompt"]
    meta: dict = {}
    style_prompt = base_style

    if variation_type == "bpm_shift":
        style_prompt, meta = _apply_bpm_shift(base_style, prof, rng)
    elif variation_type == "mood_shift":
        style_prompt, meta = _apply_mood_shift(base_style, color, rng)
    elif variation_type == "instrument_swap":
        style_prompt, meta = _apply_instrument_swap(base_style, prof, rng)
    elif variation_type == "energy_shift":
        style_prompt, meta = _apply_energy_shift(base_style, color, rng)
    # "base" → no change

    prompt_id = None
    if persist:
        prompt_id = dbm.save_prompt_template(
            color=color,
            prompt_type="beat",
            style_prompt=style_prompt,
            negative_prompt=negative,
            variation_type=variation_type,
        )

    return {
        "color": color,
        "prompt_type": "beat",
        "variation_type": variation_type,
        "style_prompt": style_prompt,
        "negative_prompt": negative,
        "meta": meta,
        "prompt_id": prompt_id,
    }


def generate_track_prompt(
    color: str,
    lyrics_theme: Optional[str] = None,
    variation_type: Optional[str] = "base",
    seed: Optional[int] = None,
    persist: bool = True,
) -> dict:
    """Generate a full-track (beat + vocal) Suno prompt.

    Adds vocal framing from identity's vocal_character. Optionally injects
    a lyrics_theme hint (free-form string from the operator).
    """
    beat = generate_beat_prompt(
        color=color,
        variation_type=variation_type,
        seed=seed,
        persist=False,    # we persist the track prompt instead
    )

    prof = _require_profile(color)
    vocal = prof.get("vocal_character") or ""
    style_prompt = beat["style_prompt"]
    if vocal:
        style_prompt += f" | vocal: {vocal}"
    if lyrics_theme:
        style_prompt += f" | lyrics theme: {lyrics_theme}"

    negative = beat["negative_prompt"]

    prompt_id = None
    if persist:
        prompt_id = dbm.save_prompt_template(
            color=color,
            prompt_type="track",
            style_prompt=style_prompt,
            negative_prompt=negative,
            variation_type=variation_type or "base",
        )

    return {
        "color": color,
        "prompt_type": "track",
        "variation_type": variation_type or "base",
        "style_prompt": style_prompt,
        "negative_prompt": negative,
        "meta": {**beat["meta"], "lyrics_theme": lyrics_theme},
        "prompt_id": prompt_id,
    }


def preview(color: str, variation_type: str = "base", seed: Optional[int] = None) -> dict:
    """Generate without persisting. Useful for TUI preview or dry-run."""
    return generate_beat_prompt(color, variation_type=variation_type,
                                seed=seed, persist=False)


# ---------------------------------------------------------------------------
# CLI for smoke testing
# ---------------------------------------------------------------------------

def _cli():
    import argparse, json
    p = argparse.ArgumentParser(description="REST prompt_engine smoke runner")
    p.add_argument("--color", required=True, choices=("green","grey","blue","cream","black"))
    p.add_argument("--type", choices=("beat","track"), default="beat")
    p.add_argument("--variation", choices=VALID_VARIATIONS, default="base")
    p.add_argument("--lyrics-theme", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--persist", action="store_true",
                   help="actually write to suno_prompts table (default: preview only)")
    args = p.parse_args()

    if args.type == "beat":
        out = generate_beat_prompt(args.color, variation_type=args.variation,
                                   seed=args.seed, persist=args.persist)
    else:
        out = generate_track_prompt(args.color, lyrics_theme=args.lyrics_theme,
                                    variation_type=args.variation,
                                    seed=args.seed, persist=args.persist)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _cli()
