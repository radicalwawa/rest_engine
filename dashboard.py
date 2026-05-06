#!/usr/bin/env python3
"""
REST ENGINE — Radical Noface TUI Dashboard
3-panel track browser with identity color system.
Data layer: DbManager (SQLite mirror of JSON source of truth).
"""

import json
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, ListItem, ListView, Log, Static

from db_manager import DbManager

# --- Paths ---
ROOT = Path(__file__).resolve().parent
VALIDATE_SCRIPT = ROOT / "python" / "validate.py"

# --- 5-Color Model ---
COLORS = {
    "grey":  {"hex": "#888888", "label": "Ember",     "emotion": "Concrete Rage"},
    "blue":  {"hex": "#0077ff", "label": "Tide",      "emotion": "Blue Sorrow"},
    "green": {"hex": "#00ff41", "label": "Cypress",   "emotion": "Saturated Growth"},
    "cream": {"hex": "#fffdd0", "label": "Ize",       "emotion": "Intimate Heat"},
    "black": {"hex": "#1a1a1a", "label": "Nightfall", "emotion": "Divine Smoke"},
}
COLOR_ORDER = ["grey", "blue", "green", "cream", "black"]


def _color_from_track_id(track_id: str) -> str:
    """radical.grey -> grey"""
    parts = track_id.split(".")
    return parts[1] if len(parts) >= 2 else "grey"


def _parse_json_field(val: str | list | None) -> list:
    """SQLite'da JSON string olarak saklanan array alanlari parse et."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _git_head() -> str:
    """Kisa git commit hash dondurur."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "-"


def _git_dirty() -> bool:
    """Calisma dizininde degisiklik var mi?"""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, timeout=2,
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


# ============================================================
# Widget: Track Browser (Sol Panel)
# ============================================================
class TrackBrowser(Vertical):
    """Sol panel — track listesi."""

    def __init__(self, tracks: list[dict]) -> None:
        super().__init__(id="left-panel")
        self._tracks = tracks

    def compose(self) -> ComposeResult:
        yield Static("TRACKS", id="track-list-title")
        yield Input(placeholder="ara...", id="search-input")
        yield ListView(*self._build_items(self._tracks), id="track-listview")

    def _build_items(self, tracks: list[dict]) -> list[ListItem]:
        """Track listesinden ListItem'lar olustur."""
        items = []
        for t in tracks:
            track_id = t.get("id", "?")
            color = _color_from_track_id(track_id)
            version = t.get("version", "-")
            theme = (t.get("theme", "") or "")[:30]
            info = COLORS.get(color, {})
            label = info.get("label", "")
            line1 = f"{track_id}  v{version}"
            line2 = f"  {label} — {theme}"
            li = ListItem(Static(f"{line1}\n{line2}"))
            li._track_data = t
            items.append(li)
        return items

    def refresh_tracks(self, tracks: list[dict]) -> None:
        """Track listesini yeniden olustur."""
        self._tracks = tracks
        lv = self.query_one("#track-listview", ListView)
        lv.clear()
        for item in self._build_items(tracks):
            lv.append(item)


