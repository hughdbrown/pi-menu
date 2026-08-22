"""The registry of applications the menu offers.

The list lives in JSON so you can add your own programs without editing
any Python. The first of these that exists wins:

1. ``$PI_MENU_APPS``
2. ``~/.config/pi-menu/apps.json``
3. the ``apps.json`` shipped inside the package
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

PACKAGED_APPS = Path(__file__).with_name("apps.json")
USER_APPS = Path.home() / ".config" / "pi-menu" / "apps.json"

#: Substituted into command entries at launch time.
PLACEHOLDERS = {
    "{python}": sys.executable,
    "{home}": str(Path.home()),
}

HOLD_CHOICES = ("on-error", "always", "never")


class ConfigError(ValueError):
    """The apps file exists but could not be used."""


@dataclass(frozen=True)
class AppEntry:
    """One launchable program."""

    id: str
    name: str
    command: list[str]
    description: str = ""
    #: When to keep the terminal window open after the program exits.
    hold: str = "on-error"
    #: False runs the program directly instead of inside a terminal.
    terminal: bool = True
    enabled: bool = True
    extra: dict = field(default_factory=dict, repr=False)

    def resolved_command(self) -> list[str]:
        """The command with ``{python}``-style placeholders filled in."""
        return [_substitute(part) for part in self.command]


def _substitute(value: str) -> str:
    for placeholder, replacement in PLACEHOLDERS.items():
        value = value.replace(placeholder, replacement)
    return value


def apps_path() -> Path:
    """Which apps.json will be used."""
    override = os.environ.get("PI_MENU_APPS")
    if override:
        return Path(override).expanduser()
    if USER_APPS.exists():
        return USER_APPS
    return PACKAGED_APPS


def load_apps(path: Path | None = None) -> list[AppEntry]:
    """Read the app registry. Raises :class:`ConfigError` on bad input."""
    path = path or apps_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"no app list at {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from exc

    entries = raw.get("apps") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ConfigError(f"{path} must hold a list of apps, or an 'apps' key")

    return [_parse(entry, index, path) for index, entry in enumerate(entries)]


def _parse(entry: object, index: int, path: Path) -> AppEntry:
    where = f"{path}: app #{index + 1}"
    if not isinstance(entry, dict):
        raise ConfigError(f"{where} must be an object")

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"{where} needs a non-empty 'name'")

    command = entry.get("command")
    if isinstance(command, str):
        raise ConfigError(
            f"{where}: 'command' must be a list of arguments, not a string "
            f"(use [\"python3\", \"-m\", \"…\"] so no shell quoting is needed)"
        )
    if not isinstance(command, list) or not command:
        raise ConfigError(f"{where} needs a non-empty 'command' list")
    if not all(isinstance(part, str) for part in command):
        raise ConfigError(f"{where}: every entry in 'command' must be a string")

    hold = entry.get("hold", "on-error")
    if hold not in HOLD_CHOICES:
        raise ConfigError(f"{where}: 'hold' must be one of {', '.join(HOLD_CHOICES)}")

    known = {"id", "name", "command", "description", "hold", "terminal", "enabled"}
    return AppEntry(
        id=str(entry.get("id") or _slug(name)),
        name=name,
        command=list(command),
        description=str(entry.get("description", "")),
        hold=hold,
        terminal=bool(entry.get("terminal", True)),
        enabled=bool(entry.get("enabled", True)),
        extra={k: v for k, v in entry.items() if k not in known},
    )


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
