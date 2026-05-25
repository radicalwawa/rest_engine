"""
REST Engine TUI — Phase 2 Step E: Modals + Interactive Rating.
3-kolonlu Textual arayuz, gercek veri akisi + 3 modal (Register, Rate, VersionPicker).

prompt_engine discovery (Step D'den):
  - Kullanilan fonksiyon: generate_beat_prompt(color, variation_type, seed, persist)
    Donus: {color, prompt_type, variation_type, style_prompt, negative_prompt, meta, prompt_id}
  - Lyrics-aware transform: LOCAL HELPER (_transform_lyrics).
  - Weirdness / Style Influence: prompt_engine donmuyor. '--' placeholder.

Step E modals:
  - RegisterMp3Modal (m): inbox'tan mp3 kayit
  - RateModal (r): en son beat'i puanla (veya belirli beat_id ile)
  - RateVersionPickerModal (R): versiyon sec, sonra RateModal ac
  Rating picker: RadioButton fallback — Textual 8.x'te custom 5-point slider
  karmasikligi RadioSet ile cozuldu.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Center
from textual.screen import ModalScreen
from textual.widgets import (
    Static, TextArea, Button, Label, Input, RadioButton, RadioSet, OptionList
)
from textual.widgets.option_list import Option
from textual import work

# db_manager ve prompt_engine importlari
sys.path.insert(0, str(Path(__file__).resolve().parent))
import db_manager as dbm
import prompt_engine as pe


# ── Sabitler ──

IDENTITY_HOTKEYS = {"1", "2", "3", "4", "5"}

IDENTITY_THEMES = {
    "green":  {"surname": "Cypress",   "accent": "#7aa861", "border": "#3d4f30"},
    "grey":   {"surname": "Ember",     "accent": "#9a9a9a", "border": "#444444"},
    "blue":   {"surname": "Tide",      "accent": "#5e8db3", "border": "#2f4a5e"},
    "cream":  {"surname": "Ize",       "accent": "#c4b08a", "border": "#5e5440"},
    "black":  {"surname": "Nightfall", "accent": "#a060c0", "border": "#3a2050"},
}

IDENTITY_ORDER = ["green", "grey", "blue", "cream", "black"]

DEFAULT_IDENTITY = "green"

RATING_FIELDS = ["rating_id", "rating_flow", "rating_beat", "rating_energy", "rating_replay"]
RATING_LABELS = ["Id", "Flow", "Beat", "Energy", "Replay"]


# ── Yardimci fonksiyonlar ──

def _transform_lyrics(color: str, raw_lyrics: str, identity_profile: dict) -> str:
    """Girdi lyrics'i [verse]/[hook] yapisal etiketleriyle sarmalar.

    Basit kural: bos satirla ayrilan bloklar sirayla [verse] / [hook] olarak
    etiketlenir (verse-hook-verse-hook dongusu). Tek blok varsa sadece [verse].
    Bu Phase 3'e kadar gecici bir placeholder'dir — akilli identity-aware
    donusum Phase 3'te yapilacak.
    """
    blocks = [b.strip() for b in raw_lyrics.strip().split("\n\n") if b.strip()]
    if not blocks:
        return ""
    tags = ["[verse]", "[hook]"]
    parts = []
    for i, block in enumerate(blocks):
        tag = tags[i % 2]
        parts.append(f"{tag}\n{block}")
    return "\n\n".join(parts)


def _copy_to_clipboard(text: str) -> bool:
    """Metni OS clipboard'a kopyalar. Basarisiz olursa False doner."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    try:
        subprocess.run(
            ["clip"],
            input=text,
            encoding="utf-8",
            shell=False,
            check=True,
            timeout=3,
        )
        return True
    except Exception:
        return False


def _rating_circles(value) -> str:
    """Rating degerini dolu/bos daire stringine cevirir."""
    if value is None:
        return "ooooo"
    v = int(value)
    return "●" * v + "○" * (5 - v)


