# REST — Radical Noface 5-Color Consciousness System

## 1. Purpose of the Project

REST (Radical Noface Structural Engine) is a JSON-centric configuration system for structural control and prompt generation in rap-techno fusion. The goal is to provide a repeatable, measurable, and deterministic production pipeline. Sound and vocal identity are defined by a five-color consciousness model; each track maps to a single color.

## 2. 5-Color Consciousness Model

The active track set is reduced to five colors. Each color carries an emotional core and a sound identity.

| Color | Emotional Core   | Description                              |
|-------|------------------|------------------------------------------|
| Grey  | Concrete Rage    | Metropolis, concrete aggression, discipline |
| Blue  | Blue Sorrow      | Emotional tension, internal sorrow      |
| Green | Saturated Growth | Obsessive growth, loop, expansion         |
| Cream | Intimate Heat    | Warm closeness, sincerity                |
| Black | Divine Smoke     | Ego, singular cold dominance             |

Each track_id maps one-to-one to a color: radical.grey, radical.blue, radical.green, radical.cream, radical.black.

## 3. Architecture

- **domain/**  
  Configuration lock and mapping files. `domain_lock.json` defines active colors and calibration rules. `sound_map.json` (v2) holds track_id → color → sound_class mapping and emotion_core per color.

- **tracks/**  
  Five active track JSON files only. Each file is schema-compliant; theme, emotional_tone, lyrical_focus, and techno_profile carry the color identity. constraints.bpm_override is set according to calibration or production.

- **knowledge/**  
  `sound_library.json` (v2) contains sound_class prompt packs and `color_profiles` (tone, vocal_style, mix_target, energy). Registry and per-track knowledge files reflect experiment history and 0-run state.

- **python/**  
  Tooling layer. Code is not the source of truth; it executes decisions derived from JSON.

- **suggest.py**  
  Reads `domain/sound_map.json` and `knowledge/sound_library.json` together with tracks to produce deterministic suggestion JSONs per track. Output: `python/out/suggestions/<track_id>.suggestion.json` and `_bundle.json`. The resolved field contains color, emotion_core, sound_class, and bpm_source. prompt_text combines style_core, tokens, structure, lyric, and color tone. Only constraints.bpm_override changes in calibration mode.

## 4. Determinism and Quality Control

- All configuration is in JSON; no implicit defaults; omitted values are represented as null.
- Key and array order are stable; no timestamps or randomness.
- Single-variable rule: only BPM override changes during calibration.
- `validate.py` validates tracks and runs against schemas. `dataset.py` writes run outputs to dataset.jsonl with suggestion_version, suggestion_hash, sound_class, and bpm_override; the same configuration hash can be used for ML and quality monitoring.

## 5. Sound Identity

Per-color sound and vocal signatures are defined in sound_library color_profiles and sound_map: tone, vocal_style, mix_target, energy. Sound classes (cold_industrial, distorted_hard_techno, hypnotic_loop_techno, high_shine_peak, dark_hypnotic_modular, etc.) are kept compatible with rap-techno and rhythmic spoken vocal line via prompt_pack. prompt_text for the Suno generation engine is derived from these components.

## 6. Long-Term Goal

A sustainable, versioned, and measurable rap-techno catalogue: each track is anchored by color identity and BPM; quality is maintained through drift classification and corrective adjustment. dataset.jsonl and suggestion hashes support a “preserve same quality” metric.

## 7. Philosophy

Structure comes first; JSON is the source of truth. Python is only a layer that reads this structure and produces output. The five colors strip away a complex moral framework and reduce to sound and emotional core only. Determinism and an explicit null policy reject silent assumptions; every decision remains visible in configuration.
