"""The world: a looping strip of terrain, generated a chunk at a time.

Heights, oceans, lakes and trees are pure functions of a column and the
seed. Chunks are 32 columns wide and made the first time anything looks
at them; they are never thrown away, because a chunk holds the player's
edits and regenerating it would silently undo them.

Rows count downwards: row 0 is the top of the sky and row 1249 the core.
"""

from __future__ import annotations

import math

from . import tiles
from .noise import (
    WORLD_PERIOD,
    WORLD_RADIUS,
    hash1,
    hash2,
    noise1d,
    wrap_x,
)

WORLD_H = 1250
#: Ground sits near the bottom of the sky; everything above is air.
SURFACE_BASE = 250
#: Grass gives way to bare stone a little below the cloud band.
GRASS_LINE_Y = (SURFACE_BASE - 30) + 8
#: Trees stop even earlier.
TREE_LINE_Y = GRASS_LINE_Y + 10
SEA_LEVEL = SURFACE_BASE + 8

TERRAIN_AMPLITUDE = 16
MOUNTAIN_MAX_FRONT = 68
MOUNTAIN_SHARPNESS = 3.6
COAST_BAND = 0.015

TREE_CELL_W = 6
CHUNK_W = 32

FRONT = 0
BACK = 1
LAYERS = (FRONT, BACK)

LAKE_CLAY_CHANCE = 0.35
OCEAN_CLAY_CHANCE = 0.12

#: The tree canopy, as rows of x offsets above the trunk's foot.
CANOPY_ROWS = (
    (-6, (-1, 0, 1)),
    (-5, (-2, -1, 0, 1, 2)),
    (-4, (-2, -1, 1, 2)),
    (-3, (-2, -1, 1, 2)),
)