# ============================================================
# Widget: Track Detail (Orta Panel)
# ============================================================
class TrackDetail(VerticalScroll):
    """Orta panel — secili track detaylari."""

    def __init__(self) -> None:
        super().__init__(id="center-panel")

    def compose(self) -> ComposeResult:
        yield Static("track sec...", id="detail-header")
        yield Static("", id="detail-identity")
        yield Static("", id="detail-techno")
        yield Static("", id="detail-binding")
        yield Static("", id="detail-calibration")
        yield Static("", id="detail-prod-dna")

    def show_detail(self, detail: dict) -> None:
        """DbManager.get_track_detail() sonucunu goster."""
        track_id = detail.get("id", "?")
        color = _color_from_track_id(track_id)
        info = COLORS.get(color, {})
        emotion = info.get("emotion", "")
        color_hex = info.get("hex", "#888888")

        self.query_one("#detail-header", Static).update(
            f"[bold {color_hex}]{track_id}[/] — {emotion}"
        )

        ident = detail.get("identity") or {}
        keywords = _parse_json_field(detail.get("keyword_vector"))
        lines = [
            "[bold]IDENTITY[/]",
            f"  theme:    {detail.get('theme', '-')}",
            f"  energy:   {detail.get('energy_profile', '-')}",
            f"  tone:     {detail.get('emotional_tone', '-')}",
            f"  focus:    {detail.get('lyrical_focus', '-')}",
            f"  keywords: {', '.join(keywords)}",
            f"  version:  {detail.get('version', '-')}",
        ]
        if ident:
            genre = _parse_json_field(ident.get("genre_stack"))
            lines.extend([
                "",
                f"  state:    {ident.get('state_label', '-')}",
                f"  genre:    {', '.join(genre)}",
                f"  bpm:      {ident.get('bpm_min', '?')}–{ident.get('bpm_max', '?')}",
                f"  groove:   {ident.get('groove', '-')}",
            ])
        self.query_one("#detail-identity", Static).update("\n".join(lines))

        self.query_one("#detail-techno", Static).update("\n".join([
            "[bold]TECHNO PROFILE[/]",
            f"  drive:    {detail.get('drive_level', '-')}",
            f"  bass:     {detail.get('bass_weight', '-')}",
            f"  texture:  {detail.get('texture_type', '-')}",
            f"  spatial:  {detail.get('spatial_depth', '-')}",
        ]))

        lb = detail.get("library_binding") or {}
        bind_lines = ["[bold]LIBRARY BINDING[/]"]
        for role in ("kick", "bass", "hat", "lead", "texture"):
            val = lb.get(role, "-")
            if val:
                bind_lines.append(f"  {role:<8} {val}")
        self.query_one("#detail-binding", Static).update("\n".join(bind_lines))

        tested = _parse_json_field(detail.get("tested_bpms"))
        drift = _parse_json_field(detail.get("drift_notes"))
        self.query_one("#detail-calibration", Static).update("\n".join([
            "[bold]CALIBRATION[/]",
            f"  tested_bpms: {tested if tested else 'none'}",
            f"  proven_bpm:  {detail.get('proven_bpm') if detail.get('proven_bpm') is not None else 'null'}",
            f"  drift_notes: {'; '.join(drift) if drift else 'none'}",
        ]))

        dna = detail.get("production_dna") or {}
        dna_widget = self.query_one("#detail-prod-dna", Static)
        if dna:
            focus = _parse_json_field(dna.get("suno_focus"))
            avoid = _parse_json_field(dna.get("suno_avoid"))
            dna_widget.update("\n".join([
                "[bold]PRODUCTION DNA[/]",
                f"  drum:     {ident.get('drum_language', '-')}",
                f"  bass:     {ident.get('bass_language', '-')}",
                f"  harmony:  {ident.get('harmony_policy', '-')}",
                f"  ambience: {ident.get('ambience_policy', '-')}",
                f"  energy:   {ident.get('energy_curve', '-')}",
                "",
                "[bold]VOCAL[/]",
                f"  anchor:    {dna.get('vocal_anchor', '-')}",
                f"  register:  {dna.get('vocal_register', '-')}",
                f"  intensity: {dna.get('vocal_intensity', '-')}",
                f"  character: {dna.get('vocal_character', '-')}",
                "",
                "[bold]FX[/]",
                f"  reverb:    {dna.get('fx_reverb', '-')}",
                f"  delay:     {dna.get('fx_delay', '-')}",
                f"  distort:   {dna.get('fx_distortion', '-')}",
                f"  bright:    {dna.get('fx_brightness', '-')}",
                f"  stereo:    {dna.get('fx_stereo_width', '-')}",
                "",
                "[bold]MIX[/]",
                f"  kick/sub:  {dna.get('mix_kick_sub', '-')}",
                f"  transient: {dna.get('mix_transients', '-')}",
                "",
                "[bold]SUNO GUIDELINES[/]",
                f"  drop:       {'yes' if dna.get('suno_allow_drop') else 'no'}",
                f"  big_reverb: {'yes' if dna.get('suno_allow_big_reverb') else 'no'}",
                f"  focus:      {', '.join(focus)}",
                f"  avoid:      {', '.join(avoid)}",
                f"  notes:      {dna.get('suno_notes', '-')}",
            ]))
        else:
            dna_widget.update("[bold]PRODUCTION DNA[/]\n  (identity bulunamadi)")


