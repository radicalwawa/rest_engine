"""Identity panels — 5 caps × 5 TUI lyrics panels.

Each cap enforces its own class rules (bar target, block size, required
section tags, tonal guards). Violations surface as a single inline warning
line under the textarea. The REST dashboard's outer frame (Header /
WorkList / WorkDetail / Log / Footer) is untouched — this module only
defines lyrics-internal widgets and an optional standalone preview app.

SDM contract:
- Engine edits yok. Freeze edits yok. Drift yok.
- ``data/identity_classes.json`` JSON source of truth.
- Kural değişikliği sadece ``sdm_tool.py`` ile (bu modül salt-okur).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
CLASSES_PATH = ROOT / "data" / "identity_classes.json"

CAP_ORDER: tuple[str, ...] = ("grey", "blue", "green", "cream", "black")

# ---------------------------------------------------------------------- tags

_TAG_RX = re.compile(r"\[([^\]]+)\]")

CHORUS_TAGS = ("chorus", "nakarat", "hook", "refrain")
HOOK_TAGS = ("hook", "nakarat", "chorus")
BRIDGE_TAGS = ("bridge", "köprü", "kopru")
VERSE_TAGS = ("verse", "kıta", "kita")

NARRATIVE_WORDS = {
    "ben", "benim", "bana", "beni", "bende", "benden", "bizim",
    "i", "me", "my", "mine", "myself",
}

AGGRESSION_WORDS = {
    "kill", "blood", "gun", "die", "smash", "rage", "fuck", "hate",
    "öl", "ol", "kan", "silah", "sik", "orospu", "puşt", "pust",
    "katil", "nefret",
}


# ---------------------------------------------------------------------- helpers

def _is_tag_line(s: str) -> bool:
    s = s.strip()
    return bool(s) and s.startswith("[") and s.endswith("]")


def count_bars(text: str) -> int:
    """Non-empty, non-tag lines. Each = 1 bar."""
    if not text:
        return 0
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or _is_tag_line(s):
            continue
        n += 1
    return n


def max_consecutive_bars(text: str) -> int:
    """Longest run of consecutive bar-lines (blank or tag line resets)."""
    cur = best = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or _is_tag_line(s):
            if cur > best:
                best = cur
            cur = 0
        else:
            cur += 1
    return max(best, cur)


def blank_ratio(text: str) -> float:
    lines = text.splitlines()
    if not lines:
        return 0.0
    blanks = sum(1 for l in lines if not l.strip())
    return blanks / len(lines)


def repetition_ratio(text: str) -> float:
    """1 − unique/total non-tag bar lines. 0 = all unique, 1 = all identical."""
    lines = [
        l.strip().lower()
        for l in text.splitlines()
        if l.strip() and not _is_tag_line(l)
    ]
    if not lines:
        return 0.0
    return 1.0 - (len(set(lines)) / len(lines))


def has_any_tag(text: str, names: Iterable[str]) -> bool:
    low = text.lower()
    for n in names:
        if f"[{n.lower()}]" in low:
            return True
    return False


def tag_set(text: str) -> set[str]:
    return {m.strip().lower() for m in _TAG_RX.findall(text)}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\wıİğĞüÜşŞçÇöÖ]+", text.lower())


def has_narrative(text: str) -> bool:
    return any(t in NARRATIVE_WORDS for t in _tokens(text))


def has_aggression(text: str) -> bool:
    return any(t in AGGRESSION_WORDS for t in _tokens(text))


# ---------------------------------------------------------------------- classes

def load_classes(path: Path = CLASSES_PATH) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class CheckResult:
    bars: int
    target: int | None
    warnings: list[str]


def _w(cfg: dict, idx: int) -> str:
    warns = cfg.get("warnings") or []
    return warns[idx] if 0 <= idx < len(warns) else ""


def check_ember(text: str, cfg: dict) -> list[str]:
    """grey — Ember: nakarat + 4×4 bar, soğuk ton."""
    out: list[str] = []
    size = cfg.get("block_size") or 4
    if max_consecutive_bars(text) > size:
        out.append(_w(cfg, 0))
    if cfg.get("requires_chorus") and not has_any_tag(text, CHORUS_TAGS):
        out.append(_w(cfg, 1))
    if has_aggression(text):
        out.append(_w(cfg, 2))
    return [w for w in out if w]


def check_cypress(text: str, cfg: dict) -> list[str]:
    """green — Cypress: 16 bar, 2×8 blok, boşluk yok."""
    out: list[str] = []
    size = cfg.get("block_size") or 8
    target = cfg.get("bar_target") or 16
    if max_consecutive_bars(text) > size:
        out.append(_w(cfg, 0))
    if count_bars(text) > target:
        out.append(_w(cfg, 1))
    # akış yumuşuyor: boşluk satırı oranı yüksek
    if count_bars(text) >= 4 and blank_ratio(text) > 0.25:
        out.append(_w(cfg, 2))
    return [w for w in out if w]


def check_tide(text: str, cfg: dict) -> list[str]:
    """blue — Tide: serbest, hook merkezli, boşluk ağırlıklı."""
    out: list[str] = []
    if cfg.get("requires_hook") and not has_any_tag(text, HOOK_TAGS):
        out.append(_w(cfg, 0))
    if has_aggression(text):
        out.append(_w(cfg, 1))
    # boşluklar kayboluyor: yeterli uzunlukta ama boşluksuz
    lines = text.splitlines()
    if len(lines) >= 6 and blank_ratio(text) < 0.1:
        out.append(_w(cfg, 2))
    return [w for w in out if w]


def check_ize(text: str, cfg: dict) -> list[str]:
    """cream — Ize: verse/chorus/bridge, 8 bar verse."""
    out: list[str] = []
    size = cfg.get("block_size") or 8
    if max_consecutive_bars(text) > size:
        out.append(_w(cfg, 0))
    if cfg.get("requires_bridge") and not has_any_tag(text, BRIDGE_TAGS):
        # only warn if there is enough content
        if count_bars(text) >= size:
            out.append(_w(cfg, 1))
    if has_aggression(text):
        out.append(_w(cfg, 2))
    return [w for w in out if w]


def check_nightfall(text: str, cfg: dict) -> list[str]:
    """black — Nightfall: chant/loop, minimal kelime, benliksiz."""
    out: list[str] = []
    bars = count_bars(text)
    uniqueness = 1.0 - repetition_ratio(text)
    # anlatı tespit edildi: yeterince bar var ve hiç tekrar yok
    if bars >= 4 and uniqueness > 0.9:
        out.append(_w(cfg, 0))
    if has_narrative(text):
        w = _w(cfg, 1)
        if w and w not in out:
            out.append(w)
    # yapı karmaşıklaştı: üçten fazla farklı tag
    if len(tag_set(text)) > 2:
        out.append(_w(cfg, 2))
    return [w for w in out if w]


CHECKERS: dict[str, Callable[[str, dict], list[str]]] = {
    "grey": check_ember,
    "green": check_cypress,
    "blue": check_tide,
    "cream": check_ize,
    "black": check_nightfall,
}


def evaluate(cap: str, text: str, classes: dict[str, dict] | None = None) -> CheckResult:
    classes = classes if classes is not None else load_classes()
    cfg = classes[cap]
    checker = CHECKERS[cap]
    return CheckResult(
        bars=count_bars(text),
        target=cfg.get("bar_target"),
        warnings=checker(text, cfg),
    )


# ---------------------------------------------------------------------- TUI

try:  # Textual is optional — import guarded so detectors run headless.
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Header, Label, ListItem, ListView, Static, TextArea
    _TEXTUAL = True
except Exception:  # pragma: no cover
    _TEXTUAL = False


if _TEXTUAL:

    class IdentityPanel(Vertical):
        """Single lyrics panel — header, textarea, bar counter, warning line."""

        def __init__(self, cap: str, cfg: dict, class_map: dict[str, dict], **kw) -> None:
            super().__init__(**kw)
            self._cap = cap
            self._cfg = cfg
            self._class_map = class_map
            self.add_class("identity-panel")
            self.add_class(f"cap-{cap}")
            self._header: Static | None = None
            self._structure: Static | None = None
            self._textarea: TextArea | None = None
            self._counter: Static | None = None
            self._warning: Static | None = None
            self.last_bars: int = 0
            self.last_warnings: list[str] = []
            # optional phonetic_engine hook (MIRAS-04)
            self._phonetic = None

        def compose(self) -> ComposeResult:
            self._header = Static(
                f"{self._cfg['name']} — {self._cap}",
                classes="identity-header",
            )
            yield self._header
            self._structure = Static(
                f"yapı: {self._cfg.get('structure', '')}  ·  akış: {self._cfg.get('flow', '')}",
                classes="identity-structure",
            )
            yield self._structure
            self._textarea = TextArea(classes="identity-textarea")
            yield self._textarea
            with Horizontal(classes="identity-footer"):
                self._counter = Static(
                    self._format_counter(0),
                    classes="identity-bar-counter",
                )
                yield self._counter
                self._warning = Static("", classes="identity-warning-clear")
                yield self._warning

        def attach_phonetic(self, engine) -> None:
            """Optional: wire MIRAS-04 phonetic_engine to silent-apply hits."""
            self._phonetic = engine

        # textual event: textarea content changed
        def on_text_area_changed(self, event: "TextArea.Changed") -> None:
            if self._textarea is None or event.text_area is not self._textarea:
                return
            self._recompute(self._textarea.text)

        def _format_counter(self, bars: int) -> str:
            tgt = self._cfg.get("bar_target")
            return f"bar: {bars} / {tgt if tgt is not None else '∞'}"

        def _recompute(self, text: str) -> None:
            result = evaluate(self._cap, text, self._class_map)
            self.last_bars = result.bars
            self.last_warnings = list(result.warnings)
            if self._counter is not None:
                self._counter.update(self._format_counter(result.bars))
            if self._warning is not None:
                if result.warnings:
                    self._warning.remove_class("identity-warning-clear")
                    self._warning.add_class("identity-warning")
                    self._warning.update("⚠ " + self._cfg["name"] + ": " + "; ".join(result.warnings))
                else:
                    self._warning.remove_class("identity-warning")
                    self._warning.add_class("identity-warning-clear")
                    self._warning.update("")
            if self._phonetic is not None:
                try:
                    self._phonetic.process_text(text)
                except Exception:
                    pass


    class IdentityDashboard(App[None]):
        """Standalone preview: 5 caps, left selector, right active panel."""

        TITLE = "REST — Identity Panels"
        CSS_PATH = "identity_panels.tcss"
        BINDINGS = [
            Binding("ctrl+q", "quit", "Quit", priority=True),
            Binding("ctrl+1", "select('grey')", "Ember", priority=True),
            Binding("ctrl+2", "select('blue')", "Tide", priority=True),
            Binding("ctrl+3", "select('green')", "Cypress", priority=True),
            Binding("ctrl+4", "select('cream')", "Ize", priority=True),
            Binding("ctrl+5", "select('black')", "Nightfall", priority=True),
        ]

        def __init__(self, class_map: dict[str, dict] | None = None, **kw) -> None:
            super().__init__(**kw)
            self._class_map = class_map or load_classes()
            self._panels: dict[str, IdentityPanel] = {}
            self._active: str = "grey"
            self._list: ListView | None = None

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            with Horizontal(id="identity-root"):
                items = []
                for cap in CAP_ORDER:
                    name = self._class_map[cap]["name"]
                    items.append(ListItem(Label(f"{cap:<6} {name}"), id=f"cap-{cap}"))
                self._list = ListView(*items, id="identity-list")
                yield self._list
                with Vertical(id="panel-slot"):
                    for cap in CAP_ORDER:
                        panel = IdentityPanel(cap, self._class_map[cap], self._class_map)
                        panel.display = (cap == self._active)
                        self._panels[cap] = panel
                        yield panel
            yield Footer()

        def on_mount(self) -> None:
            if self._list is not None:
                self._list.focus()

        def action_select(self, cap: str) -> None:
            if cap not in self._panels:
                return
            for k, p in self._panels.items():
                p.display = (k == cap)
            self._active = cap
            panel = self._panels.get(cap)
            if panel is not None and panel._textarea is not None:
                panel._textarea.focus()

        def on_list_view_selected(self, event: ListView.Selected) -> None:
            iid = event.item.id or ""
            if iid.startswith("cap-"):
                self.action_select(iid[4:])


def main() -> None:
    if not _TEXTUAL:
        raise SystemExit("textual not installed")
    IdentityDashboard().run()


if __name__ == "__main__":
    main()