def _format_ratings_compact(beat: dict) -> str:
    """Beat dict'inden kompakt rating stringi uretir: 4/3/5/4/3 veya --."""
    vals = [beat.get(f) for f in RATING_FIELDS]
    if any(v is None for v in vals):
        return "--"
    return "/".join(str(v) for v in vals)


def _truncate(s: str, maxlen: int = 12) -> str:
    if not s:
        return ""
    return s if len(s) <= maxlen else s[:maxlen] + "..."


def _count_fully_rated(beats: list[dict]) -> int:
    """Tum 5 rating'i dolu olan beat sayisini dondurur."""
    count = 0
    for b in beats:
        if all(b.get(f) is not None for f in RATING_FIELDS):
            count += 1
    return count


def _safe_normalize(track_name: str) -> str | None:
    """Track name'i normalize et. Hata durumunda None doner."""
    try:
        return dbm._normalize_track_name(track_name)
    except (ValueError, AttributeError):
        return None


# ── Ozel widgetlar ──

class PassthroughTextArea(TextArea):
    """1-5 tuslarini identity switch icin ust katmana ileten TextArea."""

    def check_consume_key(self, key: str, character: str | None = None) -> bool:
        if character in IDENTITY_HOTKEYS:
            return False
        return super().check_consume_key(key, character)


class IdentityList(Static):
    """Sol paneldeki kimlik listesi."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.active = DEFAULT_IDENTITY
        self.counts: dict[str, int] = {c: 0 for c in IDENTITY_ORDER}

    def update_data(self, active: str, counts: dict[str, int]) -> None:
        self.active = active
        self.counts = counts
        self.refresh()

    def render(self) -> str:
        lines = []
        for color in IDENTITY_ORDER:
            theme = IDENTITY_THEMES[color]
            prefix = " * " if color == self.active else "   "
            n = self.counts.get(color, 0)
            lines.append(f"{prefix}{theme['surname']:<12} [{n}]")
        return "\n".join(lines)


class RatingPanel(Static):
    """Sag paneldeki 5 boyutlu rating cetveli (read-only display)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.values: dict[str, int | None] = {f: None for f in RATING_FIELDS}

    def update_data(self, beat: dict | None) -> None:
        if beat:
            self.values = {f: beat.get(f) for f in RATING_FIELDS}
        else:
            self.values = {f: None for f in RATING_FIELDS}
        self.refresh()

    def render(self) -> str:
        lines = []
        for label, field in zip(RATING_LABELS, RATING_FIELDS):
            circles = _rating_circles(self.values.get(field))
            lines.append(f"  {label:<8} {circles}")
        return "\n".join(lines)


class HistoryPanel(Static):
    """Son 5 beat gecmisi."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.beats: list[dict] = []

    def update_data(self, beats: list[dict]) -> None:
        self.beats = beats[:5]
        self.refresh()

    def render(self) -> str:
        if not self.beats:
            return "(no beats yet)"
        lines = []
        for b in self.beats:
            vn = b.get("version_num", "?")
            tn = _truncate(b.get("track_name", "") or "", 12)
            ratings = _format_ratings_compact(b)
            lines.append(f"  v{vn}  {tn:<15} {ratings}")
        return "\n".join(lines)


class NotesHistory(Static):
    """Not gecmisi listesi."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.notes: list[dict] = []

    def update_data(self, notes: list[dict]) -> None:
        self.notes = notes
        self.refresh()

    def render(self) -> str:
        if not self.notes:
            return "(no notes yet)"
        lines = []
        for n in self.notes:
            ts = (n.get("created_at") or "")[:16]
            body = _truncate(n.get("body", ""), 40)
            lines.append(f"  {ts}  {body}")
        return "\n".join(lines)


