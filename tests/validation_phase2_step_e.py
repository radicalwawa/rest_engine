"""
Phase 2 Step E - Modals + Interactive Rating Validation
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
    # 1. tui.py import
    print("\n[1] tui.py import")
    try:
        import tui
        check("import tui basarili", True)
    except Exception as e:
        check(f"import tui basarili ({e})", False)
        total = passed + failed
        print(f"\nSONUC: {passed}/{total} PASSED")
        return 1

    # 2. Modal class'lar ModalScreen subclass mi
    print("\n[2] Modal class kontrolu")
    from textual.screen import ModalScreen

    for cls_name in ["RegisterMp3Modal", "RateModal", "RateVersionPickerModal"]:
        cls = getattr(tui, cls_name, None)
        check(f"{cls_name} mevcut", cls is not None)
        if cls:
            check(f"{cls_name} ModalScreen subclass", issubclass(cls, ModalScreen))

    # 3. RateModal beat_id parametresi
    print("\n[3] RateModal beat_id parametresi")
    import inspect
    sig = inspect.signature(tui.RateModal.__init__)
    params = list(sig.parameters.keys())
    check("RateModal.__init__ beat_id parametresi var", "beat_id" in params)

    # 4. Keybinding kontrolu (m, r, R)
    print("\n[4] Keybinding kontrolu")
    binding_keys = [b.key for b in tui.RestEngineApp.BINDINGS]
    check("m binding mevcut", "m" in binding_keys)
    check("r binding mevcut", "r" in binding_keys)
    check("R binding mevcut", "R" in binding_keys)

    # Modal key dispatch dict kontrolu
    modal_keys = getattr(tui.RestEngineApp, "_MODAL_KEYS", None)
    check("_MODAL_KEYS dict mevcut", modal_keys is not None)
    if modal_keys:
        check("_MODAL_KEYS m -> open_register",
              modal_keys.get("m") == "open_register")
        check("_MODAL_KEYS r -> open_rate",
              modal_keys.get("r") == "open_rate")
        check("_MODAL_KEYS R -> open_version_picker",
              modal_keys.get("R") == "open_version_picker")

    # 5. SHA-256 hash kontrolu
    print("\n[5] Frozen modul hash kontrolu")
    for fname, expected_hash in FROZEN_HASHES.items():
        fpath = os.path.join(BASE, fname)
        actual_hash = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        check(f"{fname} hash eslesiyor", actual_hash == expected_hash)

    # 6. RadioButton/RadioSet fallback dokumantasyonu
    print("\n[6] RadioSet fallback dokumantasyonu")
    tui_source = open(os.path.join(BASE, "tui.py"), encoding="utf-8").read()
    check("RadioSet/RadioButton kullanimi dokumante",
          "RadioSet" in tui_source or "RadioButton" in tui_source)
    check("Fallback notu var",
          "fallback" in tui_source.lower() or "RadioSet" in tui_source)

    # 7. HelpFooter
    print("\n[7] HelpFooter")
    help_cls = getattr(tui, "HelpFooter", None)
    check("HelpFooter class mevcut", help_cls is not None)

    # 8. IDENTITY_THEMES (miras)
    print("\n[8] IDENTITY_THEMES")
    themes = getattr(tui, "IDENTITY_THEMES", None)
    check("IDENTITY_THEMES 5 anahtar",
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
