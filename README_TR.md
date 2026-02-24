# REST — Radical Noface 5 Renkli Bilinç Sistemi

## 1. Projenin Amacı

REST (Radical Noface Structural Engine), rap-techno füzyonunda yapısal kontrol ve prompt üretimi için JSON-merkezli bir yapılandırma sistemidir. Amaç, tekrarlanabilir, ölçülebilir ve deterministik bir üretim hattı sunmaktır. Ses ve vokal kimliği beş renkli bilinç modeli ile tanımlanır; her parça tek bir renkle eşleşir.

## 2. 5 Renkli Bilinç Modeli

Aktif parça seti beş renge indirgenmiştir. Her renk bir duygusal çekirdek ve ses kimliği taşır.

| Renk  | Duygusal Çekirdek   | Açıklama                          |
|-------|---------------------|-----------------------------------|
| Grey  | Concrete Rage       | Metropolis, somut öfke, disiplin  |
| Blue  | Blue Sorrow         | Duygusal gerilim, içsel hüzün     |
| Green | Saturated Growth   | Takıntılı büyüme, döngü, genişleme |
| Cream | Intimate Heat       | Sıcak yakınlık, samimiyet         |
| Black | Divine Smoke        | Ego, tekil soğuk baskınlık        |

Her track_id bir renkle bire bir eşlenir: radical.grey, radical.blue, radical.green, radical.cream, radical.black.

## 3. Mimari Yapı

- **domain/**  
  Yapılandırma kilidi ve eşleme dosyaları. `domain_lock.json` etkin renkleri ve kalibrasyon kurallarını tanımlar. `sound_map.json` (v2) track_id → renk → sound_class eşlemesini ve renk başına emotion_core değerlerini tutar.

- **tracks/**  
  Yalnızca beş aktif parça JSON’ı. Her dosya şema ile uyumludur; theme, emotional_tone, lyrical_focus ve techno_profile renk kimliğini taşır. constraints.bpm_override kalibrasyon/production’a göre ayarlanır.

- **knowledge/**  
  `sound_library.json` (v2) sound_class prompt paketleri ve `color_profiles` (tone, vocal_style, mix_target, energy) içerir. Registry ve track bazlı knowledge dosyaları deney geçmişi ve 0-run durumunu yansıtır.

- **python/**  
  Araç katmanı. Kod kaynağı değildir; JSON kaynaklı kararları çalıştırır.

- **suggest.py**  
  `domain/sound_map.json` ve `knowledge/sound_library.json` ile tracks’i okuyarak parça başına deterministik öneri JSON’ları üretir. Çıktı: `python/out/suggestions/<track_id>.suggestion.json` ve `_bundle.json`. resolved alanı color, emotion_core, sound_class, bpm_source içerir. prompt_text, style_core, token’lar, structure, lyric ve color tone’u birleştirir. Yalnızca calibration modunda constraints.bpm_override değişir.

## 4. Determinizm ve Kalite Kontrol

- Tüm yapılandırma JSON’dadır; varsayılan yok, belirtilmeyen değerler null ile temsil edilir.
- Key ve dizi sırası sabittir; zaman damgası ve rastgelelik kullanılmaz.
- Tek değişken kuralı: Kalibrasyonda yalnızca BPM override değişir.
- `validate.py` track ve run şemalarına karşı doğrulama yapar. `dataset.py` run çıktılarını suggestion_version, suggestion_hash, sound_class, bpm_override ile dataset.jsonl’e yazar; ML ve kalite izleme için aynı konfigürasyon hash’i kullanılabilir.

## 5. Sound Identity

Her renk için ses ve vokal imzası sound_library color_profiles ve sound_map ile tanımlanır: tone, vocal_style, mix_target, energy. Sound class’lar (cold_industrial, distorted_hard_techno, hypnotic_loop_techno, high_shine_peak, dark_hypnotic_modular vb.) prompt_pack ile rap-techno ve ritmik konuşma vokal çizgisine uyumlu tutulur. Suno üretim motoru için prompt_text bu bileşenlerden türetilir.

## 6. Uzun Vadeli Hedef

Sürdürülebilir, versiyonlu ve ölçülebilir bir rap-techno kataloğu: her parça renk kimliği ve BPM ile sabitlenir, drift sınıflandırması ve corrective adjustment ile kalite korunur. Dataset.jsonl ve suggestion hash’leri “aynı kaliteyi koruma” metriği için kullanılır.

## 7. Felsefe

Yapı önce gelir; JSON tek gerçek kaynaktır. Python yalnızca bu yapıyı okuyup çıktı üreten bir katmandır. Beş renk, karmaşık ahlaki çerçeveyi kaldırıp yalnızca ses ve duygu çekirdeğine indirger. Determinizm ve açık null politikası, sessiz varsayımları reddeder; her karar yapılandırmada görünür olur.
