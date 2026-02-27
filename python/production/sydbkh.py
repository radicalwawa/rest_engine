"""
SYDBKH — deterministic track plan for radical.grey (first song).
Loads from repo JSON; no external services. Fail-fast on missing files/keys.
"""
from pathlib import Path
import json

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRACK_GREY = REPO_ROOT / "tracks" / "radical.grey.json"
ALBUM_MANIFEST = REPO_ROOT / "domain" / "album_5_manifest.json"
SOUND_LIBRARY = REPO_ROOT / "knowledge" / "sound_library.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path.relative_to(REPO_ROOT)}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(REPO_ROOT)}: must be a JSON object")
    return data


class SYDBKH:
    """Track plan for first song: radical.grey. Identity and inputs from repo files."""

    track_code = "SYDBKH"
    state = "radical.grey"

    def __init__(self) -> None:
        self._track_data: dict | None = None
        self._release_format: dict | None = None

    def _ensure_track(self) -> dict:
        if self._track_data is None:
            self._track_data = _load_json(TRACK_GREY)
            if self._track_data.get("id") != self.state:
                raise ValueError(f"{TRACK_GREY.relative_to(REPO_ROOT)}: id must be {self.state!r}")
        return self._track_data

    def _ensure_release_format(self) -> dict:
        if self._release_format is None:
            data = _load_json(ALBUM_MANIFEST)
            rf = data.get("release_format")
            if rf is None:
                raise ValueError(f"{ALBUM_MANIFEST.relative_to(REPO_ROOT)}: release_format must exist")
            if not isinstance(rf, dict):
                raise ValueError(f"{ALBUM_MANIFEST.relative_to(REPO_ROOT)}: release_format must be an object")
            self._release_format = rf
        return self._release_format

    def get_library_binding(self) -> dict:
        """Return library_binding from tracks/radical.grey.json (kick, bass, hat, lead, texture)."""
        track = self._ensure_track()
        binding = track.get("library_binding")
        if binding is None:
            raise ValueError(f"{TRACK_GREY.relative_to(REPO_ROOT)}: library_binding must exist")
        if not isinstance(binding, dict):
            raise ValueError(f"{TRACK_GREY.relative_to(REPO_ROOT)}: library_binding must be an object")
        for key in ("kick", "bass", "hat", "lead", "texture"):
            if key not in binding:
                raise ValueError(f"{TRACK_GREY.relative_to(REPO_ROOT)}: library_binding must have key {key!r}")
        return dict(binding)

    def get_duration_targets(self) -> dict:
        """Return radio and extended duration targets (target_sec, min_sec, max_sec) from album manifest."""
        rf = self._ensure_release_format()
        return {
            "radio": {
                "target_sec": rf["radio_version_target_sec"],
                "min_sec": rf["radio_version_min_sec"],
                "max_sec": rf["radio_version_max_sec"],
            },
            "extended": {
                "target_sec": rf["extended_version_target_sec"],
                "min_sec": rf["extended_version_min_sec"],
                "max_sec": rf["extended_version_max_sec"],
            },
        }

    def _verify_assets_optional(self) -> None:
        """Optional: verify referenced asset ids exist in sound_library.json."""
        if not SOUND_LIBRARY.exists():
            return
        data = _load_json(SOUND_LIBRARY)
        assets = data.get("assets") or []
        ids = {a.get("id") for a in assets if isinstance(a, dict) and a.get("id")}
        binding = self.get_library_binding()
        for role, asset_id in binding.items():
            if asset_id not in ids:
                raise ValueError(f"library_binding.{role} asset id {asset_id!r} not in {SOUND_LIBRARY.relative_to(REPO_ROOT)}")

    def build_suno_prompt(self, variant: str) -> str:
        """
        Build deterministic Suno prompt string (English). variant must be "radio" or "extended".
        No external calls; returns a string only.
        """
        if variant not in ("radio", "extended"):
            raise ValueError("variant must be 'radio' or 'extended'")
        track = self._ensure_track()
        theme = track.get("theme") or ""
        energy = track.get("energy_profile") or ""
        emotional = track.get("emotional_tone") or ""
        lyrical = track.get("lyrical_focus") or ""
        keywords = track.get("keyword_vector")
        if isinstance(keywords, list):
            kw = ", ".join(str(k) for k in keywords[:5])
        else:
            kw = ""
        tp = track.get("techno_profile") or {}
        drive = tp.get("drive_level") or ""
        bass_weight = tp.get("bass_weight") or ""
        texture_type = tp.get("texture_type") or ""
        spatial = tp.get("spatial_depth") or ""

        binding = self.get_library_binding()
        roles = f"Kick/bass/hat/lead/texture bound to: {binding.get('kick')}, {binding.get('bass')}, {binding.get('hat')}, {binding.get('lead')}, {binding.get('texture')}."

        if variant == "radio":
            format_note = "Radio edit. Tight structure, clear hooks, radio-friendly length."
        else:
            format_note = "Extended version. Full arrangement, room for builds and breakdowns."

        parts = [
            f"State: {self.state}. Track: {self.track_code}.",
            format_note,
            f"Theme: {theme}.",
            f"Energy: {energy}. Emotional tone: {emotional}.",
            f"Lyrical focus: {lyrical}.",
            f"Keywords: {kw}." if kw else "",
            f"Techno: drive {drive}, bass {bass_weight}, texture {texture_type}, spatial {spatial}.",
            roles,
        ]
        return " ".join(p for p in parts if p).strip()
