#!/usr/bin/env python3
# REST Engine — Phase 2 action layer. Scope: python/ only.

import json
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, ListItem, ListView, Static

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = ROOT / "domain"
WORKS_MANIFEST = DOMAIN_DIR / "works_manifest.json"
VALIDATE_SCRIPT = ROOT / "python" / "validate.py"
UI_SCRIPT = ROOT / "python" / "ui.py"
SUNO_EXPORT_SCRIPT = ROOT / "python" / "suno_export.py"
SUGGESTIONS_DIR = ROOT / "python" / "out" / "suggestions"


def _read_works_manifest() -> list:
    if not WORKS_MANIFEST.exists():
        return []
    with open(WORKS_MANIFEST, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("works") or []


class LogPanel(Static):
    BORDER_TITLE = "Log"
    _MAX_LINES = 50

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._lines: list[str] = []

    def append_log(self, text: str) -> None:
        self._lines.append(text.strip() if text else "(no output)")
        if len(self._lines) > self._MAX_LINES:
            self._lines = self._lines[-self._MAX_LINES:]
        self.update("\n".join(self._lines))


class WorkList(ListView):
    BORDER_TITLE = "Works"

    def __init__(self, works: list, **kwargs) -> None:
        super().__init__(**kwargs)
        self._works = works

    def compose(self) -> ComposeResult:
        for w in self._works:
            work_id = w.get("work_id") or ""
            title = w.get("title") or work_id
            yield ListItem(Static(f"{work_id}  {title}", shrink=True), value=w)


class WorkDetail(Static):
    BORDER_TITLE = "Work details"

    def __init__(self, work: dict | None = None, best_work_id: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._work = work
        self._best_work_id = best_work_id

    def set_work(self, work: dict | None) -> None:
        self._work = work
        self._refresh()

    def set_best_work_id(self, best_work_id: str | None) -> None:
        self._best_work_id = best_work_id
        self._refresh()

    def set_suggestion_content(self, text: str) -> None:
        self.update(text)

    def _refresh(self) -> None:
        if self._work is None:
            self.update("(no work selected)")
            return
        w = self._work

        def _v(k: str) -> str:
            x = w.get(k)
            return "null" if x is None else str(x)

        lines = []
        if self._best_work_id and w.get("work_id") == self._best_work_id:
            lines.append("★ BEST")
        lines.extend([
            f"track_id: {_v('track_id')}",
            f"status: {_v('status')}",
            f"prompt_version: {_v('prompt_version')}",
            f"suggestion_hash: {_v('suggestion_hash')}",
            f"seed_hash_hex: {_v('seed_hash_hex')}",
        ])
        self.update("\n".join(lines))

    def on_mount(self) -> None:
        self._refresh()


class WorkCreateScreen(ModalScreen[tuple[str, str, str]]):
    def __init__(self, track_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._track_id = track_id

    def compose(self) -> ComposeResult:
        yield Static("work-create (inline)")
        yield Input(placeholder="series", id="input-series")
        yield Input(placeholder="title", id="input-title")
        yield Input(placeholder="volume", id="input-volume")
        yield Button("Create", variant="primary", id="btn-create")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-create":
            return
        series = self.query_one("#input-series", Input).value.strip()
        title = self.query_one("#input-title", Input).value.strip()
        volume = self.query_one("#input-volume", Input).value.strip()
        self.dismiss((series, title, volume))


class RestTui(App[None]):
    TITLE = "REST — Radical Noface Structural Engine"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "work_create", "Work create"),
        Binding("e", "export_prompt", "Export prompt"),
        Binding("s", "show_suggestion", "Suggestion JSON"),
        Binding("b", "mark_best", "Mark best"),
        Binding("r", "validate", "Validate"),
        Binding("v", "git_info", "Git"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._works = _read_works_manifest()
        self._work_list: ListView | None = None
        self._detail: WorkDetail | None = None
        self._log_panel: LogPanel | None = None
        self._selected_work: dict | None = None
        self._best_work_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            with Horizontal():
                self._work_list = WorkList(self._works, id="work-list")
                yield self._work_list
                self._detail = WorkDetail(id="work-detail", best_work_id=self._best_work_id)
                yield self._detail
            self._log_panel = LogPanel(id="log-panel", height=8)
            yield self._log_panel
        yield Footer()

    def _log(self, out: str, err: str) -> None:
        if self._log_panel is None:
            return
        parts = []
        if out:
            parts.append(out.strip())
        if err:
            parts.append(err.strip())
        self._log_panel.append_log("\n".join(parts) if parts else "(no output)")

    def on_mount(self) -> None:
        if self._work_list and self._works:
            self._work_list.focus()
        if self._detail and self._works:
            self._detail.set_work(self._works[0])
            self._selected_work = self._works[0]
        if self._detail:
            self._detail.set_best_work_id(self._best_work_id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None:
            self._selected_work = event.item.value
            if self._detail is not None:
                self._detail.set_work(event.item.value)
                self._detail.set_best_work_id(self._best_work_id)

    def action_work_create(self) -> None:
        if not self._selected_work:
            self._log("", "No work selected")
            return
        track_id = self._selected_work.get("track_id") or ""
        if not track_id:
            self._log("", "No track_id")
            return

        def on_done(result: tuple[str, str, str]) -> None:
            series, title, volume = result
            try:
                r = subprocess.run(
                    [
                        sys.executable,
                        str(UI_SCRIPT),
                        "work-create",
                        "--track_id", track_id,
                        "--series", series,
                        "--title", title,
                        "--volume", volume,
                    ],
                    capture_output=True,
                    text=True,
                    cwd=ROOT,
                    timeout=30,
                )
                self._log(r.stdout or "", r.stderr or "")
                if r.returncode == 0:
                    self._works = _read_works_manifest()
            except Exception as e:
                self._log("", str(e))

        self.push_screen(WorkCreateScreen(track_id), on_done)

    def action_export_prompt(self) -> None:
        if not self._selected_work:
            self._log("", "No work selected")
            return
        track_id = self._selected_work.get("track_id") or ""
        if not track_id:
            self._log("", "No track_id")
            return
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    str(SUNO_EXPORT_SCRIPT),
                    "--track_id", track_id,
                    "--variation", "v0",
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=30,
            )
            self._log(r.stdout or "", r.stderr or "")
        except Exception as e:
            self._log("", str(e))

    def action_show_suggestion(self) -> None:
        if not self._selected_work or self._detail is None:
            return
        track_id = self._selected_work.get("track_id") or ""
        path = SUGGESTIONS_DIR / f"{track_id}.suggestion.json"
        if not path.exists():
            self._detail.set_suggestion_content(f"(file not found: {path})")
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._detail.set_suggestion_content(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            self._detail.set_suggestion_content(str(e))

    def action_mark_best(self) -> None:
        if not self._selected_work:
            return
        self._best_work_id = self._selected_work.get("work_id")
        if self._detail is not None:
            self._detail.set_best_work_id(self._best_work_id)
            self._detail.set_work(self._selected_work)

    def action_validate(self) -> None:
        try:
            result = subprocess.run(
                [sys.executable, str(VALIDATE_SCRIPT)],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=60,
            )
            self._log(result.stdout or "", result.stderr or "")
            if result.returncode == 0:
                self.notify("PASS", severity="information", timeout=3)
                self.query_one(Footer).update("Validate: PASS")
            else:
                self.notify("FAIL", severity="error", timeout=3)
                self.query_one(Footer).update("Validate: FAIL")
        except Exception as e:
            self._log("", str(e))
            self.query_one(Footer).update("Validate: FAIL")

    def action_git_info(self) -> None:
        branch = ""
        rev = ""
        try:
            b = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=5,
            )
            if b.returncode == 0 and b.stdout:
                branch = b.stdout.strip()
            h = subprocess.run(
                ["git", "log", "-1", "--pretty=%h"],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=5,
            )
            if h.returncode == 0 and h.stdout:
                rev = h.stdout.strip()
        except Exception:
            pass
        self.query_one(Footer).update(f"branch: {branch}  commit: {rev}")
        self.notify(f"{branch} @ {rev}", severity="information", timeout=2)


def main() -> None:
    app = RestTui()
    app.run()


if __name__ == "__main__":
    main()
