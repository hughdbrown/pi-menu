"""The art, exactly as the HTML draws it.

Every sheet here is the one extracted from the HTML's embedded PNGs by
``tools/extract_microcraft_sprites.py``, passed through untouched, so
the panel shows the same tiles the browser does. This module is the one
place a panel-specific recolour would go if one is ever wanted again;
:func:`lift` is kept for that, but nothing uses it by default.
"""

from __future__ import annotations

from . import sprites
from .tiles import (
    FLOW_TILES, ITEMS as ITEM_KINDS, MIRRORED_TILES, UI_BG_X,
    FLUID_SHEET_POS, ITEM_SHEET_POS, SHEET_POS,
)

#: The LED floor a recolour would lift to; see :func:`lift`.
FLOOR = 40

BLOCK_SHEET = sprites.BLOCK_SHEET
FLUID_SHEET = sprites.FLUID_SHEET
ITEM_SHEET = sprites.ITEM_SHEET
UI_SHEET = sprites.UI_SHEET
FIRE_SHEET = sprites.FIRE_SHEET
BREAK_SHEET = sprites.BREAK_SHEET
FURNACE_PROGRESS_SHEET = sprites.FURNACE_PROGRESS_SHEET
FURNACE_OXYGEN_BUTTON = sprites.FURNACE_OXYGEN_BUTTON
SPIDER_SHEET = sprites.SPIDER_SHEET
CRAFT_BUTTON = sprites.CRAFT_BUTTON

UI_BG_COLOUR = UI_SHEET[0][UI_BG_X]

# Flat colours the HTML paints with fillStyle rather than a sprite.
FUEL_FILL = (255, 108, 0)      # '#ff6c00'
HEAT_FILL = (255, 0, 0)        # '#ff0000'
BAR_BACKGROUND = (19, 19, 19)  # '#131313'

#: Empty-slot backgrounds: the HTML's empty slot tile is solid black.
SLOT_COLOUR = (0, 0, 0)


def lift(colour):
    """Raise a colour above the LED floor, keeping its hue and its
    proportions; transparent stays transparent, and true black stays
    black because the sheets use it for 'nothing here'. Unused by the
    default art; kept for an optional panel recolour."""
    if colour is None:
        return None
    r, g, b = colour
    if max(r, g, b) == 0:
        return colour
    scale = (255 - FLOOR) / 255
    return (int(FLOOR + r * scale), int(FLOOR + g * scale), int(FLOOR + b * scale))


def slot_colour(dx: int, dy: int):
    """The background colour of the slot whose top-left LED is ``(dx, dy)``."""
    return SLOT_COLOUR


def slot_tile(dx: int, dy: int):
    """The 2x2 empty-slot pattern for the slot at ``(dx, dy)``: solid black."""
    return ((SLOT_COLOUR, SLOT_COLOUR), (SLOT_COLOUR, SLOT_COLOUR))


def tile_art(kind: int):
    """``(sheet, sx, sy, mirrored)`` for any block or item."""
    if kind in ITEM_KINDS:
        sx, sy = ITEM_SHEET_POS[kind]
        return ITEM_SHEET, sx, sy, False
    if kind in FLOW_TILES:
        sx, sy = FLUID_SHEET_POS[kind]
        return FLUID_SHEET, sx, sy, kind in MIRRORED_TILES
    sx, sy = SHEET_POS[kind]
    return BLOCK_SHEET, sx, sy, False


def _average(sheet, sx: int, sy: int):
    """The HTML's AVG_COLOR: the mean of the tile's top row; for items,
    pitch black counts as empty."""
    samples = [sheet[sy][sx], sheet[sy][sx + 1]]
    if sheet is ITEM_SHEET:
        samples = [c for c in samples if c is not None and c != (0, 0, 0)]
    else:
        samples = [c for c in samples if c is not None]
    if not samples:
        return (128, 128, 128)
    n = len(samples)
    return tuple(round(sum(c[i] for c in samples) / n) for i in range(3))


#: The one-pixel colour a dropped item is drawn with, as the HTML's AVG_COLOR.
AVERAGE_COLOUR = {
    kind: _average(*tile_art(kind)[:3]) for kind in list(SHEET_POS) + list(ITEM_SHEET_POS)
}
