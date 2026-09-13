"""The art, recoloured for LEDs.

The HTML's sprites were drawn for a bright screen at many pixels a
block: stone is a 51-grey, dirt a 56-brown, coal ore grey with 23-grey
flecks. On the Stellar Unicorn, whose LEDs are gamma-corrected and dim
at the bottom of the range, those all read as black, and at two pixels
a block the greys of stone, cobblestone, furnace and clay are the same
grey. So every block and item gets its own 2x2 pattern here: the same
two-tone shape as the original where it has one, but lifted well above
the LEDs' floor and given a hue no neighbour shares.

Colours that are not blocks -- UI tiles, fire, the crack overlay -- go
through :func:`lift`, which raises the floor without changing the hue.
"""

from __future__ import annotations

from . import sprites
from .tiles import (
    FLOW_TILES, ITEMS as ITEM_KINDS, MIRRORED_TILES, UI_BG_X,
    BRICK, BUCKET_EMPTY, BUCKET_LAVA, BUCKET_WATER, CLAY, COAL, COAL_ORE, COBBLESTONE,
    COPPER, COPPER_AXE, COPPER_ORE, COPPER_PICKAXE, COPPER_SWORD, CRAFTING_TABLE, DIRT,
    FLUID_SHEET_POS, FURNACE, GRASS, IRON, IRON_AXE, IRON_ORE, IRON_PICKAXE, IRON_SWORD,
    ITEM_SHEET_POS, LAVA, LAVA_FLOW_DOWN, LAVA_FLOW_R1, LAVA_FLOW_R2, LAVA_FLOW_R3, LEAF,
    SAND, SHEET_POS, STICK, STONE, STONE_AXE, STONE_PICKAXE, STONE_SWORD, TUNGSTEN,
    TUNGSTEN_AXE, TUNGSTEN_ORE, TUNGSTEN_PICKAXE, TUNGSTEN_SWORD, WATER,
    WATER_FLOW_DOWN, WATER_FLOW_R1, WATER_FLOW_R2, WATER_FLOW_R3, WEBBING, WOOD,
    WOOD_PLANKS,
)

#: Nothing lit on the panel goes below this, so it is never mistaken for off.
FLOOR = 40

# Named colours, chosen to sit apart on the panel.
GRASS_TOP = (60, 220, 50)
GRASS_SOIL = (150, 90, 40)
SOIL = (160, 95, 45)
SOIL_DARK = (120, 70, 35)
ROCK = (130, 130, 140)
ROCK_DARK = (95, 95, 105)
BARK = (140, 85, 40)
BARK_DARK = (90, 55, 25)
LEAF_LIGHT = (20, 150, 40)
LEAF_DARK = (10, 100, 30)
COAL_FLECK = (10, 10, 20)
IRON_FLECK = (255, 205, 175)
COPPER_FLECK = (255, 130, 40)
LAVA_HOT = (255, 90, 0)
LAVA_GLOW = (255, 160, 0)
WATER_DEEP = (20, 60, 255)
WATER_LIGHT = (40, 110, 255)
PLANK = (215, 170, 90)
PLANK_DARK = (180, 135, 65)
TABLE_TOP = (110, 65, 30)
COBBLE_LIGHT = (175, 175, 185)
COBBLE_DARK = (80, 80, 95)
FURNACE_MOUTH = (255, 110, 20)
CLAY_LIGHT = (170, 175, 215)
CLAY_DARK = (125, 130, 175)
SAND_LIGHT = (255, 240, 150)
SAND_DARK = (230, 210, 120)
BRICK_RED = (220, 75, 45)
BRICK_MORTAR = (255, 160, 130)
STEEL = (220, 225, 235)
STEEL_DARK = (150, 155, 170)
COPPER_METAL = (240, 120, 40)
COPPER_DARK = (170, 80, 25)
TUNGSTEN_METAL = (200, 210, 220)
TUNGSTEN_DARK = (140, 150, 160)
STONE_TOOL = (150, 150, 160)
HANDLE = (150, 95, 45)
COAL_LUMP = (95, 95, 125)
BUCKET = (200, 200, 215)
WEB_SILVER = (180, 180, 190)

