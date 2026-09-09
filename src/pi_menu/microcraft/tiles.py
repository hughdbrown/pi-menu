"""Every kind of block and item, and what is true of each.

Ids follow the HTML exactly so a saved screenshot, a recipe or a bug
report reads the same against either version. Blocks are below 100 and
can be placed in the world; items are 100 and up and only ever live in
the inventory. Fluids are blocks you swim through rather than stand on,
and each has a source tile plus seven flowing tiles that carry the
direction and taper the simulation needs.
"""

from __future__ import annotations

from typing import NamedTuple

from . import sprites

# -- blocks --------------------------------------------------------------

SKY = 0
GRASS = 1
DIRT = 2
STONE = 3
WOOD = 4
LEAF = 5
COAL_ORE = 6
IRON_ORE = 7
COPPER_ORE = 8
LAVA = 9
WATER = 10
WOOD_PLANKS = 11
CRAFTING_TABLE = 12
LAVA_FLOW_DOWN = 13
LAVA_FLOW_R1 = 14
LAVA_FLOW_R2 = 15
LAVA_FLOW_R3 = 16
LAVA_FLOW_L1 = 17
LAVA_FLOW_L2 = 18
LAVA_FLOW_L3 = 19
WATER_FLOW_DOWN = 20
WATER_FLOW_R1 = 21
WATER_FLOW_R2 = 22
WATER_FLOW_R3 = 23
WATER_FLOW_L1 = 24
WATER_FLOW_L2 = 25
WATER_FLOW_L3 = 26
COBBLESTONE = 27
FURNACE = 28
CLAY = 29
SAND = 30
BRICK = 31

# -- items ---------------------------------------------------------------

STICK = 100
IRON_SWORD = 101
COPPER_SWORD = 102
IRON_PICKAXE = 103
COPPER_PICKAXE = 104
IRON_AXE = 105
COPPER_AXE = 106
COAL = 107
COPPER = 108
IRON = 109
STONE_SWORD = 110
STONE_PICKAXE = 111
STONE_AXE = 112
BUCKET_EMPTY = 113
BUCKET_LAVA = 114
BUCKET_WATER = 115

# -- where each one's art is ---------------------------------------------

#: Each tile is 2x2; these are top-left pixels in the block sheet.
SHEET_POS = {
    GRASS: (0, 0), DIRT: (2, 0), STONE: (4, 0), WOOD: (6, 0), LEAF: (8, 0),
    COAL_ORE: (10, 0), IRON_ORE: (12, 0), COPPER_ORE: (14, 0),
    LAVA: (0, 2), WATER: (2, 2), WOOD_PLANKS: (4, 2), CRAFTING_TABLE: (6, 2),
    COBBLESTONE: (8, 2), FURNACE: (10, 2), CLAY: (12, 2), SAND: (14, 2),
    BRICK: (0, 4),
}

#: Flowing fluids live in their own sheet. Left-flowing tiles reuse the
#: right-facing art and are mirrored when drawn.
FLUID_SHEET_POS = {
    LAVA_FLOW_DOWN: (0, 0), LAVA_FLOW_R1: (2, 0), LAVA_FLOW_R2: (4, 0), LAVA_FLOW_R3: (6, 0),
    LAVA_FLOW_L1: (2, 0), LAVA_FLOW_L2: (4, 0), LAVA_FLOW_L3: (6, 0),
    WATER_FLOW_DOWN: (0, 2), WATER_FLOW_R1: (2, 2), WATER_FLOW_R2: (4, 2), WATER_FLOW_R3: (6, 2),
    WATER_FLOW_L1: (2, 2), WATER_FLOW_L2: (4, 2), WATER_FLOW_L3: (6, 2),
}
FLOW_TILES = frozenset(FLUID_SHEET_POS)
MIRRORED_TILES = frozenset(
    (LAVA_FLOW_L1, LAVA_FLOW_L2, LAVA_FLOW_L3, WATER_FLOW_L1, WATER_FLOW_L2, WATER_FLOW_L3)
)

ITEM_SHEET_POS = {
    STICK: (0, 0), IRON_SWORD: (2, 0), COPPER_SWORD: (4, 0), IRON_PICKAXE: (6, 0),
    COPPER_PICKAXE: (8, 0), IRON_AXE: (10, 0), COPPER_AXE: (12, 0), COAL: (14, 0),
    COPPER: (0, 2), IRON: (2, 2), STONE_SWORD: (4, 2), STONE_PICKAXE: (6, 2),
    STONE_AXE: (8, 2), BUCKET_EMPTY: (10, 2), BUCKET_LAVA: (12, 2), BUCKET_WATER: (14, 2),
}
ITEMS = frozenset(ITEM_SHEET_POS)

