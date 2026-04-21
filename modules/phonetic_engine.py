"""Phonetic learning loop for lyrics input.

Detects foreign (non-Turkish) tokens as they are typed, queries the Claude API
for a Turkish phonetic spelling (as Suno AI would read it), prompts the user
for inline confirmation, and persists approved mappings to
``data/phonetic_dict.json``.

SDM contract:
- Engine edits yok. Freeze edits yok. Drift yok.
- Sadece ``data/phonetic_dict.json`` yazılabilir.
- JSON source of truth.
"""

from __future__ import annotations

import json
import os
import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
DICT_PATH = ROOT / "data" / "phonetic_dict.json"

TURKISH_CHARS = set("çÇğĞıİöÖşŞüÜ")

SYSTEM_PROMPT = (
    "Return only the Turkish phonetic spelling of this word as Suno AI "
    "would read it. One word in, one word out. No explanation."
)

_PUNCT_STRIP = string.punctuation + "…—–"


def _strip_token(raw: str) -> str:
    return raw.strip().strip(_PUNCT_STRIP)


def tokenize(text: str) -> list[str]:
    """Split text into cleaned tokens. Punctuation soyulur."""
    if not text:
        return []
    out: list[str] = []
    for raw in re.split(r"\s+", text):
        tok = _strip_token(raw)
        if tok:
            out.append(tok)
    return out


def is_foreign_candidate(token: str) -> bool:
    """Foreign detection rules.

    - Türkçe karakter içeren token atlanır (yerli sayılır).
    - Büyük harfle başlayanlar atlanır (özel isim).
    - Rakam içerenler atlanır.
    - Tek karakterli tokenlar atlanır.
    """
    if not token or len(token) < 2:
        return False
    if any(ch.isdigit() for ch in token):
        return False
    if token[0].isupper():
        return False
    if any(ch in TURKISH_CHARS for ch in token):
        return False
    # must contain at least one alphabetic character
    if not any(ch.isalpha() for ch in token):
        return False
    return True