#: kind -> ((top-left, top-right), (bottom-left, bottom-right)).
BLOCKS = {
    GRASS: ((GRASS_TOP, GRASS_TOP), (GRASS_SOIL, SOIL_DARK)),
    DIRT: ((SOIL, SOIL_DARK), (SOIL_DARK, SOIL)),
    STONE: ((ROCK, ROCK_DARK), (ROCK_DARK, ROCK)),
    WOOD: ((BARK, BARK_DARK), (BARK, BARK_DARK)),
    LEAF: ((LEAF_LIGHT, LEAF_DARK), (LEAF_DARK, LEAF_LIGHT)),
    COAL_ORE: ((ROCK, COAL_FLECK), (COAL_FLECK, ROCK)),
    IRON_ORE: ((ROCK, IRON_FLECK), (IRON_FLECK, ROCK)),
    COPPER_ORE: ((ROCK, COPPER_FLECK), (COPPER_FLECK, ROCK)),
    LAVA: ((LAVA_HOT, LAVA_GLOW), (LAVA_GLOW, LAVA_HOT)),
    WATER: ((WATER_DEEP, WATER_LIGHT), (WATER_LIGHT, WATER_DEEP)),
    WOOD_PLANKS: ((PLANK, PLANK_DARK), (PLANK, PLANK_DARK)),
    CRAFTING_TABLE: ((TABLE_TOP, TABLE_TOP), (PLANK, PLANK_DARK)),
    COBBLESTONE: ((COBBLE_LIGHT, COBBLE_DARK), (COBBLE_DARK, COBBLE_LIGHT)),
    FURNACE: ((ROCK_DARK, ROCK_DARK), (FURNACE_MOUTH, ROCK_DARK)),
    CLAY: ((CLAY_LIGHT, CLAY_DARK), (CLAY_DARK, CLAY_LIGHT)),
    SAND: ((SAND_LIGHT, SAND_DARK), (SAND_DARK, SAND_LIGHT)),
    BRICK: ((BRICK_RED, BRICK_RED), (BRICK_MORTAR, BRICK_RED)),
    TUNGSTEN_ORE: ((ROCK, TUNGSTEN_METAL), (TUNGSTEN_METAL, ROCK)),
    WEBBING: ((WEB_SILVER, None), (None, WEB_SILVER)),
}

#: The flow tiles keep the source's colours and the original's outline:
#: falling is a full-height column, the tapers lose pixels as they thin.
FLOWS = {
    LAVA_FLOW_DOWN: ((LAVA_HOT, LAVA_GLOW), (LAVA_GLOW, LAVA_HOT)),
    LAVA_FLOW_R1: ((LAVA_HOT, None), (LAVA_GLOW, LAVA_HOT)),
    LAVA_FLOW_R2: ((None, None), (LAVA_HOT, LAVA_GLOW)),
    LAVA_FLOW_R3: ((None, None), (LAVA_GLOW, None)),
    WATER_FLOW_DOWN: ((WATER_DEEP, WATER_LIGHT), (WATER_LIGHT, WATER_DEEP)),
    WATER_FLOW_R1: ((WATER_DEEP, None), (WATER_LIGHT, WATER_DEEP)),
    WATER_FLOW_R2: ((None, None), (WATER_DEEP, WATER_LIGHT)),
    WATER_FLOW_R3: ((None, None), (WATER_LIGHT, None)),
}

ITEMS = {
    STICK: ((None, HANDLE), (HANDLE, None)),
    IRON_SWORD: ((None, STEEL), (HANDLE, None)),
    COPPER_SWORD: ((None, COPPER_METAL), (HANDLE, None)),
    IRON_PICKAXE: ((STEEL, STEEL), (None, HANDLE)),
    COPPER_PICKAXE: ((COPPER_METAL, COPPER_METAL), (None, HANDLE)),
    IRON_AXE: ((STEEL, None), (HANDLE, STEEL_DARK)),
    COPPER_AXE: ((COPPER_METAL, None), (HANDLE, COPPER_DARK)),
    COAL: ((COAL_LUMP, None), (None, COAL_LUMP)),
    COPPER: ((COPPER_METAL, COPPER_DARK), (COPPER_DARK, COPPER_METAL)),
    IRON: ((STEEL, STEEL_DARK), (STEEL_DARK, STEEL)),
    STONE_SWORD: ((None, STONE_TOOL), (HANDLE, None)),
    STONE_PICKAXE: ((STONE_TOOL, STONE_TOOL), (None, HANDLE)),
    STONE_AXE: ((STONE_TOOL, None), (HANDLE, ROCK_DARK)),
    BUCKET_EMPTY: ((BUCKET, BUCKET), (None, BUCKET)),
    BUCKET_LAVA: ((LAVA_HOT, BUCKET), (None, BUCKET)),
    BUCKET_WATER: ((WATER_LIGHT, BUCKET), (None, BUCKET)),
    TUNGSTEN: ((TUNGSTEN_METAL, TUNGSTEN_DARK), (TUNGSTEN_DARK, TUNGSTEN_METAL)),
    TUNGSTEN_SWORD: ((None, TUNGSTEN_METAL), (HANDLE, None)),
    TUNGSTEN_PICKAXE: ((TUNGSTEN_METAL, TUNGSTEN_METAL), (None, HANDLE)),
    TUNGSTEN_AXE: ((TUNGSTEN_METAL, None), (HANDLE, TUNGSTEN_DARK)),
}