class Generator:
    """Everything that is a pure function of ``(x, seed)``."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._front: dict[int, int] = {}
        self._back: dict[int, int] = {}

    # -- noise ---------------------------------------------------------

    def _noise(self, x: float, seed: int, freq: float) -> float:
        return noise1d(x, seed, freq, self.seed)

    def _hash1(self, x: int, seed: int) -> float:
        return hash1(x, seed, self.seed)

    def hash2(self, x: int, y: int, seed: int) -> float:
        return hash2(x, y, seed, self.seed)

    def terrain_detail(self, x: int) -> float:
        return (
            self._noise(x, 1, 1 / 9) * 0.45
            + self._noise(x, 2, 1 / 22) * 0.35
            + self._noise(x, 12, 1 / 55) * 0.20
        )

    def mountain_field(self, x: int, seed: int, sharpness: float) -> float:
        n = self._noise(x, seed, 1 / 220)
        t = max(0.0, n - 0.5) / 0.5
        return t**sharpness

    # -- oceans --------------------------------------------------------

    def continent_mask(self, x: int) -> float:
        return self._noise(x, 6, 1 / 1600)

    def ocean_factor(self, x: float) -> float:
        """0 on dry land, 1 in open ocean, a short ramp between."""
        m = self.continent_mask(wrap_x(x))
        return max(0.0, min(1.0, (m - (0.5 - COAST_BAND)) / (2 * COAST_BAND)))

    def ocean_floor(self, x: int) -> float:
        rolling = self._noise(x, 7, 1 / 260)
        return min(WORLD_H - 3, SEA_LEVEL + 6 + rolling * 12)

    # -- heights -------------------------------------------------------

    def front_height(self, raw_x: float) -> int:
        x = int(wrap_x(raw_x))
        cached = self._front.get(x)
        if cached is not None:
            return cached
        detail = self.terrain_detail(x)
        mountain = self.mountain_field(x, 5, MOUNTAIN_SHARPNESS) * MOUNTAIN_MAX_FRONT
        land = _round(SURFACE_BASE + detail * TERRAIN_AMPLITUDE - mountain)
        ocean = self.ocean_factor(x)
        if ocean <= 0:
            height = land
        else:
            height = _round(land + (self.ocean_floor(x) - land) * ocean)
        self._front[x] = height
        return height

    def back_height(self, raw_x: float) -> int:
        """The background's ground: the same landform, jittered, never
        more than five rows above the front."""
        x = int(wrap_x(raw_x))
        cached = self._back.get(x)
        if cached is not None:
            return cached
        detail = self.terrain_detail(x)
        if self._hash1(x, 3) < 0.35:
            j = -1 if self._hash1(x, 4) < 0.5 else 1
        else:
            j = 0
        mountain = self.mountain_field(x, 5, MOUNTAIN_SHARPNESS) * MOUNTAIN_MAX_FRONT
        land = _round(SURFACE_BASE + detail * TERRAIN_AMPLITUDE + j - mountain)
        ocean = self.ocean_factor(x)
        raw = land if ocean <= 0 else _round(land + (self.ocean_floor(x) - land) * ocean)
        height = max(raw, self.front_height(x) - 5)
        self._back[x] = height
        return height

    def height_for(self, layer: int):
        return self.back_height if layer == BACK else self.front_height

    def is_water_column(self, raw_x: float, layer: int = FRONT) -> bool:
        """True where the ground naturally sits below sea level."""
        return self.height_for(layer)(raw_x) > SEA_LEVEL

    def surface_ref(self, raw_x: float) -> int:
        """The row a camera should treat as the surface: the water's top
        over the ocean, else the ground."""
        return SEA_LEVEL if self.ocean_factor(raw_x) > 0 else self.front_height(raw_x)

    # -- trees ---------------------------------------------------------

    def tree_in_cell(self, cell: int, layer: int):
        """``(x, surface)`` of the tree in this six-wide cell, or None."""
        background = layer == BACK
        chance = 0.55 if background else 0.22
        seed = 101 if background else 100
        if self._hash1(cell, seed) > chance:
            return None
        anchor = cell * TREE_CELL_W + 2 + math.floor(self._hash1(cell, seed + 2) * (TREE_CELL_W - 4))
        height = self.height_for(layer)
        surf = height(anchor)
        if surf - 6 < 0:
            return None
        if surf > SEA_LEVEL:
            return None
        if surf <= TREE_LINE_Y:
            return None
        for d in range(-2, 3):
            if self.is_water_column(anchor + d, layer):
                return None
        return anchor, surf

    # -- spawn ---------------------------------------------------------

    def find_spawn_x(self) -> int:
        """The dry column nearest the seed's pick."""
        start = self.seed % 1000000
        for i in range(20000):
            if not self.is_water_column(start + i):
                return int(wrap_x(start + i))
            if not self.is_water_column(start - i):
                return int(wrap_x(start - i))
        return int(wrap_x(start))

    # -- chunks --------------------------------------------------------

    def generate_chunk(self, chunk: int, layer: int) -> list:
        """A chunk as ``CHUNK_W`` columns, each a ``bytearray`` of ``WORLD_H``."""
        background = layer == BACK
        height = self.height_for(layer)
        start = chunk * CHUNK_W
        grid = [bytearray(WORLD_H) for _ in range(CHUNK_W)]

        water = tiles.SKY if background else tiles.WATER
        for lx in range(CHUNK_W):
            x = start + lx
            column = grid[lx]
            surf = height(x)
            flooded = self.is_water_column(x, layer)
            near_shore = not flooded and (
                self.is_water_column(x - 1, layer) or self.is_water_column(x + 1, layer)
            )
            sandy = flooded or near_shore
            ocean = self.ocean_factor(x) > 0
            bare = not sandy and surf <= GRASS_LINE_Y

            if flooded and SEA_LEVEL < surf:
                column[SEA_LEVEL:surf] = bytes((water,)) * (surf - SEA_LEVEL)
            if 0 <= surf < WORLD_H:
                if bare:
                    column[surf] = tiles.STONE
                elif not sandy:
                    column[surf] = tiles.GRASS
                elif flooded:
                    column[surf] = self._bed_tile(x, surf, ocean)
                else:
                    column[surf] = tiles.SAND
            for y in range(max(0, surf + 1), min(WORLD_H, surf + 3)):
                if bare:
                    column[y] = tiles.STONE
                elif not sandy:
                    column[y] = tiles.DIRT
                elif flooded:
                    column[y] = self._bed_tile(x, y, ocean)
                else:
                    column[y] = tiles.SAND
            deep = max(0, surf + 3)
            if deep < WORLD_H:
                column[deep:] = bytes((tiles.STONE,)) * (WORLD_H - deep)

        self._plant_trees(grid, start, layer)
        self._sprinkle_ore_and_lava(grid, start, layer)
        return grid

    def _bed_tile(self, x: int, y: int, ocean: bool) -> int:
        r = self.hash2(x, y, 250)
        return tiles.CLAY if r < (OCEAN_CLAY_CHANCE if ocean else LAKE_CLAY_CHANCE) else tiles.SAND

    def _plant_trees(self, grid: list, start: int, layer: int) -> None:
        first = math.floor((start - 3) / TREE_CELL_W)
        last = math.floor((start + CHUNK_W + 3) / TREE_CELL_W)
        for cell in range(first, last + 1):
            tree = self.tree_in_cell(cell, layer)
            if tree is None:
                continue
            x, surf = tree
            for dy, dxs in CANOPY_ROWS:
                for d in dxs:
                    lx = x + d - start
                    if 0 <= lx < CHUNK_W:
                        grid[lx][surf + dy] = tiles.LEAF
            lx = x - start
            if 0 <= lx < CHUNK_W:
                for dy in range(-4, 0):
                    grid[lx][surf + dy] = tiles.WOOD

    def _sprinkle_ore_and_lava(self, grid: list, start: int, layer: int) -> None:
        """Ore in the stone, and stone giving way to lava towards the core.

        The hash is inlined: this visits every stone cell in the chunk,
        and a function call per cell is most of the cost.
        """
        seed = 200 if layer == BACK else 199
        seed_term = (seed + self.seed) * 2246822519
        stone = tiles.STONE
        span = WORLD_H - SURFACE_BASE
        for lx in range(CHUNK_W):
            column = grid[lx]
            x = int(wrap_x(start + lx))
            x_term = x * 374761393
            for y in range(SURFACE_BASE, WORLD_H):
                if column[y] != stone:
                    continue
                depth = (y - SURFACE_BASE) / span
                lava_chance = 1.0 if y >= WORLD_H - 1 else depth * depth * depth
                h = (x_term + y * 668265263 + seed_term) & 0xFFFFFFFF
                h = (h * 2654435761) & 0xFFFFFFFF
                h = (h ^ (h >> 15)) & 0xFFFFFFFF
                h = (h * 2246822519) & 0xFFFFFFFF
                h = (h ^ (h >> 13)) & 0xFFFFFFFF
                r = h / 4294967296.0
                if r < lava_chance:
                    column[y] = tiles.LAVA
                    continue
                rr = (r - lava_chance) / (1 - lava_chance)
                if rr < 0.025:
                    column[y] = tiles.COAL_ORE
                elif rr < 0.04:
                    column[y] = tiles.IRON_ORE
                elif rr < 0.05:
                    column[y] = tiles.COPPER_ORE


