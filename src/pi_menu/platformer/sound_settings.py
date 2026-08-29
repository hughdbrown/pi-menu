"""The sound settings, kept between runs.

Two loudnesses and a tune choice: how loud the music is, how loud the
event blips are (either can be zero, which is off), and which of the
gameplay tunes plays. Like :mod:`.progress`, a file that is missing,
corrupt or unwritable must mean "the defaults" rather than an error --
refusing to start a game over a preferences file would be absurd.

The path follows the convention :mod:`pi_menu.config` already uses --
``~/.config/pi-menu``, with an environment variable to point it
somewhere else.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace as _replace
from pathlib import Path

ENV_VAR = "PI_MENU_SOUND"
FILENAME = "platform-sound.json"

#: Loudness runs 0 (off) to MAX_LEVEL (as loud as the panel goes).
MAX_LEVEL = 8

#: How many gameplay tunes there are to choose from, numbered from 1.
TUNE_CHOICES = 5


def _clamp(value, lowest: int, highest: int, fallback: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        return fallback
    return max(lowest, min(highest, value))


@dataclass(frozen=True)
class SoundSettings:
    """What the speaker does, and how loudly."""

    music: int = 6  #: 0 (silent) to MAX_LEVEL
    effects: int = 6  #: 0 (silent) to MAX_LEVEL
    tune: int = 1  #: 1 to TUNE_CHOICES, picking the gameplay music

    def with_music(self, level: int) -> "SoundSettings":
        return _replace(self, music=_clamp(level, 0, MAX_LEVEL, self.music))

    def with_effects(self, level: int) -> "SoundSettings":
        return _replace(self, effects=_clamp(level, 0, MAX_LEVEL, self.effects))

    def with_tune(self, number: int) -> "SoundSettings":
        return _replace(self, tune=_clamp(number, 1, TUNE_CHOICES, self.tune))


DEFAULTS = SoundSettings()


def default_path() -> Path:
    """Where the choices are recorded."""
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "pi-menu" / FILENAME


def load(path: Path | None = None) -> SoundSettings:
    """The saved choices, or the defaults where nothing usable is saved.

    Understands the earlier one-word format too: ``{"sound": "music"}``
    ran the tunes, ``"effects"`` ran only the blips, ``"off"`` was
    silence -- mapped onto loudnesses so an old file keeps its meaning.
    """
    target = Path(path) if path is not None else default_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULTS
    if not isinstance(raw, dict):
        return DEFAULTS

    old = raw.get("sound")
    if old == "effects":
        return DEFAULTS.with_music(0)
    if old == "off":
        return DEFAULTS.with_music(0).with_effects(0)

    return (
        DEFAULTS.with_music(raw.get("music", DEFAULTS.music))
        .with_effects(raw.get("effects", DEFAULTS.effects))
        .with_tune(raw.get("tune", DEFAULTS.tune))
    )


def save(settings: SoundSettings, path: Path | None = None) -> None:
    """Record the choices. Saving is best effort."""
    target = Path(path) if path is not None else default_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "music": settings.music,
                    "effects": settings.effects,
                    "tune": settings.tune,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
