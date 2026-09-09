"""What the world does on its own: fluids flow, fire burns, grass grows.

Each simulation runs over a box around the player, ``BLOCK_SIM_RADIUS``
blocks each way. The HTML scanned whole columns from sky to core; that
is far more than Python can afford several times a second and nothing
outside the box is ever on the panel, so the box is bounded vertically
too. Everything inside behaves exactly as it did.

Cells are read straight out of the chunk columns rather than through
:meth:`World.get`: a per-cell call is most of the cost of a scan.
"""

from __future__ import annotations

import random

from . import tiles
from .terrain import LAYERS, WORLD_H, World
from .tiles import (
    DOWN,
    FLUID_META,
    LAVA_KIND,
    LEFTWARD,
    RIGHTWARD,
    SKY,
    WATER_KIND,
    flow_tile_for,
)

BLOCK_SIM_RADIUS = 32

#: About 4.5 s at the 220 ms fluid tick.
BURN_DURATION_TICKS = 30

GRASS_SPREAD_CHANCE = 0.12
GRASS_DECAY_TICKS = 24

STICK_IGNITE_TAPS = 5
STICK_IGNITE_WINDOW_MS = 600

_KINDS_OF = {
    LAVA_KIND: frozenset(k for k, m in FLUID_META.items() if m.fluid == LAVA_KIND),
    WATER_KIND: frozenset(k for k, m in FLUID_META.items() if m.fluid == WATER_KIND),
}


class _Box:
    """The columns around a point, indexed by world x, with edge rows."""

    def __init__(self, world: World, layer: int, cx: int, cy: int) -> None:
        self.x_min = cx - BLOCK_SIM_RADIUS
        self.x_max = cx + BLOCK_SIM_RADIUS
        self.y_min = max(0, cy - BLOCK_SIM_RADIUS)
        self.y_max = min(WORLD_H - 1, cy + BLOCK_SIM_RADIUS)
        # One extra column each side so neighbours at the edge resolve.
        self.columns = {
            x: world.column(layer, x) for x in range(self.x_min - 1, self.x_max + 2)
        }

    def get(self, x: int, y: int) -> int:
        if y < 0:
            return SKY
        if y >= WORLD_H:
            return tiles.STONE
        return self.columns[x][y]

    def columns_touching(self, kinds: frozenset) -> list:
        """The x of every column in the box that, or whose neighbour,
        holds one of ``kinds`` within the box's rows.

        Most columns near the surface hold no fluid at all, and a set
        built from a byte slice is a C loop; scanning only where there is
        something to scan cuts a tick from several milliseconds to one.
        """
        lo, hi = self.y_min, self.y_max + 1
        hits = {
            x for x, column in self.columns.items() if set(column[lo:hi]) & kinds
        }
        return [
            x for x in range(self.x_min, self.x_max + 1)
            if x in hits or x - 1 in hits or x + 1 in hits
        ]


# -- fluids ----------------------------------------------------------------


def simulate_fluids(world: World, cx: int, cy: int) -> None:
    """One flow step for water and lava on both layers."""
    for layer in LAYERS:
        _simulate_fluid_layer(world, layer, WATER_KIND, cx, cy)
        _simulate_fluid_layer(world, layer, LAVA_KIND, cx, cy)


def _simulate_fluid_layer(world: World, layer: int, fluid: str, cx: int, cy: int) -> None:
    """Spread, taper, fall and recede one fluid on one layer.

    Sources are permanent. A flowing tile fed from above is a falling
    column; otherwise it takes the lowest taper level offered by a
    neighbour, up to 3 on solid ground and 1 in mid-air, and is removed
    when nothing feeds it. Empty air next to two sources becomes a source.
    """
    box = _Box(world, layer, cx, cy)
    get = box.get
    additions: list = []
    removals: list = []
    solid = tiles.solid

    def supported(x: int, y: int) -> bool:
        return solid(get(x, y + 1))

    def feeds_sideways(nx: int, ny: int, meta) -> bool:
        return not (meta.direction == DOWN and not supported(nx, ny))

    def best_feed(x: int, y: int):
        max_level = 3 if supported(x, y) else 1
        best_level, best_dir = 99, None
        left = FLUID_META.get(get(x - 1, y))
        if left is not None and left.fluid == fluid and feeds_sideways(x - 1, y, left):
            lv = 0 if left.is_source else left.level
            if lv + 1 <= max_level and lv + 1 < best_level:
                best_level, best_dir = lv + 1, RIGHTWARD
        right = FLUID_META.get(get(x + 1, y))
        if right is not None and right.fluid == fluid and feeds_sideways(x + 1, y, right):
            lv = 0 if right.is_source else right.level
            if lv + 1 <= max_level and lv + 1 < best_level:
                best_level, best_dir = lv + 1, LEFTWARD
        return best_level, best_dir, max_level

    for x in box.columns_touching(_KINDS_OF[fluid]):
        column = box.columns[x]
        for y in range(box.y_min, box.y_max + 1):
            t = column[y]
            meta = FLUID_META.get(t)
            if meta is not None and meta.fluid == fluid:
                if meta.is_source:
                    continue
                above = FLUID_META.get(get(x, y - 1))
                if above is not None and above.fluid == fluid:
                    if meta.direction != DOWN:
                        additions.append((x, y, 0, DOWN, False))
                    continue
                level, direction, max_level = best_feed(x, y)
                if level > max_level:
                    removals.append((x, y))
                elif level != meta.level or direction != meta.direction:
                    additions.append((x, y, level, direction, False))
            elif t == SKY:
                sources = 0
                for nt in (get(x, y - 1), get(x, y + 1), get(x - 1, y), get(x + 1, y)):
                    n_meta = FLUID_META.get(nt)
                    if n_meta is not None and n_meta.fluid == fluid and n_meta.is_source:
                        sources += 1
                if sources >= 2:
                    additions.append((x, y, 0, None, True))
                    continue
                above = FLUID_META.get(get(x, y - 1))
                if above is not None and above.fluid == fluid:
                    additions.append((x, y, 0, DOWN, False))
                    continue
                level, direction, max_level = best_feed(x, y)
                if level <= max_level:
                    additions.append((x, y, level, direction, False))

    for x, y in removals:
        world.set(layer, x, y, SKY)
    for x, y, level, direction, become_source in additions:
        if become_source:
            world.set(layer, x, y, tiles.SOURCE_OF[fluid])
        else:
            world.set(layer, x, y, flow_tile_for(fluid, level, direction))


