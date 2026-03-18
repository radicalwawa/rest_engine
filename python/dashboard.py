#!/usr/bin/env python3
"""
REST Engine — Dashboard. The body of REST.
"""

import json
import subprocess
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Static, TextArea, Input, Log
from textual.timer import Timer

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = ROOT / "domain"
TRACKS_DIR = ROOT / "tracks"
SOUND_MAP_PATH = DOMAIN_DIR / "sound_map.json"
IDENTITIES_PATH = DOMAIN_DIR / "album5_identities.json"
WORKS_MANIFEST = DOMAIN_DIR / "works_manifest.json"
SOUND_LIBRARY = ROOT / "knowledge" / "sound_library.json"
VALIDATE_SCRIPT = ROOT / "python" / "validate.py"
SUNO_FORMAT_PATH = DOMAIN_DIR / "suno_prompt_format.json"
SCORE_SCHEMA_PATH = DOMAIN_DIR / "score_schema.json"

COLORS = ["grey", "blue", "green", "cream", "black"]
TRACK_IDS = [f"radical.{c}" for c in COLORS]

COLOR_CHAR = {"grey": ".", "blue": "~", "green": "/", "cream": "'", "black": ":"}

EMOTION_CORE = {
    "grey": "concrete rage",
    "blue": "blue sorrow",
    "green": "saturated growth",
    "cream": "intimate heat",
    "black": "divine smoke",
}

BREATH = {
    "grey": [".", "..", "...", "....", "...", "..", "."],
    "blue": ["~", "~~", "~~~", "~~~~", "~~~", "~~", "~"],
    "green": ["/", "//", "///", "////", "///", "//", "/"],
    "cream": ["'", "''", "'''", "''''", "'''", "''", "'"],
    "black": [":", "::", ":::", "::::", ":::", "::", ":"],
}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _git_head() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout.strip()[:8]
    except Exception:
        pass
    return "-"


def _git_dirty() -> bool:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, timeout=2,
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _find_identity(track_id: str) -> dict:
    data = _load_json(IDENTITIES_PATH)
    for i in (data.get("identities") or []):
        if i.get("track_id") == track_id:
            return i
    return {}


def _read_works() -> list:
    data = _load_json(WORKS_MANIFEST)
    return data.get("works") or []


def _build_prompt(track_id: str, lyrics: str) -> str:
    identity = _find_identity(track_id)
    if not identity:
        return f"[identity not found: {track_id}]"

    sm = _load_json(SOUND_MAP_PATH)
    color = ""
    emotion = ""
    sound_class = ""
    for m in (sm.get("mappings") or []):
        if m.get("track_id") == track_id:
            color = m.get("color", "")
            sound_class = m.get("sound_class", "")
            break
    for c in (sm.get("colors") or []):
        if c.get("color") == color:
            emotion = c.get("emotion_core", "")
            break

    fmt = _load_json(SUNO_FORMAT_PATH)
    prod_key_order = fmt.get("prod_dna_key_order") or [
        "drum_language", "bass_language", "harmony_policy",
        "ambience_policy", "fx_policy", "energy_curve",
    ]

    title = f"{track_id} — {identity.get('state_label', '')}"
    bpm_feel = f"{identity.get('bpm_min', '?')}–{identity.get('bpm_max', '?')} BPM"

    key_label = {
        "drum_language": "drum", "bass_language": "bass",
        "harmony_policy": "harmony", "ambience_policy": "ambience",
        "energy_curve": "energy",
    }
    prod_parts = []
    for key in prod_key_order:
        if key == "fx_policy":
            fx = identity.get("fx_policy") or {}
            prod_parts.append("fx: " + ", ".join(f"{k}={v}" for k, v in fx.items()))
        else:
            prod_parts.append(f"{key_label.get(key, key)}: {identity.get(key, '')}")

    vd = identity.get("vocal_delivery") or {}
    vocal = f"{vd.get('character', '')} {vd.get('register', '')} register, {vd.get('anchor', '')}".strip()

    guidelines = identity.get("suno_prompt_guidelines") or {}
    focus = guidelines.get("focus") or []
    avoid = guidelines.get("avoid") or []

    lines = [
        f"TITLE: {title}",
        f"BPM_FEEL: {bpm_feel}",
        "",
        "PROD_DNA:",
        *prod_parts,
        "",
        f"VOCAL_DNA: {vocal}",
        "",
        "CONSTRAINTS:",
        f"allow_drop: {str(guidelines.get('allow_drop', False)).lower()}",
    ]
    if focus:
        lines.append("focus: " + ", ".join(focus))
    if avoid:
        lines.append("avoid: " + ", ".join(avoid))

    if lyrics.strip():
        lines.append("")
        lines.append("LYRICS:")
        lines.append(lyrics.strip())

    prompt_text = "\n".join(lines)

    payload = f"{prompt_text}\n{color}\n{emotion}\n{sound_class}"
    seed_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    lines.append("")
    lines.append(f"seed: {seed_hash[:16]}")

    return "\n".join(lines)