def load_dict(path: Path = DICT_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {str(k).lower(): str(v) for k, v in data.items()}


def save_dict(d: dict[str, str], path: Path = DICT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {k: d[k] for k in sorted(d.keys())}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")


def suggest_phonetic(word: str, *, client: object | None = None, model: str | None = None) -> str | None:
    """Ask Claude API for the Turkish phonetic spelling of ``word``.

    Returns ``None`` if the API or SDK is unavailable. The dashboard is
    expected to have the Claude API configured; no new key is required.
    """
    try:
        if client is None:
            try:
                import anthropic  # type: ignore
            except ImportError:
                return None
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            client = anthropic.Anthropic(api_key=api_key)
        model_id = model or os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-7"
        resp = client.messages.create(  # type: ignore[attr-defined]
            model=model_id,
            max_tokens=32,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": word}],
        )
        parts = getattr(resp, "content", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                cleaned = _strip_token(text.split()[0]) if text.split() else ""
                return cleaned.lower() or None
        return None
    except Exception:
        return None


@dataclass
class Candidate:
    word: str
    suggestion: str | None


@dataclass
class PhoneticEngine:
    """Stateful phonetic learning loop.

    Hookable into a dashboard event loop. ``process_text`` is called on every
    lyrics textarea change; unknown foreign tokens are returned as
    ``Candidate`` objects for inline confirmation. Known tokens yield silent
    substitutions in the returned ``applied`` mapping.
    """

    dict_path: Path = DICT_PATH
    suggester: Callable[[str], str | None] = field(default=suggest_phonetic)
    _dict: dict[str, str] = field(default_factory=dict)
    _seen_candidates: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._dict = load_dict(self.dict_path)

    # ------------------------------------------------------------------ state
    def reload(self) -> None:
        self._dict = load_dict(self.dict_path)

    def known(self, word: str) -> str | None:
        return self._dict.get(word.lower())

    def snapshot(self) -> dict[str, str]:
        return dict(self._dict)

    # ---------------------------------------------------------------- hooks
    def process_text(self, text: str) -> tuple[dict[str, str], list[Candidate]]:
        """Scan ``text`` for tokens.

        Returns ``(applied, candidates)``:
        - ``applied``: lowercase foreign word -> phonetic spelling, for tokens
          already in the dict (silent apply).
        - ``candidates``: tokens not yet in the dict that require confirmation.
          Each candidate is emitted only once per engine lifetime to avoid
          spamming the textarea change loop.
        """
        applied: dict[str, str] = {}
        candidates: list[Candidate] = []
        for raw in tokenize(text):
            if not is_foreign_candidate(raw):
                continue
            key = raw.lower()
            hit = self._dict.get(key)
            if hit is not None:
                applied[key] = hit
                continue
            if key in self._seen_candidates:
                continue
            self._seen_candidates.add(key)
            suggestion = None
            try:
                suggestion = self.suggester(key)
            except Exception:
                suggestion = None
            candidates.append(Candidate(word=key, suggestion=suggestion))
        return applied, candidates

    # ---------------------------------------------------------- persistence
    def confirm(self, word: str, phonetic: str) -> None:
        """Approve a suggestion. Writes to ``phonetic_dict.json``."""
        key = word.lower().strip()
        val = phonetic.strip().lower()
        if not key or not val:
            return
        self._dict[key] = val
        save_dict(self._dict, self.dict_path)

    def reject(self, word: str) -> None:
        """Drop a candidate without persisting anything.

        The rejected token stays in ``_seen_candidates`` so the prompt is not
        re-triggered on the same typing session; the caller may ask the user
        for a manual spelling and then call :meth:`confirm`.
        """
        # no-op for dict; session-level suppression only.
        self._seen_candidates.add(word.lower())

    def override(self, word: str, manual: str) -> None:
        """User-provided manual spelling after a reject."""
        self.confirm(word, manual)


# --------------------------------------------------------------------- inline prompt
PromptFn = Callable[[str, str | None], tuple[bool, str | None]]


def default_inline_prompt(word: str, suggestion: str | None) -> tuple[bool, str | None]:
    """Blocking CLI prompt: ``[cash → keş? (y/n)]``.

    Returns ``(approved, value)`` where ``value`` is the final phonetic to
    store. On ``n``, the user is asked for a manual spelling; empty input
    means reject outright.
    """
    sug = suggestion or "?"
    try:
        ans = input(f"[{word} → {sug}? (y/n)] ").strip().lower()
    except EOFError:
        return False, None
    if ans == "y" and suggestion:
        return True, suggestion
    if ans == "n" or not suggestion:
        try:
            manual = input(f"manual phonetic for {word} (blank to skip): ").strip().lower()
        except EOFError:
            return False, None
        if manual:
            return True, manual
        return False, None
    return False, None


def run_candidates(
    engine: PhoneticEngine,
    candidates: Iterable[Candidate],
    prompt: PromptFn = default_inline_prompt,
) -> dict[str, str]:
    """Iterate ``candidates`` through an inline prompt and persist approvals.

    Returns the mapping of words confirmed in this batch.
    """
    confirmed: dict[str, str] = {}
    for cand in candidates:
        approved, value = prompt(cand.word, cand.suggestion)
        if approved and value:
            engine.confirm(cand.word, value)
            confirmed[cand.word] = value
        else:
            engine.reject(cand.word)
    return confirmed


# --------------------------------------------------------------------- CLI
def _cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Phonetic engine — lyrics phonetic learning loop")
    parser.add_argument("--text", help="Lyrics text to scan", default=None)
    parser.add_argument("--stdin", action="store_true", help="Read text from stdin")
    parser.add_argument("--dict", help="Override dict path", default=None)
    args = parser.parse_args(argv)

    engine = PhoneticEngine(dict_path=Path(args.dict) if args.dict else DICT_PATH)

    if args.stdin:
        import sys as _sys
        text = _sys.stdin.read()
    elif args.text is not None:
        text = args.text
    else:
        parser.error("--text or --stdin is required")
        return 2

    applied, candidates = engine.process_text(text)
    for k, v in applied.items():
        print(f"applied: {k} -> {v}")
    run_candidates(engine, candidates)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
