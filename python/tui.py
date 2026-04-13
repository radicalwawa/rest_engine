#!/usr/bin/env python3
# REST Engine — Phase 3 lifecycle visualization and state coloring. Scope: python/ only.

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, ListItem, ListView, Static

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = ROOT / "domain"
WORKS_MANIFEST = DOMAIN_DIR / "works_manifest.json"
VALIDATE_SCRIPT = ROOT / "python" / "validate.py"
UI_SCRIPT = ROOT / "python" / "ui.py"
SUNO_EXPORT_SCRIPT = ROOT / "python" / "suno_export.py"
SUGGESTIONS_DIR = ROOT / "python" / "out" / "suggestions"
SUNO_OUT_DIR = ROOT / "python" / "out" / "suno"

STATUS_CLASS = {
    None: "status-grey",
    "null": "status-grey",
    "prompt_generated": "status-yellow",
    "generated": "status-blue",
    "scored": "status-magenta",
    "best": "status-green",
}

LIFECYCLE_ORDER = [None, "prompt_generated", "generated", "scored", "best"]


def _transition_allowed(current: str | None, target: str) -> bool:
    if current is None or current == "null":
        cur_idx = 0
    elif current in LIFECYCLE_ORDER:
        cur_idx = LIFECYCLE_ORDER.index(current)
    else:
        return False
    if target not in LIFECYCLE_ORDER:
        return False
    target_idx = LIFECYCLE_ORDER.index(target)
    return target_idx == cur_idx + 1


