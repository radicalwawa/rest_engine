# REST Ops Log

Operational and migration log for the REST (Radical Noface Structural Engine) repo.

## 5-Color Migration (Completed)

- **Domain:** domain_lock.json → 5_color_consciousness; active_colors = grey, blue, green, cream, black. sound_map.json v2 → track_to_color_v2, mappings for 5 tracks only.
- **Tracks:** Active set reduced to 5 (radical.grey, .blue, .green, .cream, .black). Legacy 7-track set moved to tracks_deprecated/.
- **Knowledge:** sound_library.json v2.0 → color_profiles; v2.1 → kits[], flows[], templates[] per color. registry.json → version 2.0, active_tracks (5), run_ids [], updated_at null.
- **Generator:** suggest.py reads sound_map v2 and color_profiles; resolved contains color, emotion_core, sound_class, bpm_source, variant (template_id, flow_id, kit_id, indices, seed_hash_hex). prompt_text built from selected template skeleton (placeholder replace). Fallback: legacy prompt build if no skeleton.
- **Dataset:** dataset.py uses color + emotion_core (no emotion_profile); suggestion_hash from prompt_text | bpm_override | sound_class | color | emotion_core.
- **Schemas:** track.schema.json and run_results.schema.json track_id enum updated to 5 colors. suggestion.schema.json added for suggestion outputs.
- **Validation:** validate.py validates tracks, runs (manifest/results), and suggestions (python/out/suggestions/*.suggestion.json). Only active 5 track_ids are validated; legacy 7-track suggestion files are skipped with a single-line log: `skipped legacy suggestion: <path>`.

## Sound library v2.2

- **Variant pool expansion:** kits/flows/templates 9 per color (scratch-techno, soft-transition). Kod değişmedi; sadece havuz genişledi. Aynı seed ile seçilen index değişebilir (len N arttı) — bu "drift" değil, kontrollü evrim.
- **Kit 4–9 identity:** Renge özgü sound_class ve mix_target; 5 kapı kimliği güçlendirildi. items[]'a yeni sound_class'lar eklendi (Grey: hard_minimal, metallic_perc; Blue: deep_melodic, dub_techno, airy_pads; Green: acid_hypno, rolling_groove, saturated_bass; Cream: warm_groove, soulful_tech, intimate_low_mids; Black: dark_peak, minimal_dominant, smoke_bass). Her biri için prompt_pack tanımlı. Davranış (blend_drive vb.) aynı, tonal dünya renge göre ayrışıyor.

## Conventions

- One scope per commit. No batched unrelated edits.
- JSON source of truth; Python is tooling only. Null instead of omission.
- Deterministic ordering; no timestamps or randomness in config/output.
- Legacy suggestion outputs: either move to python/out/suggestions_deprecated/ or leave under .gitignore; validate skips them by track_id.

## Successor

See knowledge/SUCCESSOR_PROMPT.md for the single-source master prompt for the next maintainer or agent session.
