"""Screens, keys, the clock, and what the panel shows at any moment.

Five screens: the opening screen with its demo tour behind it, the
world, the inventory, the bench and the table. One cursor moves across
all of them, one button acts on whatever is under it, and the world
keeps simulating behind the opening screen but stands still while an
inventory screen is open, as in the HTML.

Nothing here knows a display exists. Like the other sessions it takes
a sink -- a callable handed a complete framebuffer -- and every tick
and every key press pushes one. Time is the session's own: ``tick``
advances a millisecond counter by the dt it is given, so a run with a
seeded RNG is repeatable and a test can step it by hand.
"""

from __future__ import annotations

import enum
import math
import random
import time
from typing import Callable, Optional

from . import render, sim
from .canvas import Canvas
from .demo import Demo
from .inventory import BACKPACK, CRAFT, HOTBAR, OUTPUT, TABLE, TABLE_OUTPUT, Inventory
from .player import (
    BLOCK,
    COLS,
    JUMP_KEY,
    LEFT,
    RIGHT,
    STEP_MS,
    Breaker,
    Drops,
    Player,
    camera,
    place_at,
)
from .sim import StickLighter
from .sky import DayClock, make_stars, moon_phase_frac
from .terrain import BACK, FRONT, WORLD_H, World
from . import tiles
from .weather import CLOUD_MAX_Y, Weather

Sink = Callable[[bytes], None]

TICK_HZ = 20
TICK_MS = 1000 / TICK_HZ

# Held keys.
BREAK = "break"
HELD_KEYS = frozenset((LEFT, RIGHT, JUMP_KEY, BREAK))
# Tapped keys.
CURSOR_LEFT = "cursor_left"
CURSOR_RIGHT = "cursor_right"
CURSOR_UP = "cursor_up"
CURSOR_DOWN = "cursor_down"
SELECT = "select"
INVENTORY = "inventory"
LAYER = "layer"
DROP = "drop"
BACK_KEY = "back"

FLUID_TICK_MS = 220
GRASS_TICK_MS = 500
WEATHER_TICK_MS = 250
RAIN_SPAWN_MS = 160

DROP_TAPS = 3
DROP_WINDOW_MS = 600

LAYER_NAMES = {FRONT: "front", BACK: "background"}


class Screen(enum.Enum):
    MENU = "menu"
    WORLD = "world"
    INVENTORY = "inventory"
    BENCH = "bench"
    TABLE = "table"