#: The UI sheet holds three 2x2 tiles side by side on its top rows.
UI_EMPTY_X = 0
UI_EXIT_X = 2
UI_BG_X = 4
UI_BG_COLOUR = sprites.UI_SHEET[0][UI_BG_X]

# -- names ---------------------------------------------------------------

NAMES = {
    GRASS: "grass", DIRT: "dirt", STONE: "stone", WOOD: "log", LEAF: "leaves",
    COAL_ORE: "coal ore", IRON_ORE: "iron ore", COPPER_ORE: "copper ore",
    LAVA: "lava", WATER: "water", WOOD_PLANKS: "wood planks",
    CRAFTING_TABLE: "crafting table", COBBLESTONE: "cobblestone",
    FURNACE: "furnace", CLAY: "clay", SAND: "sand", BRICK: "brick",
    STICK: "stick", IRON_SWORD: "iron sword", COPPER_SWORD: "copper sword",
    IRON_PICKAXE: "iron pickaxe", COPPER_PICKAXE: "copper pickaxe",
    IRON_AXE: "iron axe", COPPER_AXE: "copper axe", COAL: "coal",
    COPPER: "copper", IRON: "iron", STONE_SWORD: "stone sword",
    STONE_PICKAXE: "stone pickaxe", STONE_AXE: "stone axe",
    BUCKET_EMPTY: "bucket", BUCKET_LAVA: "lava bucket", BUCKET_WATER: "water bucket",
}

# -- stacking ------------------------------------------------------------

TOOL_TYPES = frozenset((
    IRON_SWORD, COPPER_SWORD, STONE_SWORD,
    IRON_PICKAXE, COPPER_PICKAXE, STONE_PICKAXE,
    IRON_AXE, COPPER_AXE, STONE_AXE,
))
BUCKET_TYPES = frozenset((BUCKET_EMPTY, BUCKET_LAVA, BUCKET_WATER))
SINGLE_STACK_TYPES = TOOL_TYPES | BUCKET_TYPES
STACK_MAX = 16


def stack_max_for(kind: int) -> int:
    return 1 if kind in SINGLE_STACK_TYPES else STACK_MAX


# -- fluids --------------------------------------------------------------

LAVA_KIND = "lava"
WATER_KIND = "water"

DOWN = "D"
LEFTWARD = "L"
RIGHTWARD = "R"


class FluidMeta(NamedTuple):
    """What the flow simulation needs to know about one fluid tile."""

    fluid: str
    is_source: bool
    level: int
    direction: str | None


FLUID_META = {
    LAVA: FluidMeta(LAVA_KIND, True, 0, None),
    WATER: FluidMeta(WATER_KIND, True, 0, None),
    LAVA_FLOW_DOWN: FluidMeta(LAVA_KIND, False, 0, DOWN),
    LAVA_FLOW_R1: FluidMeta(LAVA_KIND, False, 1, RIGHTWARD),
    LAVA_FLOW_R2: FluidMeta(LAVA_KIND, False, 2, RIGHTWARD),
    LAVA_FLOW_R3: FluidMeta(LAVA_KIND, False, 3, RIGHTWARD),
    LAVA_FLOW_L1: FluidMeta(LAVA_KIND, False, 1, LEFTWARD),
    LAVA_FLOW_L2: FluidMeta(LAVA_KIND, False, 2, LEFTWARD),
    LAVA_FLOW_L3: FluidMeta(LAVA_KIND, False, 3, LEFTWARD),
    WATER_FLOW_DOWN: FluidMeta(WATER_KIND, False, 0, DOWN),
    WATER_FLOW_R1: FluidMeta(WATER_KIND, False, 1, RIGHTWARD),
    WATER_FLOW_R2: FluidMeta(WATER_KIND, False, 2, RIGHTWARD),
    WATER_FLOW_R3: FluidMeta(WATER_KIND, False, 3, RIGHTWARD),
    WATER_FLOW_L1: FluidMeta(WATER_KIND, False, 1, LEFTWARD),
    WATER_FLOW_L2: FluidMeta(WATER_KIND, False, 2, LEFTWARD),
    WATER_FLOW_L3: FluidMeta(WATER_KIND, False, 3, LEFTWARD),
}
FLUIDS = frozenset(FLUID_META)
SOURCE_OF = {LAVA_KIND: LAVA, WATER_KIND: WATER}

