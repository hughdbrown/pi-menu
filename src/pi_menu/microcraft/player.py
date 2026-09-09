"""The player: a one-block box that walks, jumps, swims, digs and builds.

Physics is the HTML's, tuned per 60 Hz frame: gravity ``0.02``, walking
``0.08``, a jump of ``0.32`` blocks a frame. The session runs three of
these steps per 20 Hz tick, so the game feels the same on the panel as
it did in the browser. Collision checks the box's true edges against
the front layer, x first and then y, so a corner never snags.

Also here: the things the player does to the world at the cursor --
breaking a block over time, placing one, scooping and pouring buckets
-- and the item drops that appear when something has nowhere to go.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from . import tiles
from .inventory import Inventory, Stack
from .noise import WORLD_RADIUS, round_half_up, wrap_x
from .sim import StickLighter
from .terrain import FRONT, WORLD_H, World

BLOCK = 2
COLS = 8
ROWS = 8

GRAV = 0.02
MOVE = 0.08
JUMP = 0.32
MAX_FALL = 0.4
MAX_FALL_IN_FLUID = 0.08
MAX_SWIM_UP = 0.12
#: One real pixel, in blocks.
PIXEL = 1 / BLOCK
#: After this long without moving, the player snaps to the pixel grid.
IDLE_SNAP_MS = 1000
#: How long one physics step stands for.
STEP_MS = 1000 / 60

LEFT = "left"
RIGHT = "right"
JUMP_KEY = "jump"

DROP_PICKUP_DELAY_MS = 300
DROP_GRAV = 0.05
DROP_MAX_FALL = 0.5

PLAYER_COLOUR = (255, 231, 94)


def row_span(y: float) -> tuple:
    """The rows a one-block box at y actually covers."""
    return (math.floor(y), math.floor(y + 0.999))


def col_span(x: float) -> tuple:
    return (math.floor(x), math.floor(x + 0.999))


def snap_to_pixel(v: float) -> float:
    return round_half_up(v / PIXEL) * PIXEL


def camera(player_x: float, player_y: float) -> tuple:
    """The top-left block of the view that centres the player."""
    cam_x = round_half_up(player_x - COLS / 2)
    cam_y = max(0, min(WORLD_H - ROWS, round_half_up(player_y - ROWS / 2)))
    return cam_x, cam_y


class Player:
    """Position and velocity in blocks; the box spans (x, y) to (x+1, y+1)."""

    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.hp = 10
        self.idle_ms = 0.0

    def step(
        self,
        world: World,
        held: frozenset,
        swimmable: Callable[[int, int], bool],
        dt_ms: float = STEP_MS,
    ) -> None:
        """One 60 Hz step of walking, jumping, swimming and falling.

        ``swimmable(x, y)`` says whether a cell counts as water for
        swimming -- fluids, plus the airspace a wave has risen into.
        """
        if LEFT in held:
            self.vx = -MOVE
        elif RIGHT in held:
            self.vx = MOVE
        else:
            self.vx *= 0.5

        rows = row_span(self.y)
        cols = col_span(self.x)
        in_fluid = any(swimmable(c, r) for c in cols for r in rows)
        on_ground = any(world.solid_at(c, math.floor(self.y + 1.001)) for c in cols)

        if JUMP_KEY in held:
            if on_ground:
                self.vy = -JUMP
            elif in_fluid:
                self.vy -= GRAV * 2.2  # a stroke against buoyancy

        self.vy += GRAV * 0.35 if in_fluid else GRAV
        max_fall = MAX_FALL_IN_FLUID if in_fluid else MAX_FALL
        if self.vy > max_fall:
            self.vy = max_fall
        if in_fluid and self.vy < -MAX_SWIM_UP:
            self.vy = -MAX_SWIM_UP

        nx = self.x + self.vx
        if self.vx != 0:
            rows = row_span(self.y)
            if self.vx > 0:
                edge = math.floor(nx + 1)
                if any(world.solid_at(edge, r) for r in rows):
                    nx = edge - 1
            else:
                edge = math.floor(nx)
                if any(world.solid_at(edge, r) for r in rows):
                    nx = edge + 1
        self.x = wrap_x(nx)

        ny = self.y + self.vy
        cols = col_span(self.x)
        if self.vy > 0:
            edge = math.floor(ny + 1)
            if any(world.solid_at(c, edge) for c in cols):
                ny = edge - 1
                self.vy = 0.0
        elif self.vy < 0:
            edge = math.floor(ny)
            if any(world.solid_at(c, edge) for c in cols):
                ny = edge + 1
                self.vy = 0.0
        self.y = ny

        # Through the core and out at the antipode.
        if self.y > WORLD_H - 2:
            self.x = wrap_x(self.x + WORLD_RADIUS)
            self.y = world.gen.front_height(round_half_up(self.x)) - 1
            self.vy = 0.0

        moving = bool(held & {LEFT, RIGHT, JUMP_KEY}) or abs(self.vx) > 0.001 or abs(self.vy) > 0.001
        if moving:
            self.idle_ms = 0.0
        else:
            self.idle_ms += dt_ms
            if self.idle_ms >= IDLE_SNAP_MS:
                self.x = snap_to_pixel(self.x)
                self.y = snap_to_pixel(self.y)

    def covers(self, x: int, y: int) -> bool:
        return x in col_span(self.x) and y in row_span(self.y)


# -- dropped items -------------------------------------------------------------


class ItemDrop:
    __slots__ = ("kind", "count", "x", "y", "vy", "landed", "born_ms")

    def __init__(self, kind: int, count: int, x: int, y: float, born_ms: float) -> None:
        self.kind, self.count, self.x, self.y = kind, count, x, y
        self.vy = 0.0
        self.landed = False
        self.born_ms = born_ms


class Drops:
    """Little pixels on the ground, waiting to be walked over."""

    def __init__(self) -> None:
        self.items: list = []

    def spawn(self, kind: int, count: int, x: float, y: float, now_ms: float) -> None:
        if count <= 0:
            return
        self.items.append(ItemDrop(kind, count, round_half_up(x), float(y), now_ms))

    def spawn_stacks(self, stacks: list, x: float, y: float, now_ms: float) -> None:
        for stack in stacks:
            self.spawn(stack.kind, stack.count, x, y, now_ms)

    def update(self, world: World, player: Player, inventory: Inventory, now_ms: float) -> None:
        """Fall until landed, then be picked up by a player with room."""
        p_cols, p_rows = col_span(player.x), row_span(player.y)
        for drop in list(self.items):
            if not drop.landed:
                drop.vy = min(drop.vy + DROP_GRAV, DROP_MAX_FALL)
                ny = drop.y + drop.vy
                edge = math.floor(ny + 1)
                if world.solid_at(drop.x, edge):
                    ny = edge - 1
                    drop.vy = 0.0
                    drop.landed = True
                drop.y = ny
                continue
            if now_ms - drop.born_ms < DROP_PICKUP_DELAY_MS:
                continue
            if drop.x not in p_cols or round_half_up(drop.y) not in p_rows:
                continue
            drop.count -= inventory.add_items(drop.kind, drop.count)
            if drop.count <= 0:
                self.items.remove(drop)


# -- breaking ------------------------------------------------------------------


class Breaker:
    """Progress on the one block being held-broken, if any."""

    def __init__(self) -> None:
        self.key: Optional[tuple] = None
        self.progress = 0.0

    def reset(self) -> None:
        self.key = None
        self.progress = 0.0

    def update(
        self,
        dt_ms: float,
        breaking: bool,
        target: Optional[tuple],
        layer: int,
        world: World,
        inventory: Inventory,
        drops: Drops,
        now_ms: float,
    ) -> None:
        """Advance while the break key is down on a breakable block;
        break it when its time is up, into the inventory or onto the
        ground."""
        if not breaking or target is None:
            self.reset()
            return
        wx, wy = target
        kind = world.get(layer, wx, wy)
        if kind == tiles.SKY or kind in tiles.FLUIDS:
            self.reset()
            return
        key = (layer, wx, wy)
        if self.key != key:
            self.key = key
            self.progress = 0.0
        self.progress += dt_ms
        held = inventory.held
        if self.progress >= tiles.break_time_ms(kind, held.kind if held else None):
            world.set(layer, wx, wy, tiles.SKY)
            if not inventory.pickup(kind):
                drops.spawn(kind, 1, wx, wy, now_ms)
            self.reset()

    def fraction(self, world: World, inventory: Inventory) -> float:
        if self.key is None:
            return 0.0
        layer, wx, wy = self.key
        kind = world.get(layer, wx, wy)
        held = inventory.held
        return min(1.0, self.progress / tiles.break_time_ms(kind, held.kind if held else None))


# -- placing ---------------------------------------------------------------------


def place_at(
    world: World,
    layer: int,
    wx: int,
    wy: int,
    player: Player,
    inventory: Inventory,
    lighter: StickLighter,
    now_ms: float,
) -> None:
    """Enter on a world cell: light it, scoop it, pour into it, or build on it."""
    held = inventory.held
    if held is None:
        return
    target = world.get(layer, wx, wy)

    if held.kind == tiles.STICK and target in tiles.FLAMMABLE:
        lighter.tap(world, layer, wx, wy, now_ms)
        return

    if held.kind == tiles.BUCKET_EMPTY:
        if tiles.is_water(target):
            world.set(layer, wx, wy, tiles.SKY)
            held.kind = tiles.BUCKET_WATER
            return
        if tiles.is_lava(target):
            world.set(layer, wx, wy, tiles.SKY)
            held.kind = tiles.BUCKET_LAVA
            return

    can_place = target == tiles.SKY or target in tiles.FLUIDS
    if not can_place or player.covers(wx, wy):
        return

    if held.kind in (tiles.BUCKET_WATER, tiles.BUCKET_LAVA):
        world.set(layer, wx, wy, tiles.WATER if held.kind == tiles.BUCKET_WATER else tiles.LAVA)
        held.kind = tiles.BUCKET_EMPTY
        return

    if held.kind not in tiles.ITEMS:
        world.set(layer, wx, wy, held.kind)
        inventory.drop_one_held()