class RESTDashboard(App):

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("1", "color_1", "grey", priority=True),
        Binding("2", "color_2", "blue", priority=True),
        Binding("3", "color_3", "green", priority=True),
        Binding("4", "color_4", "cream", priority=True),
        Binding("5", "color_5", "black", priority=True),
        Binding("ctrl+b", "build_prompt", "build"),
        Binding("ctrl+r", "validate", "validate"),
        Binding("escape", "focus_chat", "chat"),
        Binding("tab", "cycle_focus", "tab"),
    ]

    CSS = """
    Screen {
        background: #080808;
    }
    Footer {
        background: #0a0a0a;
        color: #282828;
        height: 1;
    }

    /* --- top bar --- */
    #top-bar {
        height: 1;
        background: #0a0a0a;
        color: #303030;
        padding: 0 2;
    }
    #breath {
        height: 1;
        background: #080808;
        color: #1a1a1a;
        padding: 0 2;
        content-align: center middle;
    }

    /* --- main layout --- */
    #root-layout {
        height: 1fr;
    }

    /* --- left: identity --- */
    #left-col {
        width: 20;
        border-right: solid #111111;
        padding: 0;
        background: #090909;
    }
    #color-strip {
        color: #404040;
        padding: 1 2;
        height: auto;
    }
    #pulse {
        color: #353535;
        padding: 1 2;
        height: auto;
        border-top: solid #111111;
    }
    #works-label {
        color: #1a1a1a;
        height: 1;
        padding: 0 2;
        margin-top: 1;
        border-top: solid #111111;
    }
    #works-panel {
        color: #303030;
        padding: 0 2;
        height: auto;
        max-height: 8;
    }
    #left-log {
        height: 1fr;
        background: #080808;
        color: #1a1a1a;
        padding: 0 2;
        margin-top: 1;
        border-top: solid #0e0e0e;
    }

    /* --- center: conversation --- */
    #center-col {
        width: 1fr;
        padding: 0;
        background: #080808;
    }
    #chat-area {
        height: 1fr;
        background: #080808;
        color: #707070;
        border: none;
        padding: 1 3;
    }
    #input-bar {
        height: 3;
        padding: 0 3;
        background: #0a0a0a;
        border-top: solid #111111;
    }
    #chat-input {
        background: #0c0c0c;
        color: #909090;
        border: solid #151515;
    }

    /* --- right: material --- */
    #right-col {
        width: 34;
        border-left: solid #111111;
        padding: 0;
        background: #090909;
    }
    #lyrics-label {
        color: #1a1a1a;
        height: 1;
        padding: 0 2;
    }
    #lyrics-input {
        height: 1fr;
        background: #0a0a0a;
        color: #606060;
        border: none;
        padding: 1 2;
    }
    #prompt-label {
        color: #1a1a1a;
        height: 1;
        padding: 0 2;
        border-top: solid #111111;
    }
    #prompt-output {
        height: 1fr;
        background: #080808;
        color: #484848;
        border: none;
        padding: 1 2;
    }
    #seed-line {
        color: #151515;
        height: 1;
        padding: 0 2;
    }
    """

    TITLE = "REST"

    def compose(self) -> ComposeResult:
        yield Static("", id="top-bar")
        yield Static("", id="breath")
        with Horizontal(id="root-layout"):
            with Vertical(id="left-col"):
                yield Static("", id="color-strip")
                yield Static("", id="pulse")
                yield Static("works", id="works-label")
                yield Static("", id="works-panel")
                yield Log(highlight=False, id="left-log")

            with Vertical(id="center-col"):
                yield TextArea("", id="chat-area", read_only=True)
                with Container(id="input-bar"):
                    yield Input(placeholder="", id="chat-input")

            with Vertical(id="right-col"):
                yield Static("lyrics", id="lyrics-label")
                yield TextArea("", id="lyrics-input")
                yield Static("prompt", id="prompt-label")
                yield TextArea("", id="prompt-output", read_only=True)
                yield Static("seed: -", id="seed-line")

        yield Footer()

    def on_mount(self) -> None:
        self._active_color_idx = 0
        self._active_track = TRACK_IDS[0]
        self._chat_history: list[str] = []
        self._breath_tick = 0
        self._lyrics_snapshot = ""

        self._refresh_top_bar()
        self._refresh_color_strip()
        self._refresh_pulse()
        self._refresh_works()

        log = self.query_one("#left-log", Log)
        log.write_line(f"{_ts()} alive")
        log.write_line(f"{_ts()} {_git_head()}")

        self._chat_write("ben rest.")
        color = COLORS[self._active_color_idx]
        self._chat_write(f"{EMOTION_CORE[color]}.")
        self._chat_write("")

        self.query_one("#chat-input", Input).focus()

        self._breath_timer: Timer = self.set_interval(1.2, self._do_breath)

    # --- breath ---
    def _do_breath(self) -> None:
        color = COLORS[self._active_color_idx]
        pattern = BREATH[color]
        self._breath_tick = (self._breath_tick + 1) % len(pattern)
        breath_str = pattern[self._breath_tick]
        try:
            self.query_one("#breath", Static).update(breath_str)
        except Exception:
            pass

    # --- top bar ---
    def _refresh_top_bar(self) -> None:
        head = _git_head()
        dirty = "*" if _git_dirty() else ""
        color = COLORS[self._active_color_idx]
        bar = f"  rest  {head}{dirty}  {color}"
        try:
            self.query_one("#top-bar", Static).update(bar)
        except Exception:
            pass

    # --- color strip ---
    def _refresh_color_strip(self) -> None:
        parts = []
        for i, c in enumerate(COLORS):
            char = COLOR_CHAR[c]
            if i == self._active_color_idx:
                parts.append(f" {char} {c}")
            else:
                parts.append(f"   {c}")
        try:
            self.query_one("#color-strip", Static).update("\n".join(parts))
        except Exception:
            pass

    def _select_color(self, idx: int) -> None:
        idx = max(0, min(idx, len(COLORS) - 1))
        if idx == self._active_color_idx:
            return
        self._active_color_idx = idx
        self._active_track = TRACK_IDS[idx]
        self._breath_tick = 0
        self._refresh_color_strip()
        self._refresh_pulse()
        self._refresh_top_bar()
        color = COLORS[idx]
        log = self.query_one("#left-log", Log)
        log.write_line(f"{_ts()} {self._active_track}")
        self._chat_write(f"\n{EMOTION_CORE[color]}.")

    # --- pulse ---
    def _refresh_pulse(self) -> None:
        identity = _find_identity(self._active_track)
        color = COLORS[self._active_color_idx]
        emotion = EMOTION_CORE[color]
        genre = ", ".join(identity.get("genre_stack") or [])
        bpm = f"{identity.get('bpm_min', '?')}–{identity.get('bpm_max', '?')}"
        groove = identity.get("groove", "")
        energy = identity.get("energy_curve", "")
        lines = [emotion, "", genre, f"{bpm}  {groove}", energy]
        try:
            self.query_one("#pulse", Static).update("\n".join(lines))
        except Exception:
            pass

    # --- works ---
    def _refresh_works(self) -> None:
        works = _read_works()
        if not works:
            text = "(no works)"
        else:
            lines = []
            for w in works[:6]:
                wid = (w.get("work_id") or "")[:8]
                title = w.get("title") or "-"
                status = w.get("status") or "null"
                lines.append(f"{wid} {title} [{status}]")
            text = "\n".join(lines)
        try:
            self.query_one("#works-panel", Static).update(text)
        except Exception:
            pass

    # --- chat ---
    def _chat_write(self, text: str) -> None:
        self._chat_history.append(text)
        if len(self._chat_history) > 80:
            self._chat_history = self._chat_history[-80:]
        try:
            area = self.query_one("#chat-area", TextArea)
            area.load_text("\n".join(self._chat_history))
            area.move_cursor_relative(rows=9999, columns=0)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        self._chat_write(f"\n> {text}")

        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._handle_chat(text)

    def _handle_command(self, text: str) -> None:
        log = self.query_one("#left-log", Log)
        parts = text.split()
        cmd = parts[0].lower()

        if cmd == "/validate" or cmd == "/v":
            self._chat_write("...")
            try:
                r = subprocess.run(
                    [sys.executable, str(VALIDATE_SCRIPT)],
                    cwd=ROOT, capture_output=True, text=True, timeout=60,
                )
                result = "PASS" if r.returncode == 0 else "FAIL"
                log.write_line(f"{_ts()} validate {result}")
                self._chat_write(result)
                if r.returncode != 0:
                    for line in (r.stdout or "").strip().splitlines()[:5]:
                        self._chat_write(line)
            except Exception as e:
                self._chat_write(f"error: {e}")

        elif cmd in ("/build", "/b", "/prompt"):
            self._do_build_prompt()

        elif cmd in ("/export", "/e"):
            self._do_export_prompt()

        elif cmd == "/color" or cmd == "/c":
            if len(parts) > 1:
                arg = parts[1]
                if arg in COLORS:
                    self._select_color(COLORS.index(arg))
                elif arg.isdigit() and 1 <= int(arg) <= 5:
                    self._select_color(int(arg) - 1)
                else:
                    self._chat_write(f"  {' '.join(COLORS)}")
            else:
                self._chat_write(f"  {' '.join(COLORS)}")

        elif cmd in ("/works", "/w"):
            self._refresh_works()
            self._chat_write("works refreshed.")

        elif cmd in ("/head", "/h"):
            head = _git_head()
            dirty = " (dirty)" if _git_dirty() else ""
            self._chat_write(f"{head}{dirty}")

        elif cmd == "/clear":
            self._chat_history.clear()
            try:
                self.query_one("#chat-area", TextArea).load_text("")
            except Exception:
                pass

        elif cmd == "/save":
            self._do_save_lyrics()

        elif cmd in ("/help", "/?"):
            self._chat_write("  /build  /validate  /export  /save")
            self._chat_write("  /color  /works  /head  /clear")

        else:
            self._chat_write(f"  /?")

    def _handle_chat(self, text: str) -> None:
        color = COLORS[self._active_color_idx]
        emotion = EMOTION_CORE[color]
        log = self.query_one("#left-log", Log)

        lower = text.lower().strip()

        # check for lyrics-related intent
        if any(w in lower for w in ["lyrics", "soz", "söz", "yaz"]):
            lyrics = self.query_one("#lyrics-input", TextArea).text.strip()
            if lyrics:
                line_count = len(lyrics.splitlines())
                self._chat_write(f"lyrics: {line_count} satir. /build ile baglayabilirim.")
            else:
                self._chat_write("lyrics bos. sag panele yaz.")
            return

        if any(w in lower for w in ["prompt", "build", "uret", "üret"]):
            self._do_build_prompt()
            return

        if any(w in lower for w in ["validate", "kontrol", "check"]):
            self._handle_command("/validate")
            return

        # free conversation
        word_count = len(text.split())
        log.write_line(f"{_ts()} chat {word_count}w")

        if word_count <= 2:
            self._chat_write(f"  {emotion}.")
        elif word_count <= 8:
            self._chat_write(f"  duydum.")
        else:
            self._chat_write(f"  duydum. {emotion} olarak tutuyorum.")
            lyrics = self.query_one("#lyrics-input", TextArea).text.strip()
            if not lyrics:
                self._chat_write("  sozlerin varsa sag panele koy.")

    def _do_build_prompt(self) -> None:
        log = self.query_one("#left-log", Log)
        lyrics = self.query_one("#lyrics-input", TextArea).text.strip()
        prompt_text = _build_prompt(self._active_track, lyrics)

        try:
            self.query_one("#prompt-output", TextArea).load_text(prompt_text)
        except Exception:
            pass

        log.write_line(f"{_ts()} build {self._active_track}")

        lines = prompt_text.strip().splitlines()
        seed_line = lines[-1] if lines else ""
        try:
            if seed_line.startswith("seed:"):
                self.query_one("#seed-line", Static).update(seed_line)
            else:
                self.query_one("#seed-line", Static).update("seed: -")
        except Exception:
            pass

        color = COLORS[self._active_color_idx]
        if lyrics:
            n = len(lyrics.splitlines())
            self._chat_write(f"  {self._active_track}. {n} satir. {EMOTION_CORE[color]}.")
        else:
            self._chat_write(f"  {self._active_track}. sozler bos.")

    def _do_export_prompt(self) -> None:
        log = self.query_one("#left-log", Log)
        prompt_text = self.query_one("#prompt-output", TextArea).text.strip()
        if not prompt_text:
            self._chat_write("  once /build yap.")
            return

        out_dir = ROOT / "python" / "out" / "prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{self._active_track}__{ts}.txt"
        out_path.write_text(prompt_text, encoding="utf-8")

        rel = out_path.relative_to(ROOT)
        log.write_line(f"{_ts()} export {rel}")
        self._chat_write(f"  {rel}")

    def _do_save_lyrics(self) -> None:
        log = self.query_one("#left-log", Log)
        lyrics = self.query_one("#lyrics-input", TextArea).text.strip()
        if not lyrics:
            self._chat_write("  lyrics bos.")
            return

        out_dir = ROOT / "python" / "out" / "lyrics"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{self._active_track}__{ts}.txt"
        out_path.write_text(lyrics, encoding="utf-8")

        rel = out_path.relative_to(ROOT)
        log.write_line(f"{_ts()} save lyrics {rel}")
        self._chat_write(f"  {rel}")

    # --- key bindings ---
    def action_color_1(self) -> None:
        self._select_color(0)

    def action_color_2(self) -> None:
        self._select_color(1)

    def action_color_3(self) -> None:
        self._select_color(2)

    def action_color_4(self) -> None:
        self._select_color(3)

    def action_color_5(self) -> None:
        self._select_color(4)

    def action_build_prompt(self) -> None:
        self._do_build_prompt()

    def action_validate(self) -> None:
        self._handle_command("/validate")

    def action_focus_chat(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def action_cycle_focus(self) -> None:
        focused = self.focused
        chat_input = self.query_one("#chat-input", Input)
        lyrics_input = self.query_one("#lyrics-input", TextArea)
        if focused == chat_input:
            lyrics_input.focus()
        else:
            chat_input.focus()


def main() -> None:
    app = RESTDashboard()
    app.run()


if __name__ == "__main__":
    main()