_FLOW_TABLE = {
    LAVA_KIND: {
        DOWN: (LAVA_FLOW_DOWN,),
        LEFTWARD: (None, LAVA_FLOW_L1, LAVA_FLOW_L2, LAVA_FLOW_L3),
        RIGHTWARD: (None, LAVA_FLOW_R1, LAVA_FLOW_R2, LAVA_FLOW_R3),
    },
    WATER_KIND: {
        DOWN: (WATER_FLOW_DOWN,),
        LEFTWARD: (None, WATER_FLOW_L1, WATER_FLOW_L2, WATER_FLOW_L3),
        RIGHTWARD: (None, WATER_FLOW_R1, WATER_FLOW_R2, WATER_FLOW_R3),
    },
}


def flow_tile_for(fluid: str, level: int, direction: str | None) -> int:
    """The flowing tile for a fluid at a taper level. Level 0 always falls."""
    if level == 0:
        return _FLOW_TABLE[fluid][DOWN][0]
    return _FLOW_TABLE[fluid][direction][level]


def is_lava(kind: int) -> bool:
    meta = FLUID_META.get(kind)
    return meta is not None and meta.fluid == LAVA_KIND


def is_water(kind: int) -> bool:
    meta = FLUID_META.get(kind)
    return meta is not None and meta.fluid == WATER_KIND


def solid(kind: int) -> bool:
    """Anything you cannot walk or fall through."""
    return kind != SKY and kind not in FLUIDS


# -- fire ----------------------------------------------------------------

FLAMMABLE = frozenset((WOOD, WOOD_PLANKS, CRAFTING_TABLE))

# -- digging -------------------------------------------------------------

#: Milliseconds of held Backspace to break each block with bare hands.
BREAK_TIME_MS = {
    LEAF: 1000, GRASS: 1500, DIRT: 1500, SAND: 1500, CLAY: 1750,
    WOOD_PLANKS: 2250, WOOD: 2500, CRAFTING_TABLE: 2500, BRICK: 3000,
    COBBLESTONE: 3750, STONE: 4000, COAL_ORE: 4000, IRON_ORE: 4500,
    COPPER_ORE: 4500, FURNACE: 4500,
}
DEFAULT_BREAK_MS = 2500

AXE_BLOCKS = frozenset((WOOD, WOOD_PLANKS, CRAFTING_TABLE))
AXE_MULT = {STONE_AXE: 0.5, COPPER_AXE: 0.35, IRON_AXE: 0.22}
PICKAXE_BLOCKS = frozenset((STONE, COBBLESTONE, COAL_ORE, IRON_ORE, COPPER_ORE, FURNACE, BRICK))
PICKAXE_MULT = {STONE_PICKAXE: 0.5, COPPER_PICKAXE: 0.35, IRON_PICKAXE: 0.22}


def break_time_ms(kind: int, held: int | None = None) -> float:
    """How long a block takes to break with what is in hand."""
    base = BREAK_TIME_MS.get(kind, DEFAULT_BREAK_MS)
    if held is not None:
        if kind in AXE_BLOCKS and held in AXE_MULT:
            return base * AXE_MULT[held]
        if kind in PICKAXE_BLOCKS and held in PICKAXE_MULT:
            return base * PICKAXE_MULT[held]
    return base


# -- art lookups ---------------------------------------------------------


def tile_art(kind: int) -> tuple[tuple, int, int, bool]:
    """``(sheet, sx, sy, mirrored)`` for any block or item."""
    if kind in ITEMS:
        sx, sy = ITEM_SHEET_POS[kind]
        return sprites.ITEM_SHEET, sx, sy, False
    if kind in FLOW_TILES:
        sx, sy = FLUID_SHEET_POS[kind]
        return sprites.FLUID_SHEET, sx, sy, kind in MIRRORED_TILES
    sx, sy = SHEET_POS[kind]
    return sprites.BLOCK_SHEET, sx, sy, False


def _average(sheet, sx: int, sy: int) -> tuple[int, int, int]:
    samples = [
        sheet[sy + dy][sx + dx]
        for dy in range(2)
        for dx in range(2)
        if sheet[sy + dy][sx + dx] is not None
    ]
    if not samples:
        return (128, 128, 128)
    n = len(samples)
    return tuple(round(sum(p[i] for p in samples) / n) for i in range(3))


#: The one-pixel colour a dropped item is drawn with.
AVERAGE_COLOUR = {
    kind: _average(*tile_art(kind)[:3])
    for kind in list(SHEET_POS) + list(ITEM_SHEET_POS)
}
