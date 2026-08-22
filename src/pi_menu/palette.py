"""Colours shared by the apps.

Kept in one place so the Tk swatch and the LED always agree.
"""

from __future__ import annotations

#: Name -> RGB, used for live cells and Tk swatches alike.
PALETTE: dict[str, tuple[int, int, int]] = {
    "Green": (0, 255, 80),
    "Amber": (255, 150, 0),
    "Cyan": (0, 200, 255),
    "Magenta": (255, 0, 160),
    "White": (255, 255, 255),
}

DEFAULT_COLOUR = "Green"

# Tk chrome, dark enough that the app does not glare next to a lit panel.
BG = "#16161c"
PANEL_BG = "#0d0d11"
CELL_DEAD = "#1d1d25"
GRID_LINE = "#2c2c38"
FG = "#e6e6ee"
MUTED = "#9a9aab"


def to_hex(rgb: tuple[int, int, int]) -> str:
    """Format an RGB triple as a Tk colour string."""
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"
