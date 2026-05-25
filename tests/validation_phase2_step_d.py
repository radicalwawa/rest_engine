"""
Phase 2 Step D - Panel Wiring Validation
"""
import hashlib
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

FROZEN_HASHES = {
    "db_manager.py": "66080761d7658cd49f5c2419be331d8b3349ac58856b86fdafa88591a0a3f053",
    "prompt_engine.py": "ef39a6c1df61cf13ec69c5fbd682201930954887e8abf139f3bbffffe5364866",
    "daily_pipeline.py": "de151348ffe2e5503cb3fcd8defdfb1355ccf335af322071f7cd3b9d90688c51",
}

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label}")


def main():
    # 1. tui.py var mi ve import edilebilir mi
    print("\n[1] tui.py import")
    tui_path = os.path.join(BASE, "tui.py")
    check("tui.py mevcut", os.path.isfile(tui_path))

    try:
        import tui
        check("import tui basarili", True)
    except Exception as e:
        check(f"import tui basarili ({e})", False)
        total = passed + failed
        print(f"\nSONUC: {passed}/{total} PASSED")
        return 1

    # 2. RestEngineApp attribute/method kontrolu
    print("\n[2] RestEngineApp attribute/method")
    app_cls = tui.RestEngineApp

    check("active_color attr", hasattr(app_cls, "active_color"))
    check("active_color default 'green'", getattr(app_cls, "active_color", None) == "green")
    check("lyrics_drafts attr", hasattr(app_cls, "lyrics_drafts"))
    check("switch_identity method (action_switch_identity)",
          callable(getattr(app_cls, "action_switch_identity", None)))

    # 3. _transform_lyrics
    print("\n[3] _transform_lyrics")
    transform_fn = getattr(tui, "_transform_lyrics", None)
    check("_transform_lyrics mevcut", transform_fn is not None)

    if transform_fn:
        result = transform_fn("green", "line one\n\nline two", {})
        check("donuste [verse] etiketi var", "[verse]" in result)
        check("donuste girdi metni korunmus (line one)", "line one" in result)
        check("donuste girdi metni korunmus (line two)", "line two" in result)
        # 2 blok: verse + hook
        check("donuste [hook] etiketi var (2 blok)", "[hook]" in result)
    else:
        for _ in range(4):
            check("_transform_lyrics test", False)

    # 4. _copy_to_clipboard
    print("\n[4] _copy_to_clipboard")
    clipboard_fn = getattr(tui, "_copy_to_clipboard", None)
    check("_copy_to_clipboard mevcut", clipboard_fn is not None)

    if clipboard_fn:
        try:
            clipboard_fn("test")
            check("_copy_to_clipboard('test') hata vermedi", True)
        except Exception as e:
            check(f"_copy_to_clipboard('test') hata vermedi ({e})", False)
    else:
        check("_copy_to_clipboard cagri testi", False)

    # 5. requirements.txt
    print("\n[5] requirements.txt")
    req_path = os.path.join(BASE, "requirements.txt")
    check("requirements.txt mevcut", os.path.isfile(req_path))
    if os.path.isfile(req_path):
        content = open(req_path).read()
        check("textual satiri var", "textual" in content)
        check("pyperclip satiri var", "pyperclip" in content)
    else:
        check("textual satiri var", False)
        check("pyperclip satiri var", False)

    # 6. Frozen modul hash kontrolu
    print("\n[6] Frozen modul hash kontrolu")
    for fname, expected_hash in FROZEN_HASHES.items():
        fpath = os.path.join(BASE, fname)
        actual_hash = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        check(f"{fname} hash eslesiyor", actual_hash == expected_hash)

    # 7. Discovery comment in tui.py
    print("\n[7] Discovery dokumantasyonu")
    tui_source = open(tui_path, encoding="utf-8").read()
    check("generate_beat_prompt referansi var", "generate_beat_prompt" in tui_source)
    check("lyrics-aware / local helper notu var",
          "LOCAL HELPER" in tui_source or "_transform_lyrics" in tui_source)

    # 8. IDENTITY_THEMES (Step C'den miras)
    print("\n[8] IDENTITY_THEMES")
    themes = getattr(tui, "IDENTITY_THEMES", None)
    check("IDENTITY_THEMES mevcut, 5 anahtar",
          themes is not None and set(themes.keys()) == {"green", "grey", "blue", "cream", "black"})

    # Sonuc
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"SONUC: {passed}/{total} PASSED")
    if failed > 0:
        print(f"BASARISIZ: {failed} assertion")
    else:
        print("Tum assertion'lar gecti!")
    print(f"{'='*50}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
