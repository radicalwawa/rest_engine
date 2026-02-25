# REST — Radical Noface Yapısal Motor

REST deterministik bir bilinç-ses motorudur. Tek gerçek kaynak JSON’dır; Python yalnızca araçtır.

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

## Yönetişim

- JSON gerçektir. Eksik yerine null.
- Commit başına tek kapsam. Her şeyin üstünde determinizm.
- Rastgelelik yok. Estetik sapma yok.

## Mimari

- **domain/** — Yapılandırma, works_manifest, albüm kimlikleri, şemalar.
- **tracks/** — Yalnızca beş aktif parça JSON dosyası. Eski parçalar tracks_deprecated/ içinde.
- **knowledge/** — sound_library.json (v2+), color_profiles, kits, flows, templates.
- **python/** — validate.py, suggest.py, suno_export.py, ui.py (CLI), tui.py (TUI). Çıktılar python/out/ altında.

Öneri akışı: domain + knowledge + tracks → python/out/suggestions/<track_id>.suggestion.json. resolved alanı color, emotion_core, sound_class, bpm_source içerir; variant seed_hash_hex içerir.

## Determinizm

- Tüm yapılandırma JSON’da; belirtilmeyen değerler null.
- Sabit anahtarlar ve sıra; yapılandırmada zaman damgası veya rastgelelik yok.
- validate.py parça ve önerileri şemalara karşı doğrular.

## Güncel Sistem Durumu

- 5 renk modeli aktif. sound_library v2.2.
- Deterministik varyant sistemi; çapraz dil güvenliği için seed_hash_hex.
- Eski parçalar tracks_deprecated içinde izole.