def _read_works_manifest() -> list:
    if not WORKS_MANIFEST.exists():
        return []
    with open(WORKS_MANIFEST, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("works") or []


def _status_class(work: dict) -> str:
    s = work.get("status")
    if s is None:
        return STATUS_CLASS.get(None, "status-grey")
    return STATUS_CLASS.get(s, "status-grey")


class LogPanel(Static):
    BORDER_TITLE = "Log"
    _MAX_LINES = 100

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
            cls = _status_class(w)
            yield ListItem(
                Static(f"{work_id}  {title}", shrink=True),
                value=w,
                classes=cls,
            )

    def refresh_works(self, works: list) -> None:
        self._works = works
        self.remove_children()
        for w in works:
            work_id = w.get("work_id") or ""
            title = w.get("title") or work_id
            cls = _status_class(w)
            self.mount(
                ListItem(
                    Static(f"{work_id}  {title}", shrink=True),
                    value=w,
                    classes=cls,
                )
            )


class WorkDetail(Static):
    BORDER_TITLE = "WORK LIFECYCLE"

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

    def _v(self, w: dict, k: str) -> str:
        x = w.get(k)
        return "null" if x is None else str(x)

    def _structural_check(self, w: dict) -> tuple[list[str], bool]:
        lines = []
        ok = True
        track_id = w.get("track_id") or ""
        status = w.get("status")
        status_ge_prompt = status in ("prompt_generated", "generated", "scored", "best")
        if w.get("suggestion_hash") is not None and w.get("suggestion_hash") != "":
            lines.append("suggestion_hash ✔")
        else:
            lines.append("suggestion_hash ❌")
            ok = False
        if w.get("seed_hash_hex") is not None and w.get("seed_hash_hex") != "":
            lines.append("seed_hash_hex ✔")
        else:
            lines.append("seed_hash_hex ❌")
            ok = False
        if w.get("prompt_version") is not None and w.get("prompt_version") != "":
            lines.append("prompt_version ✔")
        else:
            lines.append("prompt_version ❌")
            ok = False
        if status_ge_prompt:
            if w.get("export_path") is not None and w.get("export_path") != "":
                lines.append("export_path ✔")
            else:
                lines.append("export_path ❌")
                ok = False
        else:
            lines.append("export_path (n/a)")
        suggestion_path = SUGGESTIONS_DIR / f"{track_id}.suggestion.json"
        if suggestion_path.exists():
            lines.append("suggestion file ✔")
        else:
            lines.append("suggestion file ❌")
            ok = False
        return lines, ok

    def _refresh(self) -> None:
        if self._work is None:
            self.update("(no work selected)")
            return
        w = self._work
        export_path = w.get("export_path")
        if export_path is None:
            export_path = "null"
        else:
            export_path = str(export_path)
        lines = []
        if self._best_work_id and w.get("work_id") == self._best_work_id:
            lines.append("★ BEST")
        lines.extend([
            f"work_id: {self._v(w, 'work_id')}",
            f"track_id: {self._v(w, 'track_id')}",
            f"prompt_version: {self._v(w, 'prompt_version')}",
            f"suggestion_hash: {self._v(w, 'suggestion_hash')}",
            f"seed_hash_hex: {self._v(w, 'seed_hash_hex')}",
            f"status: {self._v(w, 'status')}",
            f"export_path: {export_path}",
        ])
        check_lines, all_ok = self._structural_check(w)
        lines.append("")
        lines.append("STRUCTURAL CHECK")
        lines.extend(check_lines)
        if all_ok:
            lines.append("✔ STRUCTURE OK")
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
    CSS_PATH = "tui.css"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "work_create", "Work create"),
        Binding("e", "export_prompt", "Export prompt"),
        Binding("g", "generate", "Batch export all"),
        Binding("l", "link", "Link work"),
        Binding("m", "mark_generated", "Mark generated"),
        Binding("k", "mark_scored", "Mark scored"),
        Binding("B", "mark_best_status", "Mark best status"),
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
            with ScrollableContainer(id="log-container", height=8):
                self._log_panel = LogPanel(id="log-panel")
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

    def _refresh_works_list(self) -> None:
        self._works = _read_works_manifest()
        if self._work_list is not None:
            self._work_list.refresh_works(self._works)
        if self._works and self._selected_work:
            wid = self._selected_work.get("work_id")
            self._selected_work = next((w for w in self._works if w.get("work_id") == wid), self._works[0])
        elif self._works:
            self._selected_work = self._works[0]
        else:
            self._selected_work = None
        if self._detail is not None:
            self._detail.set_work(self._selected_work)
            self._detail.set_best_work_id(self._best_work_id)

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
                    self._refresh_works_list()
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
            self._refresh_works_list()
        except Exception as e:
            self._log("", str(e))

    def action_generate(self) -> None:
        """Batch export: generate v0/v1/v2 for all 5 tracks."""
        track_ids = [
            "radical.grey", "radical.blue", "radical.green",
            "radical.cream", "radical.black",
        ]
        variations = ["v0", "v1", "v2"]
        total = 0
        errors = 0
        for tid in track_ids:
            for var in variations:
                try:
                    r = subprocess.run(
                        [
                            sys.executable,
                            str(SUNO_EXPORT_SCRIPT),
                            "--track_id", tid,
                            "--variation", var,
                        ],
                        capture_output=True,
                        text=True,
                        cwd=ROOT,
                        timeout=30,
                    )
                    if r.returncode == 0:
                        total += 1
                    else:
                        errors += 1
                        self._log("", r.stderr or f"FAIL: {tid}/{var}")
                except Exception as e:
                    errors += 1
                    self._log("", str(e))
        self._log(f"Batch export: {total} ok, {errors} errors (5 tracks x 3 variations)", "")
        self._refresh_works_list()

    def action_link(self) -> None:
        try:
            r = subprocess.run(
                [sys.executable, str(UI_SCRIPT), "--help"],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=10,
            )
            out = (r.stdout or "") + (r.stderr or "")
            if "work-update" not in out:
                self._log("", "MISSING COMMAND: work-update")
                return
        except Exception as e:
            self._log("", str(e))
            return
        if not self._selected_work:
            self._log("", "No work selected")
            return
        work_id = self._selected_work.get("work_id") or ""
        track_id = self._selected_work.get("track_id") or ""
        if not track_id:
            self._log("", "No track_id")
            return
        suggestion_path = SUGGESTIONS_DIR / f"{track_id}.suggestion.json"
        if not suggestion_path.exists():
            self._log("", f"suggestion file not found: {suggestion_path}")
            return
        with open(suggestion_path, encoding="utf-8") as f:
            suggestion_data = json.load(f)
        suggestion_hash = suggestion_data.get("suggestion_hash")
        if suggestion_hash is None or suggestion_hash == "":
            suggestion_hash = hashlib.sha256(
                json.dumps(suggestion_data, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
        resolved = suggestion_data.get("resolved") or {}
        variant = resolved.get("variant") or {}
        seed_hash_hex = variant.get("seed_hash_hex") or ""
        if not seed_hash_hex:
            self._log("", "seed_hash_hex not found in suggestion")
            return
        export_path = SUNO_OUT_DIR / f"{track_id}__v0__suno_prompt.txt"
        if not export_path.exists():
            self._log("", f"export_path not found: {export_path}")
            return
        export_path_str = str(export_path.relative_to(ROOT))
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    str(UI_SCRIPT),
                    "work-update",
                    "--work_id", work_id,
                    "--prompt_version", "v0",
                    "--status", "prompt_generated",
                    "--suggestion_hash", suggestion_hash,
                    "--seed_hash_hex", seed_hash_hex,
                    "--export_path", export_path_str,
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=30,
            )
            self._log(r.stdout or "", r.stderr or "")
            if r.returncode == 0:
                self._refresh_works_list()
        except Exception as e:
            self._log("", str(e))

    def _run_work_update(self, status: str) -> None:
        if not self._selected_work:
            self._log("", "No work selected")
            return
        work_id = self._selected_work.get("work_id") or ""
        if not work_id:
            self._log("", "No work_id")
            return
        current = self._selected_work.get("status")
        if not _transition_allowed(current, status):
            self._log("", "INVALID TRANSITION")
            return
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    str(UI_SCRIPT),
                    "work-update",
                    "--work_id", work_id,
                    "--status", status,
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=30,
            )
            self._log(r.stdout or "", r.stderr or "")
            self._refresh_works_list()
        except Exception as e:
            self._log("", str(e))

    def action_mark_generated(self) -> None:
        self._run_work_update("generated")

    def action_mark_scored(self) -> None:
        self._run_work_update("scored")

    def action_mark_best_status(self) -> None:
        self._run_work_update("best")

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
            self._refresh_works_list()
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
