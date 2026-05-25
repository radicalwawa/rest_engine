"""
Phase 2 Step C - TUI Scaffold Validation
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
    # 1. tui.py var mi
    print("\n[1] tui.py dosya kontrolu")
    tui_path = os.path.join(BASE, "tui.py")
    check("tui.py repo root'ta mevcut", os.path.isfile(tui_path))

    # 2. import tui yan etki olmadan basarili
    print("\n[2] import tui")
    try:
        import tui
        check("import tui basarili", True)
    except Exception as e:
        check(f"import tui basarili ({e})", False)
        # Devam edemeyiz
        total = passed + failed
        print(f"\nSONUC: {passed}/{total} PASSED")
        return 1

    # 3. IDENTITY_THEMES kontrolu
    print("\n[3] IDENTITY_THEMES")
    themes = getattr(tui, "IDENTITY_THEMES", None)
    check("IDENTITY_THEMES mevcut", themes is not None)

    expected_colors = {"green", "grey", "blue", "cream", "black"}
    actual_colors = set(themes.keys()) if themes else set()
    check("tam 5 renk anahtari", actual_colors == expected_colors)

    expected_keys = {"surname", "accent", "border"}
    all_have_keys = all(
        set(themes[c].keys()) >= expected_keys
        for c in expected_colors
        if c in themes
    ) if themes else False
    check("her renkte surname/accent/border var", all_have_keys)

    # 4. Surname eslesmesi
    print("\n[4] Surname eslesmesi")
    expected_surnames = {
        "green": "Cypress",
        "grey": "Ember",
        "blue": "Tide",
        "cream": "Ize",
        "black": "Nightfall",
    }
    if themes:
        for color, surname in expected_surnames.items():
            actual = themes.get(color, {}).get("surname", "")
            check(f"{color} -> {surname}", actual == surname)
    else:
        for color, surname in expected_surnames.items():
            check(f"{color} -> {surname}", False)

    # 5. RestEngineApp textual.app.App subclass mi
    print("\n[5] RestEngineApp sinif kontrolu")
    from textual.app import App
    app_cls = getattr(tui, "RestEngineApp", None)
    check("RestEngineApp mevcut", app_cls is not None)
    check("App subclass", app_cls is not None and issubclass(app_cls, App))

    # 6. Default identity green
    print("\n[6] Default identity")
    default = getattr(tui, "DEFAULT_IDENTITY", None)
    check("DEFAULT_IDENTITY == 'green'", default == "green")

    # Class attribute kontrolu
    if app_cls:
        cls_active = getattr(app_cls, "active_color", None)
        check("RestEngineApp.active_color == 'green'", cls_active == "green")

    # 7. textual importable
    print("\n[7] textual import")
    try:
        import textual
        check(f"textual importable (v{textual.__version__})", True)
    except ImportError:
        check("textual importable", False)

    # 8. Frozen modul hash kontrolu
    print("\n[8] Frozen modul hash kontrolu")
    for fname, expected_hash in FROZEN_HASHES.items():
        fpath = os.path.join(BASE, fname)
        actual_hash = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        check(f"{fname} hash eslesiyor", actual_hash == expected_hash)

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
