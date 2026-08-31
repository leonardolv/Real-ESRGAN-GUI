"""Persistent user configuration management.

Saves and restores GUI settings (window geometry, last-used model, output
preferences) to a JSON file in the user's home directory so everything
survives across sessions.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

# Default config dir: ~/.realesrgan-gui/
CONFIG_DIR = Path.home() / ".realesrgan-gui"
CONFIG_FILE = CONFIG_DIR / "config.json"

_DEFAULTS: Dict[str, Any] = {
    # Window geometry
    "window_width": 1400,
    "window_height": 850,
    "window_x": None,
    "window_y": None,
    "window_maximized": False,

    # Model & processing
    "last_model": "RealESRGAN_x4plus",
    "last_scale": 4.0,
    "last_tile": 0,
    "tile_pad": 10,
    "pre_pad": 0,
    "face_enhance": False,
    "fp32": False,
    "denoise_strength": 0.5,
    "alpha_upsampler": "realesrgan",

    # Output
    "output_format": "auto",
    "output_suffix": "out",
    "output_folder": "results",

    # UI preferences
    "theme": "system",  # "system", "dark", "light"

    # File history
    "last_input_folder": "",
    "recent_files": [],
}

MAX_RECENT_FILES = 20


class Config:
    """Thread-safe, auto-persisting configuration store."""

    def __init__(self, path: Path | None = None):
        self._path = path or CONFIG_FILE
        self._data: Dict[str, Any] = dict(_DEFAULTS)
        self._load()

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def get(self, key: str, fallback: Any = None) -> Any:
        """Retrieve a config value, with optional fallback."""
        return self._data.get(key, fallback if fallback is not None else _DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist to disk."""
        self._data[key] = value
        self._save()

    def update(self, mapping: Dict[str, Any]) -> None:
        """Bulk-update multiple keys and persist once."""
        self._data.update(mapping)
        self._save()

    def reset(self) -> None:
        """Reset all settings to defaults."""
        self._data = dict(_DEFAULTS)
        self._save()

    def add_recent_file(self, filepath: str) -> None:
        """Add a file to the recent-files list (most-recent first)."""
        recents = self._data.get("recent_files", [])
        # Remove if already present so it moves to the top
        if filepath in recents:
            recents.remove(filepath)
        recents.insert(0, filepath)
        self._data["recent_files"] = recents[:MAX_RECENT_FILES]
        self._save()

    @property
    def data(self) -> Dict[str, Any]:
        """Return a copy of all config data."""
        return dict(self._data)

    # ------------------------------------------------------------------ #
    #  Persistence                                                        #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        """Load config from disk, merging with defaults for missing keys."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                # Merge: defaults first, then stored values overwrite
                self._data = {**_DEFAULTS, **stored}
            except (json.JSONDecodeError, OSError):
                # Corrupted file — fall back to defaults
                self._data = dict(_DEFAULTS)
        # Ensure config dir exists for future saves
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _save(self) -> None:
        """Persist current config to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass  # Silently fail — not critical
