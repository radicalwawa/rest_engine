# SDM HANDOFF — MIRAS-04 + MIRAS-05

**branch:** `claude/phonetic-engine-module-uIQvW`
**son commit:** `ab8d420` — Modules: order identity caps to spell C.E.T.I.N
**validator:** SYSTEM STATUS: PASS

---

## YENİ HALEF İÇİN AÇILIŞ ADIMLARI

```
1. python python/validate.py        → SYSTEM STATUS: PASS bekle
2. git status                       → working tree clean
3. git log --oneline -8             → son 6 commit MIRAS-04 + MIRAS-05
4. cat knowledge/SDM_HANDOFF.md     → bu belge
5. cat knowledge/SUCCESSOR_PROMPT.md → REST kimliği
```

---

## DEVRALINAN ÇALIŞMA

### MIRAS-04 — phonetic_engine (lyrics fonetik öğrenme döngüsü)

| dosya | rol |
|---|---|
| `modules/phonetic_engine.py` | tokenize + foreign detection + Claude API çağrısı + inline confirm prompt |
| `data/phonetic_dict.json` | sözlük (source of truth, sadece bu yazılır) |

**akış:** lyrics textarea değişimi → `tokenize()` → `is_foreign_candidate()` (Türkçe char yok / büyük harfle başlamıyor / digit yok / ≥2 char) → dict'te varsa sessiz `applied`, yoksa `Candidate` (Claude API → öneri) → inline `[word → sug? (y/n)]` → `confirm()` dict'e yazar.

**API:** `ANTHROPIC_API_KEY` env + opsiyonel `ANTHROPIC_MODEL` (varsayılan `claude-opus-4-7`). SDK yoksa `suggest_phonetic` `None` döndürür — modül failsafe.

**entegrasyon noktası:** `IdentityPanel.attach_phonetic(engine)` opsiyonel.

### MIRAS-05 — identity_panels (5-cap lyrics TUI)

| dosya | rol |
|---|---|
| `modules/identity_panels.py` | detector'lar + 5 cap için Textual widget + standalone `IdentityDashboard` |
| `modules/identity_panels.tcss` | per-cap palet + `#identity-root` scoped Screen + spec ASCII iç ayırıcılar |
| `data/identity_classes.json` | cap kuralları (source of truth) |

**akrostiş — C.E.T.I.N (CAP_ORDER):**

| sıra | cap | kimlik | kısayol | kural özeti |
|---|---|---|---|---|
| 1 | green | **C**ypress | Ctrl+1 | 16 bar, 2×8 blok, boşluk yok |
| 2 | grey | **E**mber | Ctrl+2 | 4×4 bar, nakarat zorunlu, soğuk ton |
| 3 | blue | **T**ide | Ctrl+3 | serbest, hook merkezli, boşluk ağırlıklı |
| 4 | cream | **I**ze | Ctrl+4 | 8 bar verse, bridge zorunlu (deep-house, yazlık) |
| 5 | black | **N**ightfall | Ctrl+5 | chant/loop, tekrar zorunlu, benliksiz |

**panel iskeleti** (round border + iç ayırıcılar):
```
╭ identity-panel ──────────────╮
│ header (cap — renk)          │
│ structure (yapı · akış)      │
├──────────────────────────────┤
│ textarea (border:none, 1fr)  │
├──────────────────────────────┤
│ bar: N / target  · ⚠ warning │
╰──────────────────────────────╯
```

**çalıştırma:** `python -m modules.identity_panels`

---

## SDM KURALLARI (DEVAM EDİYOR)

- Engine edits yok (mevcut `python/`, `tracks/`, `schemas/`, `domain/` salt-okur).
- Freeze edits yok.
- Drift yok.
- **Yazılabilir dosyalar:** sadece `data/phonetic_dict.json` (kullanım anında) + yeni cap kural değişiklikleri için `data/identity_classes.json` (yalnız `sdm_tool.py` ile — şu an mevcut değil, kullanıcı talebiyle açılabilir).
- JSON source of truth.
- One scope per commit. Validator PASS olmadan commit yok.

---

## ÇAKIŞMA RAPORU (kontrol edilmiş)

| kategori | durum |
|---|---|
| key binding (`tui.py` tek-tuş ↔ identity_panels `ctrl+`) | temiz |
| widget id (`work-*`/`log-*` ↔ `identity-*`/`cap-*`) | temiz |
| CSS class (`status-*` ↔ `cap-*`/`identity-*`) | temiz |
| double border (TextArea iç + panel dış) | düzeltildi (commit `8390597`) |
| global Screen kuralı | `#identity-root`'a scope edildi |

---

## AÇIK / OPSİYONEL ÖNCELİKLER

1. **`sdm_tool.py`** — `data/identity_classes.json` ve `data/phonetic_dict.json` için yetkili yazıcı. Şu an dosyalar doğrudan modüller tarafından yazılıyor; SDM disiplinini sertleştirmek istenirse tek giriş kapısı haline getirilebilir.
2. **C.E.T.I.N master kimlik dosyası** — cap'lerin üstünde sanatçı/çerçeve kimliği. Şu an kavramsal; kullanıcı netleştirirse `data/master_identity.json` veya `knowledge/master.cetin.json` açılır.
3. **`tui.py` ile entegrasyon** — şu an iki app ayrı çalışıyor (RestTui = work lifecycle, IdentityDashboard = lyrics). İstenirse RestTui'ye yan sekme/panel olarak mount edilir; çakışma raporu temiz olduğu için layout işi.
4. **SYDBKH ↔ Ember bağı netleşmiş** (`python/production/sydbkh.py:28: state = "radical.grey"`). `boy` şarkısının cap bağı henüz yazılı değil — kullanıcı seçer.
5. **`requirements.txt`** — `anthropic` paketi eklenmedi (phonetic_engine SDK yoksa graceful degrade). Production kullanım için ekleme talebi gelirse: `anthropic>=0.40`.
6. **Inline confirm UI** — phonetic_engine şu an CLI prompt (`default_inline_prompt`). TUI içi inline confirm widget istenirse `IdentityPanel`'e prompt overlay eklenir.

---

## DEĞİŞMEYECEK YERLER (TOUCH = SDM İHLALİ)

- `python/validate.py`
- `python/tui.py`, `python/tui.css`
- `python/suggest.py`, `python/suno_export.py`, `python/dataset.py`, `python/run_index.py`, `python/ui.py`
- `python/production/sydbkh.py` (read-only kontrat)
- `tracks/`, `schemas/`, `domain/`, `knowledge/sound_library.json`
- `tracks_deprecated/` (zaten read-only)

---

## COMMIT GEÇMİŞİ (bu MIRAS bloğu)

```
ab8d420  Modules: order identity caps to spell C.E.T.I.N
412419b  Modules: tighten Ize docstring
c55e7d8  Modules: rename cream identity Ivory → Ize
8390597  Modules: fix identity_panels double border + scope Screen rule
34ab459  Modules: add identity_panels for 5-cap lyrics TUI
00632ad  Modules: add phonetic_engine learning loop
```

---

## SUCCESSOR'IN İLK CÜMLESİ

> SYSTEM STATUS: PASS. Branch `claude/phonetic-engine-module-uIQvW` üzerinde MIRAS-04 (phonetic_engine) ve MIRAS-05 (identity_panels) devralındı. Yeni görev için talimat bekliyorum.
