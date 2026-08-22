"""Display backends for the Stellar Unicorn, and the factory that picks one."""

from __future__ import annotations

import argparse
import sys

from .base import Display
from .null_ import NullDisplay
from .protocol import FRAME_BYTES, HEIGHT, NUM_PIXELS, PROTOCOL_VERSION, WIDTH
from .serial_link import SerialDisplay, StellarUnicornNotFound, find_port
from .term import TerminalDisplay

__all__ = [
    "Display",
    "NullDisplay",
    "SerialDisplay",
    "StellarUnicornNotFound",
    "TerminalDisplay",
    "add_display_args",
    "find_port",
    "open_display",
    "FRAME_BYTES",
    "HEIGHT",
    "NUM_PIXELS",
    "PROTOCOL_VERSION",
    "WIDTH",
]

BACKENDS = ("auto", "serial", "term", "null")


def add_display_args(parser: argparse.ArgumentParser) -> None:
    """Add the display options every app shares."""
    group = parser.add_argument_group("display")
    group.add_argument(
        "--backend",
        choices=BACKENDS,
        default="auto",
        help="where to draw: auto tries the panel then falls back to the terminal",
    )
    group.add_argument(
        "--port",
        default=None,
        help="serial device of the Stellar Unicorn (default: autodetect)",
    )
    group.add_argument(
        "--brightness",
        type=float,
        default=0.5,
        help="panel brightness, 0.0 to 1.0 (default: 0.5)",
    )


def open_display(
    backend: str = "auto",
    port: str | None = None,
    brightness: float = 0.5,
) -> Display:
    """Open a display, falling back to the terminal when asked to.

    ``auto`` prefers the real panel and drops to the terminal preview if
    none is attached, so an app started with no hardware still runs and
    says why on stderr. An explicit ``serial`` raises instead, because a
    caller who named the backend wants to hear about the failure.
    """
    if backend == "null":
        return NullDisplay(brightness=brightness)
    if backend == "term":
        return TerminalDisplay(brightness=brightness)
    if backend == "serial":
        return SerialDisplay(port=port, brightness=brightness)

    try:
        display = SerialDisplay(port=port, brightness=brightness)
    except StellarUnicornNotFound as exc:
        print(f"Stellar Unicorn unavailable: {exc}", file=sys.stderr)
        print("Falling back to the terminal preview.", file=sys.stderr)
        return TerminalDisplay(brightness=brightness)

    print(
        f"Stellar Unicorn connected on {display.port} "
        f"(firmware protocol v{display.firmware_version})",
        file=sys.stderr,
    )
    if not display.firmware_is_current:
        print(
            f"warning: the Pico is running protocol v{display.firmware_version}, "
            f"this needs v{PROTOCOL_VERSION}. Re-copy "
            "firmware/stellar_frame_server.py onto it as main.py, or the panel "
            "will stop responding partway through.",
            file=sys.stderr,
        )
    return display