# ============================================================
# Widget: Action Console (Sag Panel)
# ============================================================
class ActionConsole(Vertical):
    """Sag panel — proje durumu, identity ozeti, notlar."""

    def __init__(self) -> None:
        super().__init__(id="right-panel")

    def compose(self) -> ComposeResult:
        yield Static("ACTION CONSOLE", id="console-title")
        yield Static("", id="console-status")
        yield Static("", id="console-identities")
        yield Static("", id="console-sdm")
        yield Static("", id="console-sound")
        yield Static("[bold]NOTES[/]", id="console-log-label")
        yield Log(highlight=False, max_lines=50, id="console-log")
        yield Input(placeholder="not yaz... (/help)", id="console-input")

    def refresh_from_db(self, db: DbManager) -> None:
        """Tum console verilerini DbManager'dan yukle."""
        self._refresh_status(db)
        self._refresh_identities(db)
        self._refresh_sdm(db)
        self._refresh_sound(db)

    def _refresh_status(self, db: DbManager) -> None:
        stats = db.get_stats()
        git_h = _git_head()
        dirty_mark = " [bold red]*dirty[/]" if _git_dirty() else ""
        self.query_one("#console-status", Static).update("\n".join([
            "[bold]PROJECT STATUS[/]",
            f"  git:      {git_h}{dirty_mark}",
            f"  db sync:  {stats.get('last_sync', '-')}",
            f"  tracks:   {stats['tracks']}/5",
            f"  works:    {stats['works']}",
            f"  assets:   {stats['sound_assets']}",
        ]))

    def _refresh_identities(self, db: DbManager) -> None:
        tracks = db.get_all_tracks()
        lines = ["[bold]5-COLOR MODEL[/]"]
        for t in tracks:
            tid = t.get("id", "?")
            color = _color_from_track_id(tid)
            info = COLORS.get(color, {})
            hex_c = info.get("hex", "#888888")
            state = t.get("state_label", "-")
            bpm = f"{t.get('bpm_min', '?')}-{t.get('bpm_max', '?')}"
            lines.append(f"  [{hex_c}]{color:<6}[/] {state:<18} {bpm}")
        self.query_one("#console-identities", Static).update("\n".join(lines))

    def _refresh_sdm(self, db: DbManager) -> None:
        widget = self.query_one("#console-sdm", Static)
        sdm = db.get_sdm_state()
        if not sdm:
            widget.update("[bold]SDM[/]\n  (veri yok)")
            return
        inv_fields = [
            ("no_engine_edits", sdm.get("inv_no_engine_edits")),
            ("no_freeze_edits", sdm.get("inv_no_freeze_edits")),
            ("no_repo_refactor", sdm.get("inv_no_repo_refactor")),
            ("one_scope_per_change", sdm.get("inv_one_scope_per_change")),
            ("json_source_of_truth", sdm.get("inv_json_source_of_truth")),
        ]
        events = sdm.get("events") or []
        last_event = events[-1] if events else {}
        lines = [
            "[bold]SDM STATE[/]",
            f"  proto:   {sdm.get('proto', '-')}",
            f"  mission: {sdm.get('mission_id', '-')} — {sdm.get('mission_title', '-')}",
            f"  status:  {sdm.get('mission_status', '-')}",
            "",
            "[bold]INVARIANTS[/]",
        ]
        for name, val in inv_fields:
            mark = "[green]ok[/]" if val else "[red]NO[/]"
            lines.append(f"  {name}: {mark}")
        if last_event:
            lines.extend([
                "",
                "[bold]LAST EVENT[/]",
                f"  scope:  {last_event.get('scope', '-')}",
                f"  result: {last_event.get('result', '-')}",
                f"  note:   {last_event.get('note', '-')}",
            ])
        widget.update("\n".join(lines))

    def _refresh_sound(self, db: DbManager) -> None:
        stats = db.get_stats()
        apc = stats.get("assets_per_color", {})
        lines = [
            "[bold]SOUND LIBRARY[/]",
            f"  total assets: {stats['sound_assets']}",
        ]
        for color in COLOR_ORDER:
            key = f"radical.{color}"
            count = apc.get(key, 0)
            hex_c = COLORS[color]["hex"]
            lines.append(f"  [{hex_c}]{color:<6}[/] {count} assets")
        self.query_one("#console-sound", Static).update("\n".join(lines))

    def console_write(self, prefix: str, text: str) -> None:
        """Console log'a mesaj yaz."""
        try:
            self.query_one("#console-log", Log).write_line(f"{prefix} {text}")
        except Exception:
            pass

    def console_clear(self) -> None:
        """Console log'u temizle."""
        try:
            self.query_one("#console-log", Log).clear()
        except Exception:
            pass


