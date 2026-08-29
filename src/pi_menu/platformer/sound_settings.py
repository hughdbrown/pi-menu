"""The sound setting, kept between runs.

Three choices: theme music, sound on events, or silence. Like
:mod:`.progress`, a file that is missing, corrupt or unwritable must
mean "the default" rather than an error -- refusing to start a game
over a one-word preference file would be absurd.

The path follows the convention :mod:`pi_menu.config` already uses --
``~/.config/pi-menu``, with an environment variable to point it
somewhere else.
"""

from __future__ import annotations

import enum
import json
import os
from pathlib import Path

ENV_VAR = "PI_MENU_SOUND"
FILENAME = "platform-sound.json"


class Sound(enum.Enum):
    """What the speaker does while the game runs."""

    MUSIC = "music"
    EFFECTS = "effects"
    OFF = "off"


DEFAULT = Sound.MUSIC


def default_path() -> Path:
    """Where the choice is recorded."""
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "pi-menu" / FILENAME


def load(path: Path | None = None) -> Sound:
    """The saved choice, or the default when there is no usable file."""
    target = Path(path) if path is not None else default_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT
    if not isinstance(raw, dict):
        return DEFAULT
    try:
        return Sound(raw.get("sound"))
    except ValueError:
        return DEFAULT


def save(mode: Sound, path: Path | None = None) -> None:
    """Record the choice. Saving is best effort."""
    target = Path(path) if path is not None else default_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"sound": mode.value}) + "\n", encoding="utf-8"
        )
    except OSError:
        pass
