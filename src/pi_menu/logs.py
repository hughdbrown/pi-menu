"""File logging for the apps, aimed at the GUI-launched case.

A program started from the desktop menu has no terminal, so everything
it prints -- tracebacks included -- vanishes. Each app therefore writes
a log under ``~/.local/state/pi-menu/``, one file per app, rotated so it
can never fill a disk. When something misbehaves on the Pi, the log is
the first thing worth reading:

    tail -50 ~/.local/state/pi-menu/pi-menu.log

Logging must never be the thing that breaks the app: if the directory
cannot be created or written, the app runs without a log rather than
not at all.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

ENV_VAR = "PI_MENU_LOG_DIR"

#: Modest by design; two files of this size is plenty of history.
MAX_BYTES = 256_000
BACKUPS = 1

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def default_directory() -> Path:
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local" / "state" / "pi-menu"


def setup(app_name: str) -> Path | None:
    """Send the ``pi_menu`` logger to a file. Returns the file's path.

    Safe to call more than once -- a second call for the same file adds
    nothing. Returns None when no log could be opened, and the app is
    expected to carry on exactly as before.
    """
    logger = logging.getLogger("pi_menu")
    logger.setLevel(logging.DEBUG)

    try:
        directory = default_directory()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{app_name}.log"

        already = any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            and Path(getattr(h, "baseFilename", "")) == path
            for h in logger.handlers
        )
        if not already:
            handler = logging.handlers.RotatingFileHandler(
                path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter(FORMAT))
            logger.addHandler(handler)
        return path
    except OSError:
        return None


def log_unhandled(logger: logging.Logger) -> None:
    """Route uncaught exceptions through the log before they die.

    From a terminal a traceback lands in your face; from the desktop
    menu it lands nowhere. This keeps the normal stderr behaviour and
    adds the copy that survives.
    """
    previous = sys.excepthook

    def hook(kind, value, traceback):
        if not issubclass(kind, KeyboardInterrupt):
            logger.critical(
                "uncaught exception", exc_info=(kind, value, traceback)
            )
        previous(kind, value, traceback)

    sys.excepthook = hook
