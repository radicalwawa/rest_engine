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
- **Cursor:** Çalıştırma disiplini; kurallar `.cursor/rules/`.
- **Suno:** Export ve prompt pipeline; parçalar ve sound library ile bağlantılı.

## Sound Library

- `knowledge/sound_library.json` — varlık kataloğu (şema: `schemas/sound_library.schema.json`).
- Her aktif parçada `library_binding` zorunlu: kick, bass, hat, lead, texture (kütüphanedeki asset id’leri).
- Doğrulama binding bütünlüğü ve color_state eşleşmesini zorunlu kılar.

## Süre Politikası

- `domain/album_5_manifest.json` — `release_format` radyo ve extended sürüm hedeflerini (sn), min/target/max ve yayın stratejisini tanımlar.
- Doğrulama sayısal aralıkları ve ayrım kuralını (radio max < extended min) zorunlu kılar.

## Yönetişim

Commit başına tek kapsam. Commit öncesi validate. Spontane refactor yok. GOVERNANCE.md ve docs/PRODUCTION_LOCK.md.
