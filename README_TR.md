# REST — Radical Noface Yapısal Motor

REST deterministik bir bilinç-ses motorudur. Tek gerçek kaynak JSON’dır; Python yalnızca araçtır.

## Hızlı Başlangıç — Doğrulama

Reponun kökünden:

- **Windows:** `py -X faulthandler python/validate.py`  
  `python` takılırsa Windows Store “Uygulama yürütme diğer adları”ndan python.exe/python3.exe kapatın (GOVERNANCE.md).
- **Betikler:** Windows’ta deterministik giriş için `scripts\validate.cmd` veya `scripts\validate.ps1`.

Politika: GOVERNANCE.md, docs/PRODUCTION_LOCK.md.

## 5 Renk Modeli

Beş sabit durum. Renk başına bir parça. Karıştırma yok.

| Renk  | Duygusal Çekirdek   |
|-------|---------------------|
| Grey  | Concrete Rage       |
| Blue  | Blue Sorrow         |
| Green | Saturated Growth    |
| Cream | Intimate Heat       |
| Black | Divine Smoke        |

Parça kimlikleri: radical.grey, radical.blue, radical.green, radical.cream, radical.black.

## Repo Katmanları

- **JSON / Şemalar:** Tek gerçek kaynak. Şemalar `schemas/`. Eksik yerine null.
- **Python:** Sadece araç. `python/validate.py`, `python/production/` altında üretim betikleri.
- **Suno:** Export ve prompt pipeline; parçalar ve sound library ile bağlantılı.

## v2.0 — SQL Operasyonel Katman (Phase 1+2)

- **rest_engine.db** — SQLite operasyonel state. Şema `migrations/` altında,
  `domain/identities_v3_seed.json`'dan seed'lenir.
- **db_manager.py** — `rest_engine.db` üzerine CRUD katmanı. Tüm DB erişimi buradan.
- **prompt_engine.py** — Suno prompt varyasyonları (base, bpm_shift, mood_shift,
  instrument_swap, energy_shift, track). DB destekli.
- **daily_pipeline.py** — Operasyonel akış: `init_daily_queue` → `stage_prompts` →
  `process_queue_item` → `review_beat`.
- **tui.py** — Textual dashboard. 5 renk identity paneli, rating + notes UI, MP3
  arşiv akışı.
- **sdm_tool.py** — Successor Document Memo (MIRAS) bookkeeping. Komutlar:
  `touch <sdm.json>`, `event`, `mission`.

### Akış: Suno → arşiv → puan
1. Suno'da prompt'tan track üret.
2. mp3'ü `rest_inbox/` klasörüne indir.
3. `register_beat_mp3(color, track_name)` çağır (veya TUI üzerinden). MP3
   `archive/beats/<color>/<track>/<track>_vN.mp3` yoluna kopyalanır, beats satırı eklenir.
4. 5 boyutu (id, flow, beat, energy, replay) 1–5 arası puanla + serbest not.
5. notes tablosu color-scoped feedback tutar; `prompt_engine` sonraki üretimde okur.

### Testler
`tests/validation_phase1.py` ve
`tests/validation_phase2_step_{a,a2,b,b2,c,d,e,f,g}.py`'de 10/10 validation suite.
Hepsi idempotent.

## Sound Library

- `knowledge/sound_library.json` — varlık kataloğu (şema: `schemas/sound_library.schema.json`).
- Her aktif parçada `library_binding` zorunlu: kick, bass, hat, lead, texture (kütüphanedeki asset id’leri).
- Doğrulama binding bütünlüğü ve color_state eşleşmesini zorunlu kılar.

## Süre Politikası

- `domain/album_5_manifest.json` — `release_format` radyo ve extended sürüm hedeflerini (sn), min/target/max ve yayın stratejisini tanımlar.
- Doğrulama sayısal aralıkları ve ayrım kuralını (radio max < extended min) zorunlu kılar.

## Yönetişim

Commit başına tek kapsam. Commit öncesi validate. Spontane refactor yok. GOVERNANCE.md ve docs/PRODUCTION_LOCK.md.