class MoreOptions(Static):
    """Orta paneldeki ek secenekler."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.weirdness = "--"
        self.style_influence = "--"

    def update_data(self, weirdness: str = "--", style_influence: str = "--") -> None:
        self.weirdness = weirdness
        self.style_influence = style_influence
        self.refresh()

    def render(self) -> str:
        return (
            f"  Weirdness:        {self.weirdness}\n"
            f"  Style Influence:  {self.style_influence}"
        )


class HelpFooter(Static):
    """Alt satirda tus ipuclari."""

    DEFAULT_CSS = """
    HelpFooter {
        dock: bottom;
        height: 1;
        background: #111111;
        color: #666666;
        padding: 0 1;
    }
    """

    def render(self) -> str:
        return "1-5 identity   r rate   R pick   m mp3   ctrl+s note   q quit"


# ── Modaller ──

class RegisterMp3Modal(ModalScreen):
    """Inbox'tan mp3 kayit modali."""

    DEFAULT_CSS = """
    RegisterMp3Modal {
        align: center middle;
    }
    #register-modal-container {
        width: 60;
        height: auto;
        max-height: 18;
        border: solid #555555;
        background: #1a1a1a;
        padding: 1 2;
    }
    #register-modal-container Label {
        margin-bottom: 1;
    }
    #register-preview {
        margin: 1 0;
        color: #888888;
    }
    #register-preview-error {
        margin: 1 0;
        color: #cc4444;
    }
    .modal-btn-row {
        margin-top: 1;
        height: auto;
    }
    .modal-btn-row Button {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, color: str) -> None:
        super().__init__()
        self.color = color
        self.surname = IDENTITY_THEMES[color]["surname"]

    def compose(self) -> ComposeResult:
        with Vertical(id="register-modal-container"):
            yield Label(f"Register mp3 -- {self.surname}")
            yield Label("Track name:")
            yield Input(id="register-track-input", placeholder="track name")
            yield Static("", id="register-preview")
            with Horizontal(classes="modal-btn-row"):
                yield Button("Register", id="register-btn", disabled=True)
                yield Button("Cancel", id="register-cancel-btn")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "register-track-input":
            return
        raw = event.value
        normalized = _safe_normalize(raw) if raw.strip() else None
        preview = self.query_one("#register-preview", Static)
        btn = self.query_one("#register-btn", Button)

        if not raw.strip():
            preview.update("")
            btn.disabled = True
            return

        if normalized is None:
            preview.update("Inbox file: (invalid track name)")
            preview.styles.color = "#cc4444"
            btn.disabled = True
            return

        try:
            versions = dbm.get_beat_versions(self.color, normalized)
            next_v = len(versions) + 1
        except Exception:
            next_v = None

        v_str = f"v{next_v}" if next_v else "v--"
        preview.update(
            f"Inbox file: rest_inbox/{normalized}.mp3\n"
            f"Next version: {v_str}  (auto)"
        )
        preview.styles.color = "#888888"
        btn.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "register-cancel-btn":
            self.dismiss(None)
        elif event.button.id == "register-btn":
            self._do_register()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_enter(self) -> None:
        btn = self.query_one("#register-btn", Button)
        if not btn.disabled:
            self._do_register()

    @work(thread=True)
    def _do_register(self) -> None:
        raw = self.app.call_from_thread(
            lambda: self.query_one("#register-track-input", Input).value
        )
        try:
            result = dbm.register_beat_mp3(self.color, raw)
            tn = result["track_name"]
            vn = result["version_num"]
            color = result["color"]

            def _success():
                self.app.notify(
                    f"registered: {color} {tn} v{vn}", timeout=2
                )
                self.dismiss(result)

            self.app.call_from_thread(_success)

        except FileNotFoundError as exc:
            self.app.call_from_thread(
                self.app.notify,
                f"inbox file not found: {exc}",
                severity="error",
            )
        except Exception as exc:
            self.app.call_from_thread(
                self.app.notify,
                f"register error: {exc}",
                severity="error",
            )


class RateModal(ModalScreen):
    """Beat puanlama modali. RadioSet fallback kullaniliyor (Textual 8.x uyumu)."""

    DEFAULT_CSS = """
    RateModal {
        align: center middle;
    }
    #rate-modal-container {
        width: 60;
        height: auto;
        max-height: 30;
        border: solid #555555;
        background: #1a1a1a;
        padding: 1 2;
    }
    #rate-modal-container Label {
        margin-bottom: 1;
    }
    .rate-row {
        height: auto;
        margin-bottom: 1;
    }
    .rate-row-label {
        width: 10;
        margin-right: 1;
    }
    .rate-radio-set {
        height: auto;
        layout: horizontal;
    }
    #rate-validation-msg {
        color: #cc4444;
        margin: 1 0;
    }
    #rate-note-input {
        margin: 1 0;
    }
    .modal-btn-row {
        margin-top: 1;
        height: auto;
    }
    .modal-btn-row Button {
        margin-right: 2;
    }
    #no-beats-msg {
        margin: 2 0;
        color: #888888;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, color: str, beat_id: int | None = None) -> None:
        super().__init__()
        self.color = color
        self.target_beat_id = beat_id
        self.beat: dict | None = None
        self.rating_values: dict[str, int | None] = {f: None for f in RATING_FIELDS}

    def compose(self) -> ComposeResult:
        self.beat = self._load_beat()
        surname = IDENTITY_THEMES[self.color]["surname"]

        with Vertical(id="rate-modal-container"):
            if self.beat is None:
                yield Label(f"Rate beat -- {surname}")
                yield Static("no beats to rate", id="no-beats-msg")
                with Horizontal(classes="modal-btn-row"):
                    yield Button("Close", id="rate-cancel-btn")
                return

            vn = self.beat.get("version_num", "?")
            tn = self.beat.get("track_name", "?")
            yield Label(f"Rate beat -- {surname} v{vn} {tn}")

            for field, label in zip(RATING_FIELDS, RATING_LABELS):
                existing = self.beat.get(field)
                self.rating_values[field] = existing
                with Horizontal(classes="rate-row"):
                    yield Label(f"{label}:", classes="rate-row-label")
                    rs = RadioSet(id=f"rs-{field}", classes="rate-radio-set")
                    with rs:
                        for val in range(1, 6):
                            rb = RadioButton(str(val), id=f"rb-{field}-{val}")
                            if existing is not None and val == int(existing):
                                rb.value = True
                            yield rb

            existing_note = self.beat.get("rating_note") or ""
            yield Label("Note:")
            yield Input(
                value=existing_note,
                id="rate-note-input",
                placeholder="rating note",
            )
            yield Static("", id="rate-validation-msg")
            with Horizontal(classes="modal-btn-row"):
                yield Button("Save", id="rate-save-btn")
                yield Button("Cancel", id="rate-cancel-btn")

    def _load_beat(self) -> dict | None:
        if self.target_beat_id is not None:
            beats = dbm.get_recent_beats(self.color, limit=1000)
            for b in beats:
                if b.get("id") == self.target_beat_id:
                    return b
            return None
        beats = dbm.get_recent_beats(self.color, limit=1)
        return beats[0] if beats else None

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        rs_id = event.radio_set.id or ""
        if not rs_id.startswith("rs-"):
            return
        field = rs_id[3:]
        pressed = event.pressed
        if pressed and pressed.id:
            val = int(pressed.id.split("-")[-1])
            self.rating_values[field] = val

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rate-cancel-btn":
            self.dismiss(None)
        elif event.button.id == "rate-save-btn":
            self._do_save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_enter(self) -> None:
        if self.beat is not None:
            self._do_save()

    @work(thread=True)
    def _do_save(self) -> None:
        vals = dict(self.rating_values)
        missing = [l for f, l in zip(RATING_FIELDS, RATING_LABELS) if vals.get(f) is None]
        if missing:
            def _show_err():
                msg = self.query_one("#rate-validation-msg", Static)
                msg.update(f"all 5 ratings required (missing: {', '.join(missing)})")
            self.app.call_from_thread(_show_err)
            return

        note = self.app.call_from_thread(
            lambda: self.query_one("#rate-note-input", Input).value
        )
        beat_id = self.beat["id"]
        color = self.color
        try:
            dbm.rate_beat(
                beat_id=beat_id,
                rating_id=vals["rating_id"],
                rating_flow=vals["rating_flow"],
                rating_beat_score=vals["rating_beat"],
                rating_energy=vals["rating_energy"],
                rating_replay=vals["rating_replay"],
                rating_note=note or None,
            )
            vn = self.beat.get("version_num", "?")
            tn = self.beat.get("track_name", "?")

            def _success():
                self.app.notify(
                    f"rated: {color} v{vn} {tn}", timeout=2
                )
                self.dismiss({"rated": True})

            self.app.call_from_thread(_success)

        except Exception as exc:
            self.app.call_from_thread(
                self.app.notify,
                f"rate error: {exc}",
                severity="error",
            )


