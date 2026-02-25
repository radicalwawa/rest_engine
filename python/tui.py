#!/usr/bin/env python3
# REST Engine — Phase 1 deterministic TUI (read-only). Scope: python/ only.

import json
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, ListItem, ListView, Static

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = ROOT / "domain"
WORKS_MANIFEST = DOMAIN_DIR / "works_manifest.json"
VALIDATE_SCRIPT = ROOT / "python" / "validate.py"


def _read_works_manifest() -> list:
    if not WORKS_MANIFEST.exists():
        return []
    with open(WORKS_MANIFEST, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("works") or []


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

    def __init__(self, work: dict | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._work = work

    def set_work(self, work: dict | None) -> None:
        self._work = work
        self._refresh()

    def _refresh(self) -> None:
        if self._work is None:
            self.update("(no work selected)")
            return
        w = self._work

        def _v(k: str) -> str:
            x = w.get(k)
            return "null" if x is None else str(x)

        lines = [
            f"track_id: {_v('track_id')}",
            f"status: {_v('status')}",
            f"prompt_version: {_v('prompt_version')}",
            f"suggestion_hash: {_v('suggestion_hash')}",
            f"seed_hash_hex: {_v('seed_hash_hex')}",
        ]
        self.update("\n".join(lines))

    def on_mount(self) -> None:
        self._refresh()


class RestTui(App[None]):
    TITLE = "REST — Radical Noface Structural Engine"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "validate", "Validate"),
        Binding("v", "git_info", "Git"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._works = _read_works_manifest()
        self._work_list: ListView | None = None
        self._detail: WorkDetail | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            self._work_list = WorkList(self._works, id="work-list")
            yield self._work_list
            self._detail = WorkDetail(id="work-detail")
            yield self._detail
        yield Footer()

    def on_mount(self) -> None:
        if self._work_list and self._works:
            self._work_list.focus()
        if self._detail and self._works:
            self._detail.set_work(self._works[0])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._detail is not None and event.item is not None:
            self._detail.set_work(event.item.value)

    def action_validate(self) -> None:
        try:
            result = subprocess.run(
                [sys.executable, str(VALIDATE_SCRIPT)],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=60,
            )
        except Exception:
            result = None
        if result is not None and result.returncode == 0:
            self.notify("PASS", severity="information", timeout=3)
            self.query_one(Footer).update("Validate: PASS")
        else:
            self.notify("FAIL", severity="error", timeout=3)
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
