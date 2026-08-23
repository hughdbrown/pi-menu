"""Which levels have been finished, kept between runs.

This file exists to colour the level picker green, and for nothing else.
Every level is always playable, so a file that is missing, corrupt,
unreadable or unwritable has to mean "nothing finished yet" rather than
an error: refusing to start a game because a cache of cosmetic state
could not be parsed would be absurd.

The path follows the convention :mod:`pi_menu.config` already uses --
``~/.config/pi-menu``, with an environment variable to point it
somewhere else.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

ENV_VAR = "PI_MENU_PROGRESS"
FILENAME = "platform-progress.json"


def default_path() -> Path:
    """Where completed levels are recorded."""
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "pi-menu" / FILENAME


class Progress:
    """The set of finished level ids, loaded on creation and saved on change."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_path()
        self._completed = _read(self.path)

    @property
    def completed(self) -> frozenset:
        return frozenset(self._completed)

    def is_done(self, level_id: str) -> bool:
        return level_id in self._completed

    def mark(self, level_id: str) -> None:
        """Record a finished level. Saving is best effort."""
        if level_id in self._completed:
            return
        self._completed.add(level_id)
        _write(self.path, self._completed)


def _read(path: Path) -> set:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(raw, dict):
        return set()
    entries = raw.get("completed")
    if not isinstance(entries, list):
        return set()
    return {entry for entry in entries if isinstance(entry, str)}


def _write(path: Path, completed: Iterable[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"completed": sorted(completed)}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # A read-only home, a full disk, or something already sitting
        # where the file should be. The game does not need this to run.
        pass