def lift(colour):
    """Raise a colour above the LED floor, keeping its hue and its
    proportions; transparent stays transparent, and true black stays
    black because the sheets use it for 'nothing here'."""
    if colour is None:
        return None
    r, g, b = colour
    if max(r, g, b) == 0:
        return colour
    scale = (255 - FLOOR) / 255
    return (int(FLOOR + r * scale), int(FLOOR + g * scale), int(FLOOR + b * scale))


def _lifted(sheet):
    return tuple(tuple(lift(c) for c in row) for row in sheet)


def _apply(sheet, positions, patterns):
    """Copy a sheet, dropping each pattern in at its tile's position."""
    rows = [list(row) for row in sheet]
    for kind, (sx, sy) in positions.items():
        pattern = patterns.get(kind)
        if pattern is None:
            continue
        for dy in range(2):
            for dx in range(2):
                rows[sy + dy][sx + dx] = pattern[dy][dx]
    return tuple(tuple(row) for row in rows)


BLOCK_SHEET = _apply(sprites.BLOCK_SHEET, SHEET_POS, BLOCKS)
#: Only the right-facing flow tiles have positions of their own; the
#: left-facing ones share them and are mirrored when drawn.
FLUID_SHEET = _apply(
    sprites.FLUID_SHEET,
    {k: v for k, v in FLUID_SHEET_POS.items() if k in FLOWS},
    FLOWS,
)
ITEM_SHEET = _apply(sprites.ITEM_SHEET, ITEM_SHEET_POS, ITEMS)
UI_SHEET = _lifted(sprites.UI_SHEET)
FIRE_SHEET = _lifted(sprites.FIRE_SHEET)
#: The crack is drawn over a lit block, so it wants to be dark, not lifted.
BREAK_SHEET = sprites.BREAK_SHEET
#: The furnace progress sheet is dark grey on transparent; lift it so it shows.
FURNACE_PROGRESS_SHEET = _lifted(sprites.FURNACE_PROGRESS_SHEET)
FURNACE_OXYGEN_BUTTON = _lifted(sprites.FURNACE_OXYGEN_BUTTON)
SPIDER_SHEET = _lifted(sprites.SPIDER_SHEET)
CRAFT_BUTTON = ((110, 110, 125), (140, 140, 155)), ((140, 140, 155), (110, 110, 125))

UI_BG_COLOUR = UI_SHEET[0][UI_BG_X]

#: Empty-slot backgrounds. Black: the slot reads as a hole in the grey
#: panel, and whatever sits in it is the only thing lit.
SLOT_COLOUR = (0, 0, 0)


def slot_colour(dx: int, dy: int):
    """The background colour of the slot whose top-left LED is ``(dx, dy)``."""
    return SLOT_COLOUR


def slot_tile(dx: int, dy: int):
    """The 2x2 empty-slot pattern for the slot at ``(dx, dy)``: solid black."""
    return ((SLOT_COLOUR, SLOT_COLOUR), (SLOT_COLOUR, SLOT_COLOUR))


def tile_art(kind: int):
    """``(sheet, sx, sy, mirrored)`` for any block or item, panel colours."""
    if kind in ITEM_KINDS:
        sx, sy = ITEM_SHEET_POS[kind]
        return ITEM_SHEET, sx, sy, False
    if kind in FLOW_TILES:
        sx, sy = FLUID_SHEET_POS[kind]
        return FLUID_SHEET, sx, sy, kind in MIRRORED_TILES
    sx, sy = SHEET_POS[kind]
    return BLOCK_SHEET, sx, sy, False


def _average(sheet, sx: int, sy: int):
    samples = [
        sheet[sy + dy][sx + dx]
        for dy in range(2)
        for dx in range(2)
        if sheet[sy + dy][sx + dx] is not None
    ]
    if not samples:
        return (128, 128, 128)
    n = len(samples)
    return tuple(round(sum(c[i] for c in samples) / n) for i in range(3))


#: The one-pixel colour a dropped item is drawn with.
AVERAGE_COLOUR = {
    kind: _average(*tile_art(kind)[:3]) for kind in list(SHEET_POS) + list(ITEM_SHEET_POS)
}