# ============================================================
# App: REST Engine Dashboard
# ============================================================
class RESTDashboardApp(App):
    """REST ENGINE — Radical Noface TUI Dashboard."""

    TITLE = "REST ENGINE — Radical Noface"

    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("tab", "focus_next", "navigate"),
        Binding("shift+tab", "focus_previous", "back"),
        Binding("r", "refresh_data", "refresh"),
        Binding("v", "run_validate", "validate"),
        Binding("c", "clear_console", "clear"),
        Binding("s", "open_search", "search"),
        Binding("escape", "close_search", "esc", show=False),
    ]

    CSS = """
    Screen {
        background: #080808;
    }
    Header {
        background: #111111;
        color: #888888;
    }
    Footer {
        background: #0e0e0e;
        color: #444444;
    }

    /* color indicator */
    #color-indicator {
        height: 1;
        background: #111111;
        color: #555555;
        padding: 0 2;
    }

    /* main 3-panel layout */
    #main-layout {
        height: 1fr;
    }

    /* left panel: track browser */
    #left-panel {
        width: 32;
        border-right: solid #222222;
        background: #0c0c0c;
    }
    #track-list-title {
        height: 1;
        padding: 0 1;
        background: #111111;
        color: #555555;
        text-style: bold;
    }
    #search-input {
        display: none;
        height: 1;
        background: #151515;
        color: #aaaaaa;
        border: none;
        padding: 0 1;
    }
    #search-input.visible {
        display: block;
    }
    #track-listview {
        height: 1fr;
        background: #0c0c0c;
    }
    #track-listview > ListItem {
        padding: 0 1;
        height: 3;
        background: #0c0c0c;
        color: #606060;
    }
    #track-listview > ListItem:hover {
        background: #151515;
    }
    #track-listview:focus > ListItem.--highlight {
        background: #1a1a1a;
        color: #aaaaaa;
    }

    /* center panel: track detail */
    #center-panel {
        width: 1fr;
        background: #0a0a0a;
        padding: 1 2;
    }
    #detail-header {
        color: #888888;
        text-style: bold;
        height: auto;
        margin-bottom: 1;
    }
    #detail-identity,
    #detail-techno,
    #detail-binding,
    #detail-calibration,
    #detail-prod-dna {
        color: #666666;
        height: auto;
        margin-bottom: 1;
    }

    /* right panel: action console */
    #right-panel {
        width: 38;
        border-left: solid #222222;
        background: #0c0c0c;
    }
    #console-title {
        color: #555555;
        text-style: bold;
        height: auto;
        padding: 1 2 0 2;
        margin-bottom: 1;
    }
    #console-status,
    #console-identities,
    #console-sdm,
    #console-sound {
        color: #555555;
        height: auto;
        padding: 0 2;
        margin-bottom: 1;
    }
    #console-log-label {
        color: #333333;
        height: 1;
        padding: 0 2;
        border-top: solid #1a1a1a;
    }
    #console-log {
        height: 1fr;
        min-height: 4;
        background: #090909;
        color: #505050;
        padding: 0 2;
    }
    #console-input {
        height: 1;
        background: #0e0e0e;
        color: #888888;
        border: none;
        padding: 0 2;
    }

    /* status bar */
    #status-bar {
        height: 1;
        background: #0e0e0e;
        color: #333333;
        padding: 0 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._db = DbManager()
        self._all_tracks: list[dict] = []
        self._search_active = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="color-indicator")
        with Horizontal(id="main-layout"):
            yield TrackBrowser([])
            yield TrackDetail()
            yield ActionConsole()
        yield Static("", id="status-bar")
        yield Footer()

    def _db_sync(self) -> None:
        """FK kisitlamalarini gecici kapatarak sync yap."""
        self._db.conn.execute("PRAGMA foreign_keys=OFF")
        self._db.sync_from_json()
        self._db.conn.execute("PRAGMA foreign_keys=ON")

    def on_mount(self) -> None:
        """Baslangicta DB sync yap ve panelleri yukle."""
        try:
            self._db.connect()
            self._db_sync()
            self._all_tracks = self._db.get_all_tracks()
            self.query_one(TrackBrowser).refresh_tracks(self._all_tracks)
            self.query_one(ActionConsole).refresh_from_db(self._db)
            self._console_sys("db sync tamamlandi.")
        except Exception as e:
            self._console_sys(f"db hatasi: {e}")

        try:
            self._update_color_indicator(None)
        except Exception:
            pass
        try:
            self._update_status_bar("hazir. /help ile komutlari gor.")
        except Exception:
            pass

    def on_unmount(self) -> None:
        """Kapanista DB baglantiyi kapat."""
        try:
            self._db.close()
        except Exception:
            pass

    # --- console helpers ---
    def _console_sys(self, text: str) -> None:
        """Console'a sistem mesaji yaz."""
        try:
            self.query_one(ActionConsole).console_write("<", text)
        except Exception:
            pass

    # --- color indicator ---
    def _update_color_indicator(self, track_id: str | None) -> None:
        indicator = self.query_one("#color-indicator", Static)
        parts = []
        for color in COLOR_ORDER:
            tid = f"radical.{color}"
            hex_c = COLORS[color]["hex"]
            if tid == track_id:
                parts.append(f"[bold {hex_c}][{color}][/]")
            else:
                parts.append(f"[{hex_c}] {color} [/]")
        indicator.update("  ".join(parts))

    def _update_status_bar(self, msg: str) -> None:
        self.query_one("#status-bar", Static).update(f"  {msg}")

    # --- track selection ---
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        track_data = getattr(event.item, "_track_data", None)
        if not track_data:
            return
        self._show_selected_track(track_data.get("id", ""))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        track_data = getattr(event.item, "_track_data", None)
        if not track_data:
            return
        self._show_selected_track(track_data.get("id", ""))

    def _show_selected_track(self, track_id: str) -> None:
        if not track_id:
            return
        try:
            detail = self._db.get_track_detail(track_id)
        except Exception:
            detail = None
        if detail:
            self.query_one(TrackDetail).show_detail(detail)
            self._update_color_indicator(track_id)
            color = _color_from_track_id(track_id)
            emotion = COLORS.get(color, {}).get("emotion", "")
            self._update_status_bar(f"{track_id} — {emotion}")
        else:
            self._update_status_bar(f"{track_id} — detay bulunamadi")

    # --- input handling ---
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "console-input":
            self._handle_console_input(event.value)
            event.input.value = ""
        elif event.input.id == "search-input":
            self._run_search(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._run_search(event.value)

    # ============================================================
    # Console input: slash commands + local notes
    # ============================================================
    def _handle_console_input(self, text: str) -> None:
        """Console input mesajini isle: slash commands veya not."""
        text = text.strip()
        if not text:
            return

        console = self.query_one(ActionConsole)

        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        # Local note — sadece log'a yaz
        console.console_write(">", text)

    def _handle_slash_command(self, text: str) -> None:
        """Slash komutlarini isle."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd == "/help":
            self._console_sys(
                "/stats — proje istatistikleri\n"
                "  /clear — log temizle\n"
                "  /help  — bu mesaj"
            )

        elif cmd == "/stats":
            try:
                stats = self._db.get_stats()
                self._console_sys(
                    f"tracks: {stats['tracks']}, works: {stats['works']}, "
                    f"assets: {stats['sound_assets']}, events: {stats['sdm_events']}"
                )
            except Exception as e:
                self._console_sys(f"stats hatasi: {e}")

        elif cmd == "/clear":
            self.query_one(ActionConsole).console_clear()
            self._console_sys("log temizlendi.")

        else:
            self._console_sys(f"bilinmeyen komut: {cmd}. /help dene.")

    # --- search ---
    def _run_search(self, query: str) -> None:
        query = query.strip()
        if not query:
            self.query_one(TrackBrowser).refresh_tracks(self._all_tracks)
            self._update_status_bar(f"arama temizlendi. {len(self._all_tracks)} track.")
            return
        try:
            results = self._db.search_tracks(query)
        except Exception:
            results = []
        self.query_one(TrackBrowser).refresh_tracks(results)
        self._update_status_bar(f"arama: '{query}' — {len(results)} sonuc")

    # --- actions ---
    def action_refresh_data(self) -> None:
        try:
            self._update_status_bar("sync calisiyor...")
            self._db_sync()
            self._all_tracks = self._db.get_all_tracks()
            self.query_one(TrackBrowser).refresh_tracks(self._all_tracks)
            self.query_one(ActionConsole).refresh_from_db(self._db)
            self._update_status_bar("veriler yenilendi.")
            self._console_sys("sync tamamlandi.")
        except Exception as e:
            self._update_status_bar(f"sync hatasi: {e}")

    def action_run_validate(self) -> None:
        self._update_status_bar("validate calisiyor...")
        try:
            r = subprocess.run(
                [sys.executable, str(VALIDATE_SCRIPT)],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                self._update_status_bar("validate: PASS")
                self._console_sys("validate: PASS")
                self.notify("PASS", severity="information", timeout=3)
            else:
                out = (r.stdout or "").strip()
                first_line = out.splitlines()[0] if out else "FAIL"
                self._update_status_bar(f"validate: FAIL — {first_line}")
                self._console_sys(f"validate: FAIL — {first_line}")
                self.notify("FAIL", severity="error", timeout=3)
        except Exception as e:
            self._update_status_bar(f"validate hatasi: {e}")

    def action_clear_console(self) -> None:
        self.query_one(ActionConsole).console_clear()
        self._console_sys("log temizlendi.")

    def action_open_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        search_input.add_class("visible")
        search_input.value = ""
        search_input.focus()
        self._search_active = True

    def action_close_search(self) -> None:
        if not self._search_active:
            return
        search_input = self.query_one("#search-input", Input)
        search_input.remove_class("visible")
        search_input.value = ""
        self._search_active = False
        self.query_one(TrackBrowser).refresh_tracks(self._all_tracks)
        self.query_one("#track-listview", ListView).focus()
        self._update_status_bar(f"arama kapatildi. {len(self._all_tracks)} track.")


def main() -> None:
    """Dashboard giris noktasi."""
    app = RESTDashboardApp()
    app.run()


if __name__ == "__main__":
    main()