class World:
    """Two layers of blocks, plus the fire and grass clocks that ride on them."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.gen = Generator(seed)
        self._chunks: dict = {}
        #: ``(layer, x, y) -> ticks of burning left``.
        self.burning: dict = {}
        #: ``(layer, x, y) -> ticks a grass block has been covered``.
        self.grass_covered: dict = {}

    def chunk(self, layer: int, index: int) -> list:
        key = (layer, index)
        grid = self._chunks.get(key)
        if grid is None:
            grid = self.gen.generate_chunk(index, layer)
            self._chunks[key] = grid
        return grid

    @property
    def chunks_loaded(self) -> int:
        return len(self._chunks)

    def get(self, layer: int, x: int, y: int) -> int:
        """The block at a cell; sky above the world, stone below it."""
        if y < 0:
            return tiles.SKY
        if y >= WORLD_H:
            return tiles.STONE
        wx = int(wrap_x(x))
        index = wx // CHUNK_W
        return self.chunk(layer, index)[wx - index * CHUNK_W][y]

    def set(self, layer: int, x: int, y: int, kind: int) -> None:
        if not 0 <= y < WORLD_H:
            return
        wx = int(wrap_x(x))
        index = wx // CHUNK_W
        self.chunk(layer, index)[wx - index * CHUNK_W][y] = kind

    def block(self, x: int, y: int) -> int:
        return self.get(FRONT, x, y)

    def solid_at(self, x: int, y: int) -> bool:
        return tiles.solid(self.get(FRONT, x, y))

    def fluid_at(self, x: int, y: int) -> bool:
        return self.get(FRONT, x, y) in tiles.FLUIDS

    def is_open_water_surface(self, x: int, y: int) -> bool:
        """Water with nothing but sky directly above it."""
        return tiles.is_water(self.get(FRONT, x, y)) and self.get(FRONT, x, y - 1) == tiles.SKY


def _round(value: float) -> int:
    return math.floor(value + 0.5)


__all__ = [
    "BACK",
    "CHUNK_W",
    "FRONT",
    "GRASS_LINE_Y",
    "Generator",
    "LAYERS",
    "SEA_LEVEL",
    "SURFACE_BASE",
    "TREE_LINE_Y",
    "WORLD_H",
    "WORLD_PERIOD",
    "WORLD_RADIUS",
    "World",
    "wrap_x",
]