class Session:
    """One sitting in one world."""

    def __init__(
        self,
        sink: Sink,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._sink = sink
        self.rng = rng if rng is not None else random.Random()
        self.seed = seed if seed is not None else self.rng.randrange(2**31 - 1)
        self.wall_clock = wall_clock
        self.now_ms = 0.0

        self.world = World(self.seed)
        spawn_x = self.world.gen.find_spawn_x()
        self.player = Player(spawn_x, self.world.gen.front_height(spawn_x) - 1)
        self.inventory = Inventory()
        self.drops = Drops()
        self.breaker = Breaker()
        self.lighter = StickLighter()
        self.weather = Weather(self.world, self.rng, spawn_x)
        self.day = DayClock()
        self.day.anchor_noon(spawn_x, self.now_ms)
        self.stars = make_stars(self.rng)
        self.demo = Demo(self.world.gen, spawn_x)

        self.screen = Screen.MENU
        self.cursor = [8, 6]  # on the opening screen's play button
        self.active_layer = FRONT
        self._held: set = set()
        self._drop_taps = 0
        self._drop_time = -1e9
        self._fluid_acc = 0.0
        self._grass_acc = 0.0
        self._weather_acc = 0.0
        self._rain_acc = 0.0
        self.push()

    # -- input -----------------------------------------------------------------

    @property
    def held(self) -> frozenset:
        return frozenset(self._held)

    def press(self, key: str) -> None:
        """A key going down. Held keys stay down until :meth:`release`;
        the rest act at once."""
        if key in HELD_KEYS:
            self._held.add(key)
        elif key == CURSOR_LEFT:
            self.move_cursor(-1, 0)
        elif key == CURSOR_RIGHT:
            self.move_cursor(1, 0)
        elif key == CURSOR_UP:
            self.move_cursor(0, -1)
        elif key == CURSOR_DOWN:
            self.move_cursor(0, 1)
        elif key == SELECT:
            self.interact()
        elif key == INVENTORY:
            self.toggle_inventory()
        elif key == LAYER:
            self.toggle_layer()
        elif key == DROP:
            self._drop_tap()
        elif key == BACK_KEY:
            self.back()
        self.push()

    def release(self, key: str) -> None:
        self._held.discard(key)

    def select_slot(self, index: int) -> None:
        self.inventory.select_slot(index)
        self.push()

    def move_cursor(self, dx: int, dy: int) -> None:
        self.cursor[0] = max(0, min(15, self.cursor[0] + dx))
        self.cursor[1] = max(0, min(15, self.cursor[1] + dy))

    def toggle_layer(self) -> None:
        if self.screen is Screen.WORLD:
            self.active_layer = BACK if self.active_layer == FRONT else FRONT

    def toggle_inventory(self) -> None:
        if self.screen is Screen.WORLD:
            self._open(Screen.INVENTORY)
        elif self.screen is Screen.INVENTORY:
            self._close_inventory()

    def back(self) -> None:
        if self.screen is Screen.INVENTORY:
            self._close_inventory()
        elif self.screen is Screen.BENCH:
            self._close_bench()
        elif self.screen is Screen.TABLE:
            self._close_table()
        elif self.screen is Screen.WORLD:
            self.screen = Screen.MENU
            self.breaker.reset()

    def _drop_tap(self) -> None:
        """Q three times quickly drops one of the held item at the cursor."""
        if self.now_ms - self._drop_time < DROP_WINDOW_MS:
            self._drop_taps += 1
        else:
            self._drop_taps = 1
        self._drop_time = self.now_ms
        if self._drop_taps >= DROP_TAPS:
            self._drop_taps = 0
            self.drop_held()

    def drop_held(self) -> None:
        if self.screen is not Screen.WORLD:
            return
        if self.inventory.held is None:
            return
        target = self.cursor_world()
        x, y = target if target is not None else (self.player.x, self.player.y)
        kind = self.inventory.drop_one_held()
        self.drops.spawn(kind, 1, x, y, self.now_ms)

    # -- screens ---------------------------------------------------------------

    def _open(self, screen: Screen) -> None:
        self.screen = screen
        self.inventory.deselect()
        self.breaker.reset()

    def _close_inventory(self) -> None:
        self.inventory.deselect()
        self.screen = Screen.WORLD

    def _close_bench(self) -> None:
        leftovers = self.inventory.close_bench()
        self.drops.spawn_stacks(leftovers, self.player.x, self.player.y, self.now_ms)
        self.screen = Screen.WORLD

    def _close_table(self) -> None:
        leftovers = self.inventory.close_table()
        self.drops.spawn_stacks(leftovers, self.player.x, self.player.y, self.now_ms)
        self.screen = Screen.WORLD

    def cursor_world(self) -> Optional[tuple]:
        """The world cell under the cursor, or None above or below the world."""
        cam_x, cam_y = camera(self.player.x, self.player.y)
        wx = cam_x + self.cursor[0] // BLOCK
        wy = cam_y + self.cursor[1] // BLOCK
        if not 0 <= wy < WORLD_H:
            return None
        return wx, wy

    def interact(self) -> None:
        """Enter: the play button, a slot, a button, or the world."""
        cx, cy = self.cursor
        if self.screen is Screen.MENU:
            if render.point_in_button(cx, cy):
                self.screen = Screen.WORLD
            return
        if self.screen is Screen.INVENTORY:
            region, index = Inventory.hit_inventory(cx, cy)
            if region == "exit":
                self._close_inventory()
            elif region == "openCraft":
                self.screen = Screen.BENCH
                self.breaker.reset()
            elif region in (BACKPACK, HOTBAR):
                self.inventory.slot_click(region, index, self.now_ms)
            return
        if self.screen is Screen.BENCH:
            region, index = Inventory.hit_bench(cx, cy)
            if region == "exit":
                self._close_bench()
            elif region == OUTPUT:
                self.inventory.bench_output_click(self.now_ms)
            elif region in (CRAFT, BACKPACK, HOTBAR):
                self.inventory.slot_click(region, index, self.now_ms)
            return
        if self.screen is Screen.TABLE:
            region, index = Inventory.hit_table(cx, cy)
            if region == "exit":
                self._close_table()
            elif region == TABLE_OUTPUT:
                self.inventory.table_output_click(self.now_ms)
            elif region in (TABLE, BACKPACK, HOTBAR):
                self.inventory.slot_click(region, index, self.now_ms)
            return

        target = self.cursor_world()
        if target is None:
            return
        wx, wy = target
        held = self.inventory.held
        if (
            self.world.get(self.active_layer, wx, wy) == tiles.CRAFTING_TABLE
            and not (held is not None and held.kind == tiles.STICK)
        ):
            self._open(Screen.TABLE)
            return
        place_at(
            self.world, self.active_layer, wx, wy, self.player,
            self.inventory, self.lighter, self.now_ms,
        )

    # -- the clock -------------------------------------------------------------

    def tick(self, dt_ms: float = TICK_MS) -> None:
        """Advance everything on screen by ``dt_ms`` and push a frame."""
        self.now_ms += dt_ms
        if self.screen is Screen.MENU:
            self.drops.update(self.world, self.player, self.inventory, self.now_ms)
            self._simulate(dt_ms)
            self.demo.update(dt_ms)
            self.weather.settle_overcast(self.demo.cam_x + COLS / 2)
        elif self.screen is Screen.WORLD:
            steps = max(1, round(dt_ms / STEP_MS))
            swim = self._swimmable
            for _ in range(steps):
                self.player.step(self.world, self._physics_held(), swim, dt_ms / steps)
            self.breaker.update(
                dt_ms, BREAK in self._held, self.cursor_world(), self.active_layer,
                self.world, self.inventory, self.drops, self.now_ms,
            )
            self.drops.update(self.world, self.player, self.inventory, self.now_ms)
            self._simulate(dt_ms)
            self.weather.settle_overcast(self.player.x)
        self.push()

    def _physics_held(self) -> frozenset:
        return frozenset(k for k in self._held if k in (LEFT, RIGHT, JUMP_KEY))

    def _swimmable(self, x: int, y: int) -> bool:
        return self.weather.fluid_or_wave_at(x, y, self.now_ms / 1000.0)

    def _simulate(self, dt_ms: float) -> None:
        px = math.floor(self.player.x)
        py = math.floor(self.player.y)
        self._fluid_acc += dt_ms
        while self._fluid_acc >= FLUID_TICK_MS:
            sim.simulate_fluids(self.world, px, py)
            sim.simulate_fire(self.world, px, py)
            self._fluid_acc -= FLUID_TICK_MS
        self._grass_acc += dt_ms
        while self._grass_acc >= GRASS_TICK_MS:
            sim.simulate_grass(self.world, px, py, self.rng)
            self._grass_acc -= GRASS_TICK_MS
        cam_x = self.demo.cam_x if self.screen is Screen.MENU else camera(self.player.x, self.player.y)[0]
        self.weather.update_motion(dt_ms, cam_x)
        self._weather_acc += dt_ms
        while self._weather_acc >= WEATHER_TICK_MS:
            self.weather.tick(self.player.x)
            self._weather_acc -= WEATHER_TICK_MS
        self._rain_acc += dt_ms
        while self._rain_acc >= RAIN_SPAWN_MS:
            self.weather.spawn_rain(self.player.x, self.player.y)
            self._rain_acc -= RAIN_SPAWN_MS
        self.weather.update_rain(dt_ms, self.player.x, self.player.y, self.now_ms / 1000.0)
        self.weather.update_lightning(dt_ms, self.player.x, self.player.y)

    # -- output ----------------------------------------------------------------

    def moon_phase(self) -> float:
        return moon_phase_frac(self.wall_clock())

    def framebuffer(self) -> bytes:
        canvas = Canvas()
        if self.screen is Screen.MENU:
            demo = self.demo
            if demo.index == -1:
                demo.update(0)
            moon = demo.moon_phase if demo.moon_phase is not None else self.moon_phase()
            render.draw_world(
                canvas, self.world, self.weather, demo.cam_x, demo.cam_y,
                sky_frac=demo.time_frac, moon_phase=moon, stars=self.stars,
                now_ms=self.now_ms, ref_y=demo.cam_y + COLS / 2,
            )
            render.draw_menu(canvas)
        elif self.screen is Screen.INVENTORY:
            render.draw_inventory(canvas, self.inventory, self.now_ms)
        elif self.screen is Screen.BENCH:
            render.draw_bench(canvas, self.inventory, self.now_ms)
        elif self.screen is Screen.TABLE:
            render.draw_table(canvas, self.inventory, self.now_ms)
        else:
            cam_x, cam_y = camera(self.player.x, self.player.y)
            render.draw_world(
                canvas, self.world, self.weather, cam_x, cam_y,
                sky_frac=self.day.local_day_frac(self.player.x, self.now_ms),
                moon_phase=self.moon_phase(), stars=self.stars, now_ms=self.now_ms,
                ref_y=self.player.y, player=self.player, breaker=self.breaker,
                inventory=self.inventory, drops=self.drops, active_layer=self.active_layer,
            )
        render.draw_cursor(canvas, self.cursor[0], self.cursor[1])
        return canvas.to_bytes()

    def push(self) -> None:
        self._sink(self.framebuffer())

    def status_text(self) -> str:
        held = self.inventory.held_text()
        layer = LAYER_NAMES[self.active_layer]
        if self.screen is Screen.MENU:
            return "opening screen  ·  move the cursor onto the button and press Enter"
        if self.screen is Screen.INVENTORY:
            return f"inventory  ·  Enter picks up and puts down  ·  Esc closes  ·  block: {held}"
        if self.screen is Screen.BENCH:
            return "crafting bench  ·  2x2 grid, output to its right  ·  Esc closes"
        if self.screen is Screen.TABLE:
            return "crafting table  ·  3x3 grid, output to its right  ·  Esc closes"
        hour = self.day.local_day_frac(self.player.x, self.now_ms) * 24
        return (
            f"♥ {self.player.hp}  ·  block: {held}  ·  layer: {layer}  ·  "
            f"{int(hour):02d}:{int(hour * 60) % 60:02d} local"
        )