class RateVersionPickerModal(ModalScreen):
    """Versiyon secici — secilen beat icin RateModal acar."""

    DEFAULT_CSS = """
    RateVersionPickerModal {
        align: center middle;
    }
    #picker-modal-container {
        width: 65;
        height: auto;
        max-height: 28;
        border: solid #555555;
        background: #1a1a1a;
        padding: 1 2;
    }
    #picker-modal-container Label {
        margin-bottom: 1;
    }
    #picker-list {
        height: auto;
        max-height: 18;
    }
    .modal-btn-row {
        margin-top: 1;
        height: auto;
    }
    .modal-btn-row Button {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, color: str) -> None:
        super().__init__()
        self.color = color
        self.beats: list[dict] = []

    def compose(self) -> ComposeResult:
        surname = IDENTITY_THEMES[self.color]["surname"]
        self.beats = dbm.get_recent_beats(self.color, limit=20)

        with Vertical(id="picker-modal-container"):
            yield Label(f"Pick version to rate -- {surname}")

            if not self.beats:
                yield Static("(no beats yet)")
            else:
                options = []
                for b in self.beats:
                    vn = b.get("version_num", "?")
                    tn = _truncate(b.get("track_name", "") or "", 12)
                    ratings = _format_ratings_compact(b)
                    created = (b.get("created_at") or "")[:10]
                    line = f"v{vn}  {tn:<15} {ratings:<12} {created}"
                    options.append(Option(line, id=str(b["id"])))
                yield OptionList(*options, id="picker-list")

            with Horizontal(classes="modal-btn-row"):
                yield Button("Select", id="picker-select-btn",
                             disabled=not self.beats)
                yield Button("Cancel", id="picker-cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-cancel-btn":
            self.dismiss(None)
        elif event.button.id == "picker-select-btn":
            self._select_current()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_enter(self) -> None:
        if self.beats:
            self._select_current()

    def _select_current(self) -> None:
        ol = self.query_one("#picker-list", OptionList)
        idx = ol.highlighted
        if idx is not None and 0 <= idx < len(self.beats):
            beat_id = self.beats[idx]["id"]
            self.dismiss({"beat_id": beat_id})
        else:
            self.dismiss(None)


# ── Ana uygulama ──

class RestEngineApp(App):
    """REST Engine TUI — 3 kolonlu, veri bagli arayuz + modaller."""

    TITLE = "REST Engine"
    CSS = """
    Screen {
        layout: horizontal;
        background: #1a1a1a;
        color: #cccccc;
    }

    #left-col {
        width: 28%;
        min-width: 24;
        height: 100%;
        padding: 0 1;
    }

    #center-col {
        width: 44%;
        min-width: 36;
        height: 100%;
        padding: 0 1;
    }

    #right-col {
        width: 28%;
        min-width: 24;
        height: 100%;
        padding: 0 1;
    }

    .panel {
        border: solid #444444;
        padding: 1;
        margin-bottom: 1;
    }

    .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #identity-panel {
        height: auto;
        max-height: 12;
    }

    #lyrics-input-panel {
        height: 1fr;
    }

    #lyrics-input-area {
        height: 1fr;
        min-height: 4;
    }

    #rest-btn {
        width: 100%;
        margin-top: 1;
    }

    #lyrics-output-panel {
        height: 1fr;
    }

    #lyrics-output-area {
        height: 1fr;
        min-height: 4;
        background: #222222;
    }

    #styles-output-panel {
        height: auto;
        max-height: 8;
    }

    #styles-output-area {
        height: 3;
        background: #222222;
    }

    #more-options-panel {
        height: auto;
        max-height: 8;
    }

    #rating-panel {
        height: auto;
        max-height: 14;
    }

    #rating-note-area {
        height: 3;
        background: #222222;
    }

    #history-panel {
        height: auto;
        max-height: 12;
    }

    #notes-panel {
        height: 1fr;
    }

    #notes-input-area {
        height: 4;
    }

    #notes-history {
        margin-top: 1;
    }

    .copy-btn {
        dock: right;
        min-width: 8;
        height: 1;
        margin: 0;
        padding: 0 1;
    }

    #main-layout {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("1", "switch_identity('green')", "Cypress", show=False, priority=True),
        Binding("2", "switch_identity('grey')", "Ember", show=False, priority=True),
        Binding("3", "switch_identity('blue')", "Tide", show=False, priority=True),
        Binding("4", "switch_identity('cream')", "Ize", show=False, priority=True),
        Binding("5", "switch_identity('black')", "Nightfall", show=False, priority=True),
        Binding("q", "quit", "Quit", show=False),
        Binding("ctrl+s", "save_note", "Save note", show=False, priority=True),
        Binding("m", "open_register", "Register mp3", show=False),
        Binding("r", "open_rate", "Rate beat", show=False),
        Binding("R", "open_version_picker", "Pick version", show=False),
    ]

    # m, r, R: TextArea/Input focusluyken metin girisi olarak calisir.
    # Diger durumlarda modal acar. on_key ile kontrol edilir.
    _MODAL_KEYS = {"m": "open_register", "r": "open_rate", "R": "open_version_picker"}

    active_color: str = DEFAULT_IDENTITY
    lyrics_drafts: dict[str, str] = {}
    errors: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            # ── Sol kolon ──
            with Vertical(id="left-col"):
                with Vertical(id="identity-panel", classes="panel"):
                    yield Label("Identities", classes="panel-title")
                    yield IdentityList()

                with Vertical(id="lyrics-input-panel", classes="panel"):
                    yield Label("Lyrics input", classes="panel-title")
                    yield PassthroughTextArea(id="lyrics-input-area")
                    yield Button("rest", id="rest-btn", disabled=True)

            # ── Orta kolon ──
            with Vertical(id="center-col"):
                with Vertical(id="lyrics-output-panel", classes="panel"):
                    with Horizontal():
                        yield Label("Lyrics", classes="panel-title")
                        yield Button("[copy]", id="copy-lyrics-btn", classes="copy-btn",
                                     disabled=True)
                    lyrics_out = PassthroughTextArea("(no output yet)", id="lyrics-output-area")
                    lyrics_out.read_only = True
                    yield lyrics_out

                with Vertical(id="styles-output-panel", classes="panel"):
                    with Horizontal():
                        yield Label("Styles", classes="panel-title")
                        yield Button("[copy]", id="copy-styles-btn", classes="copy-btn",
                                     disabled=True)
                    styles_out = PassthroughTextArea("(no output yet)", id="styles-output-area")
                    styles_out.read_only = True
                    yield styles_out

                with Vertical(id="more-options-panel", classes="panel"):
                    yield Label("More options", classes="panel-title")
                    yield MoreOptions()

            # ── Sag kolon ──
            with Vertical(id="right-col"):
                with Vertical(id="rating-panel", classes="panel"):
                    yield Label("Rating", classes="panel-title")
                    yield RatingPanel()
                    rn = PassthroughTextArea(id="rating-note-area")
                    rn.read_only = True
                    yield rn

                with Vertical(id="history-panel", classes="panel"):
                    yield Label("History (last 5)", classes="panel-title")
                    yield HistoryPanel()

                with Vertical(id="notes-panel", classes="panel"):
                    yield Label("Notes", classes="panel-title")
                    yield PassthroughTextArea(id="notes-input-area")
                    yield NotesHistory(id="notes-history")

        yield HelpFooter()

    def on_mount(self) -> None:
        self.lyrics_drafts = {c: "" for c in IDENTITY_ORDER}
        self.errors = []
        self._apply_theme()
        self._refresh_all_panels()

    # ── Panel refresh ──

    def _refresh_all_panels(self) -> None:
        self._refresh_identity_counts()
        self._refresh_rating()
        self._refresh_history()
        self._refresh_notes()
        self._sync_lyrics_input()

    def _refresh_identity_counts(self) -> None:
        counts = {}
        for color in IDENTITY_ORDER:
            try:
                beats = dbm.get_recent_beats(color, limit=1000)
                counts[color] = _count_fully_rated(beats)
            except Exception as exc:
                self._log_error(f"identity count ({color}): {exc}")
                counts[color] = 0
        self.query_one(IdentityList).update_data(self.active_color, counts)

    def _refresh_rating(self) -> None:
        try:
            beats = dbm.get_recent_beats(self.active_color, limit=1)
            beat = beats[0] if beats else None
        except Exception as exc:
            self._log_error(f"rating refresh: {exc}")
            beat = None
        self.query_one(RatingPanel).update_data(beat)
        rn_widget = self.query_one("#rating-note-area", PassthroughTextArea)
        note_text = (beat.get("rating_note") or "(no rating note)") if beat else "(no rating note)"
        rn_widget.text = note_text

    def _refresh_history(self) -> None:
        try:
            beats = dbm.get_recent_beats(self.active_color, limit=5)
        except Exception as exc:
            self._log_error(f"history refresh: {exc}")
            beats = []
        self.query_one(HistoryPanel).update_data(beats)

    def _refresh_notes(self) -> None:
        try:
            notes = dbm.get_notes(self.active_color, limit=20)
        except Exception as exc:
            self._log_error(f"notes refresh: {exc}")
            notes = []
        self.query_one(NotesHistory).update_data(notes)

    def _sync_lyrics_input(self) -> None:
        ta = self.query_one("#lyrics-input-area", PassthroughTextArea)
        ta.text = self.lyrics_drafts.get(self.active_color, "")
        self._update_rest_button()

    def _update_rest_button(self) -> None:
        ta = self.query_one("#lyrics-input-area", PassthroughTextArea)
        btn = self.query_one("#rest-btn", Button)
        btn.disabled = not ta.text.strip()

    def _reset_middle_column(self) -> None:
        self.query_one("#lyrics-output-area", PassthroughTextArea).text = "(no output yet)"
        self.query_one("#styles-output-area", PassthroughTextArea).text = "(no output yet)"
        self.query_one("#copy-lyrics-btn", Button).disabled = True
        self.query_one("#copy-styles-btn", Button).disabled = True
        self.query_one(MoreOptions).update_data("--", "--")

    def _log_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.notify(f"db: {msg}", severity="error")

    # ── Event handlers ──

    def on_key(self, event) -> None:
        """m, r, R tuslarini TextArea/Input disinda modal acmak icin yakala."""
        focused = self.focused
        is_text_input = isinstance(focused, (TextArea, Input))
        char = event.character
        if char in self._MODAL_KEYS and not is_text_input:
            event.prevent_default()
            event.stop()
            action = self._MODAL_KEYS[char]
            getattr(self, f"action_{action}")()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "lyrics-input-area":
            self.lyrics_drafts[self.active_color] = event.text_area.text
            self._update_rest_button()

    def action_switch_identity(self, color: str) -> None:
        if color == self.active_color:
            return
        ta = self.query_one("#lyrics-input-area", PassthroughTextArea)
        self.lyrics_drafts[self.active_color] = ta.text
        self.active_color = color
        self._apply_theme()
        self._reset_middle_column()
        self._refresh_all_panels()

    def _apply_theme(self) -> None:
        theme = IDENTITY_THEMES[self.active_color]
        accent = theme["accent"]
        border_color = theme["border"]
        for panel in self.query(".panel"):
            panel.styles.border = ("solid", border_color)
        for title in self.query(".panel-title"):
            title.styles.color = accent

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rest-btn":
            self._fire_rest()
        elif event.button.id == "copy-lyrics-btn":
            text = self.query_one("#lyrics-output-area", PassthroughTextArea).text
            if _copy_to_clipboard(text):
                self.notify("lyrics copied", timeout=1)
            else:
                self.notify("clipboard unavailable", severity="warning")
        elif event.button.id == "copy-styles-btn":
            text = self.query_one("#styles-output-area", PassthroughTextArea).text
            if _copy_to_clipboard(text):
                self.notify("styles copied", timeout=1)
            else:
                self.notify("clipboard unavailable", severity="warning")

    @work(thread=True)
    def _fire_rest(self) -> None:
        color = self.active_color
        raw_lyrics = self.lyrics_drafts.get(color, "").strip()
        if not raw_lyrics:
            self.app.call_from_thread(
                self.notify, "empty lyrics", severity="warning"
            )
            return
        try:
            result = pe.generate_beat_prompt(
                color=color,
                variation_type="base",
                persist=True,
            )
            style_prompt = result["style_prompt"]
            profile = dbm.get_identity_profile(color)
            transformed = _transform_lyrics(color, raw_lyrics, profile or {})
            weirdness = "--"
            style_influence = "--"
        except Exception as exc:
            self.app.call_from_thread(
                self.notify, f"rest error: {exc}", severity="error"
            )
            self.errors.append(f"rest: {exc}")
            return

        def _update_ui():
            self.query_one("#lyrics-output-area", PassthroughTextArea).text = transformed
            self.query_one("#styles-output-area", PassthroughTextArea).text = style_prompt
            self.query_one("#copy-lyrics-btn", Button).disabled = False
            self.query_one("#copy-styles-btn", Button).disabled = False
            self.query_one(MoreOptions).update_data(weirdness, style_influence)
            self.notify("rest fired", timeout=1)

        self.app.call_from_thread(_update_ui)

    def action_save_note(self) -> None:
        ta = self.query_one("#notes-input-area", PassthroughTextArea)
        body = ta.text.strip()
        if not body:
            self.notify("empty note ignored", severity="warning")
            return
        try:
            dbm.add_note(self.active_color, body)
            ta.text = ""
            self.notify("note saved", timeout=1)
            self._refresh_notes()
        except Exception as exc:
            self._log_error(f"note save: {exc}")

    # ── Modal actions ──

    def action_open_register(self) -> None:
        self.push_screen(
            RegisterMp3Modal(self.active_color),
            callback=self._on_register_dismiss,
        )

    def _on_register_dismiss(self, result) -> None:
        if result is not None:
            self._refresh_history()
            self._refresh_identity_counts()

    def action_open_rate(self) -> None:
        self.push_screen(
            RateModal(self.active_color),
            callback=self._on_rate_dismiss,
        )

    def _on_rate_dismiss(self, result) -> None:
        if result is not None:
            self._refresh_rating()
            self._refresh_history()
            self._refresh_identity_counts()

    def action_open_version_picker(self) -> None:
        self.push_screen(
            RateVersionPickerModal(self.active_color),
            callback=self._on_picker_dismiss,
        )

    def _on_picker_dismiss(self, result) -> None:
        if result is not None and "beat_id" in result:
            self.push_screen(
                RateModal(self.active_color, beat_id=result["beat_id"]),
                callback=self._on_rate_dismiss,
            )


if __name__ == "__main__":
    RestEngineApp().run()
