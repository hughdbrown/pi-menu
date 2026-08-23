"""The player, the physics, and everything that can happen to them.

No I/O, no display, no Tk: a world is stepped by handing it the set of
keys currently held down, and it answers with what happened. That makes
the whole game testable, and it is what lets the level solver in the
test suite search a level by playing it for real rather than by
approximating it.

Positions and velocities are floats in cell units and are only rounded
to whole pixels when something draws them. A player who moved a whole
cell at a time could not have a jump arc at all on a screen sixteen
pixels tall.
"""

from __future__ import annotations

import enum
import math
from typing import Container, Iterator

from .level import Level

#: Names for the keys, so nothing downstream has to know about Tk.
LEFT = "left"
RIGHT = "right"
JUMP = "jump"

#: The simulation runs at a fixed rate; every constant below is per tick.
TICK_HZ = 20

GRAVITY = 0.055
#: Chosen so a full jump rises about 3.6 cells: enough to clear a
#: three-cell ledge with room to spare, never enough to cheat a four.
JUMP_VELOCITY = -0.66
#: Letting go of Up clamps the rise to about 1.5 cells.
CUT_JUMP_VELOCITY = -0.34
RUN_SPEED = 0.22
ACCELERATION = 0.11
FRICTION = 0.11
#: Below one cell a tick, so the player can never step over a one-cell
#: floor without ever overlapping it and drop through the world.
MAX_FALL_SPEED = 0.85
#: A jump still works for this many ticks after walking off a ledge.
COYOTE_TICKS = 3
#: A jump pressed this soon before landing is remembered and fires on it.
BUFFER_TICKS = 4

#: How close the player's box must be to a tile to touch it. Coins and
#: the goal are generous; spikes are not, so brushing one is survivable
#: and walking into one is not.
PICKUP_REACH = 0.8
SPIKE_REACH = 0.6

#: Keeps a player flush against a wall from counting as inside it.
EPSILON = 1e-9


class Event(enum.Enum):
    """The most notable thing that happened during one step."""

    NONE = "none"
    COIN = "coin"
    DIED = "died"
    WON = "won"


class World:
    """One attempt at one level."""

    def __init__(self, level: Level) -> None:
        self.level = level
        self.reset()

    def reset(self) -> None:
        """Put the player back on the spawn with every coin restored."""
        self.x, self.y = float(self.level.spawn[0]), float(self.level.spawn[1])
        self.vx = 0.0
        self.vy = 0.0
        self.coins = self.level.coins
        self.alive = True
        self.won = False
        self.on_ground = False
        self._coyote = 0
        self._buffer = 0
        self._jump_was_held = False
        self._jumping = False

    # -- reading ---------------------------------------------------------

    @property
    def goal_open(self) -> bool:
        """The goal only opens once every coin has been collected."""
        return not self.coins

    @property
    def pixel(self) -> tuple[int, int]:
        """Which LED the player is on."""
        return int(round(self.x)), int(round(self.y))

    # -- stepping --------------------------------------------------------

    def step(self, held: Container[str]) -> Event:
        """Advance one tick. ``held`` is the set of keys held down."""
        if not self.alive or self.won:
            return Event.NONE

        self._apply_input(held)
        self._apply_gravity()
        self._move_x()
        self._move_y()
        return self._resolve_contacts()

    def _apply_input(self, held: Container[str]) -> None:
        direction = (RIGHT in held) - (LEFT in held)
        if direction:
            self.vx = _towards(self.vx, direction * RUN_SPEED, ACCELERATION)
        else:
            self.vx = _towards(self.vx, 0.0, FRICTION)

        jump = JUMP in held
        if jump and not self._jump_was_held:
            self._buffer = BUFFER_TICKS
        self._jump_was_held = jump

        self._coyote = COYOTE_TICKS if self.on_ground else max(0, self._coyote - 1)
        self._buffer = max(0, self._buffer - 1)

        if self._buffer and self._coyote:
            self.vy = JUMP_VELOCITY
            self._buffer = 0
            self._coyote = 0
            self.on_ground = False
            self._jumping = True
        elif self._jumping and not jump and self.vy < CUT_JUMP_VELOCITY:
            # Released early: cut the rise short rather than ending it, so
            # a tap is still a jump and not a twitch.
            self.vy = CUT_JUMP_VELOCITY

        if self.vy >= 0:
            self._jumping = False

    def _apply_gravity(self) -> None:
        self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)

    def _move_x(self) -> None:
        """Move horizontally, then push back out of anything hit.

        The two axes are resolved separately. Moving diagonally into a
        corner and resolving both at once has to guess which axis caused
        the overlap, and it guesses wrong often enough to leave the
        player stuck on flat ground.
        """
        self.x += self.vx
        if self.vx > 0:
            column = math.floor(self.x + 1 - EPSILON)
            if any(self.level.solid(column, row) for row in self._rows()):
                self.x = column - 1.0
                self.vx = 0.0
        elif self.vx < 0:
            column = math.floor(self.x)
            if any(self.level.solid(column, row) for row in self._rows()):
                self.x = float(column + 1)
                self.vx = 0.0

    def _move_y(self) -> None:
        self.y += self.vy
        self.on_ground = False
        if self.vy > 0:
            row = math.floor(self.y + 1 - EPSILON)
            if any(self.level.solid(column, row) for column in self._columns()):
                self.y = row - 1.0
                self.vy = 0.0
                self.on_ground = True
        elif self.vy < 0:
            row = math.floor(self.y)
            if any(self.level.solid(column, row) for column in self._columns()):
                self.y = float(row + 1)
                self.vy = 0.0

    def _rows(self) -> Iterator[int]:
        yield from range(math.floor(self.y), math.floor(self.y + 1 - EPSILON) + 1)

    def _columns(self) -> Iterator[int]:
        yield from range(math.floor(self.x), math.floor(self.x + 1 - EPSILON) + 1)

    def _resolve_contacts(self) -> Event:
        if self.y >= self.level.height:
            self.alive = False
            return Event.DIED

        if any(self._touching(spike, SPIKE_REACH) for spike in self.level.spikes):
            self.alive = False
            return Event.DIED

        taken = {coin for coin in self.coins if self._touching(coin, PICKUP_REACH)}
        if taken:
            self.coins = self.coins - taken
            return Event.COIN

        if self.goal_open and self._touching(self.level.goal, PICKUP_REACH):
            self.won = True
            return Event.WON

        return Event.NONE

    def _touching(self, cell: tuple[int, int], reach: float) -> bool:
        return abs(self.x - cell[0]) < reach and abs(self.y - cell[1]) < reach


def _towards(value: float, target: float, step: float) -> float:
    """Move ``value`` towards ``target`` by at most ``step``."""
    if value < target:
        return min(value + step, target)
    return max(value - step, target)