# -- fire ------------------------------------------------------------------


def _touches(box: _Box, x: int, y: int, test) -> bool:
    return (
        test(box.get(x, y - 1))
        or test(box.get(x, y + 1))
        or test(box.get(x - 1, y))
        or test(box.get(x + 1, y))
    )


def simulate_fire(world: World, cx: int, cy: int) -> None:
    """Ignite flammables touching lava; burn, bake clay, go out in water."""
    burning = world.burning
    boxes = {}
    for layer in LAYERS:
        box = _Box(world, layer, cx, cy)
        boxes[layer] = box
        flammable = tiles.FLAMMABLE
        for x in box.columns_touching(flammable):
            column = box.columns[x]
            for y in range(box.y_min, box.y_max + 1):
                if column[y] not in flammable:
                    continue
                key = (layer, x, y)
                if key in burning:
                    continue
                if _touches(box, x, y, tiles.is_lava):
                    burning[key] = BURN_DURATION_TICKS

    for key, ticks_left in list(burning.items()):
        layer, x, y = key
        if abs(x - cx) > BLOCK_SIM_RADIUS:
            continue  # out of range this tick; revisited later
        if world.get(layer, x, y) not in tiles.FLAMMABLE:
            del burning[key]  # mined or changed out from under the fire
            continue
        for nx, ny in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            if world.get(layer, nx, ny) == tiles.CLAY:
                world.set(layer, nx, ny, tiles.BRICK)
        box = boxes[layer]
        in_box = box.x_min - 1 <= x <= box.x_max + 1
        touching_water = (
            _touches(box, x, y, tiles.is_water)
            if in_box
            else any(
                tiles.is_water(world.get(layer, nx, ny))
                for nx, ny in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y))
            )
        )
        if touching_water:
            del burning[key]  # extinguished; the block survives
        elif ticks_left <= 1:
            world.set(layer, x, y, SKY)
            del burning[key]
        else:
            burning[key] = ticks_left - 1


# -- grass -----------------------------------------------------------------


def simulate_grass(world: World, cx: int, cy: int, rng: random.Random) -> None:
    """Grass dies under cover and spreads onto sunlit dirt."""
    from .terrain import GRASS_LINE_Y

    covered = world.grass_covered
    solid = tiles.solid
    GRASS, DIRT = tiles.GRASS, tiles.DIRT
    for layer in LAYERS:
        box = _Box(world, layer, cx, cy)
        get = box.get

        grassy = box.columns_touching(frozenset((GRASS,)))
        for x in grassy:
            column = box.columns[x]
            for y in range(box.y_min, box.y_max + 1):
                if column[y] != GRASS:
                    continue
                key = (layer, x, y)
                if solid(get(x, y - 1)):
                    ticks = covered.get(key, 0) + 1
                    if ticks >= GRASS_DECAY_TICKS:
                        world.set(layer, x, y, DIRT)
                        covered.pop(key, None)
                    else:
                        covered[key] = ticks
                elif key in covered:
                    del covered[key]

        additions = []
        for x in grassy:
            column = box.columns[x]
            for y in range(box.y_min, box.y_max + 1):
                if column[y] != DIRT:
                    continue
                if solid(get(x, y - 1)):
                    continue
                if y <= GRASS_LINE_Y:
                    continue
                borders_grass = (
                    get(x - 1, y) == GRASS or get(x + 1, y) == GRASS
                    or get(x, y - 1) == GRASS or get(x, y + 1) == GRASS
                    or get(x - 1, y - 1) == GRASS or get(x + 1, y - 1) == GRASS
                    or get(x - 1, y + 1) == GRASS or get(x + 1, y + 1) == GRASS
                )
                if borders_grass and rng.random() < GRASS_SPREAD_CHANCE:
                    additions.append((x, y))
        for x, y in additions:
            world.set(layer, x, y, GRASS)


# -- a stick ---------------------------------------------------------------


class StickLighter:
    """Counts quick taps on one block; enough of them light it.

    Tapping a different block, or pausing, starts the count again.
    """

    def __init__(self) -> None:
        self._key = None
        self._count = 0
        self._time = 0.0

    def tap(self, world: World, layer: int, x: int, y: int, now_ms: float) -> bool:
        key = (layer, x, y)
        if key == self._key and now_ms - self._time < STICK_IGNITE_WINDOW_MS:
            self._count += 1
        else:
            self._key = key
            self._count = 1
        self._time = now_ms
        if self._count >= STICK_IGNITE_TAPS:
            world.burning[key] = BURN_DURATION_TICKS
            self._key = None
            self._count = 0
            return True
        return False
