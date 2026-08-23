"""The player, the physics, and everything that can happen to them.

No I/O, no display, no Tk: a world is stepped by handing it the set of
keys currently held down, and it answers with what happened. That makes
the whole game testable, and it is what lets the level solver in the
test suite search a level by playing it for real rather than by
approximating it.

Positions and velocities are floats in cell units and are only rounded
to whole pixels when something draws them. A player who moved a whole
cell at a time could not have a jump arc at all on a screen sixteen
pixels tall. The moving platforms are the exception: the panel can only
draw them on whole pixels, so they step a cell at a time rather than
gliding through positions nothing can show.
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

#: A bounce pad throws you about six cells up -- well past a jump, and
#: not so far that you leave the panel from ground level.
BOUNCE_VELOCITY = -0.85
#: Ice barely grips. You keep most of your speed after letting go, which
#: is the whole point: stopping has to be planned rather than decided.
ICE_ACCELERATION = 0.03
ICE_FRICTION = 0.015
#: A conveyor is worth about half a run, so walking against one is slow
#: going rather than impossible.
CONVEYOR_SPEED = 0.12

#: How close the player's box must be to a tile to touch it. Coins and
#: the goal are generous; spikes and enemies are not, so brushing one is
#: survivable and walking into one is not.
PICKUP_REACH = 0.8
HAZARD_REACH = 0.6

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
        """Put the player back on the spawn, with the level as it began."""
        self.x, self.y = float(self.level.spawn[0]), float(self.level.spawn[1])
        self.vx = 0.0
        self.vy = 0.0
        self.coins = self.level.coins
        self.alive = True
        self.won = False
        self.on_ground = False
        self.tick = 0
        self._movers = self.level.mover_cells(0)
        self._drift = 0.0
        #: Crumbling tiles the player has already stepped off. Gone for
        #: the rest of the attempt.
        self.crumbled: frozenset = frozenset()
        self._standing_on: frozenset = frozenset()
        self._in_portal = False
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
    def pixel(self) -> tuple:
        """Which LED the player is on."""
        return int(round(self.x)), int(round(self.y))

    def mover_cells(self) -> frozenset:
        return self.level.mover_cells(self.tick)

    def enemy_cells(self) -> frozenset:
        return self.level.enemy_cells(self.tick)

    def dynamic_key(self) -> tuple:
        """Everything about the world that is not the player's position.

        The solver needs this to tell two states apart: the same player
        standing in the same place with a platform under them and with
        one about to leave is not the same situation.
        """
        return (self.tick % self.level.period, self.crumbled, self._in_portal)

    def solid(self, x: int, y: int) -> bool:
        """Solid right now, movers and crumbled tiles taken into account."""
        if (x, y) in self.crumbled:
            return False
        if self.level.static_solid(x, y):
            return True
        return (x, y) in self._movers

    # -- stepping --------------------------------------------------------

    def step(self, held: Container) -> Event:
        """Advance one tick. ``held`` is the set of keys held down."""
        if not self.alive or self.won:
            return Event.NONE

        self._advance_clock()
        self._apply_input(held)
        self._apply_gravity()
        self._move_x()
        self._move_y()
        self._land_on_what_is_underfoot()
        return self._resolve_contacts()

    def _advance_clock(self) -> None:
        """Move time on, and carry the player with any platform they ride."""
        was_on = self._movers_underfoot() if self.on_ground else ()
        self.tick += 1
        self._movers = self.level.mover_cells(self.tick)

        for mover in was_on:
            dx, dy = mover.step_delta(self.tick)
            self.x += dx
            self.y += dy
            break  # one platform at a time; they never overlap

        self._push_out_of_anything_that_moved_into_us()

    def _movers_underfoot(self) -> list:
        """The moving platforms holding the player up, before time moved."""
        underfoot = set(self._support_cells())
        return [
            mover
            for mover in self.level.movers
            if underfoot & set(mover.occupied(self.tick))
        ]

    def _push_out_of_anything_that_moved_into_us(self) -> None:
        """Set the player on top of a platform that has run into them.

        Without this a mover rising through the player leaves them
        embedded in it, where neither axis of the ordinary collision
        pass will push them out and they stay stuck for good.
        """
        overlapping = [
            (cx, cy)
            for cy in self._rows()
            for cx in self._columns()
            if self.solid(cx, cy)
        ]
        if overlapping:
            self.y = float(min(cy for _, cy in overlapping)) - 1.0
            self.vy = min(self.vy, 0.0)

    def _apply_input(self, held: Container) -> None:
        accelerate, slow = self._grip()

        direction = (RIGHT in held) - (LEFT in held)
        if direction:
            self.vx = _towards(self.vx, direction * RUN_SPEED, accelerate)
        else:
            self.vx = _towards(self.vx, 0.0, slow)

        self._drift = CONVEYOR_SPEED * self._conveyor_push()

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

    def _grip(self) -> tuple:
        """How hard the player can push off and how hard they can stop."""
        if self.on_ground and self._underfoot() & self.level.ice:
            return ICE_ACCELERATION, ICE_FRICTION
        return ACCELERATION, FRICTION

    def _conveyor_push(self) -> int:
        if not self.on_ground:
            return 0
        pushes = [self.level.conveyors[cell] for cell in self._underfoot()
                  if cell in self.level.conveyors]
        return pushes[0] if pushes else 0

    def _apply_gravity(self) -> None:
        self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)

    def _move_x(self) -> None:
        """Move horizontally, then push back out of anything hit.

        A conveyor's push is part of this movement, not something
        applied beside it: pushed into a wall it has to be undone the
        same way a run into a wall is, or the player ends up inside it.

        The two axes are resolved separately. Moving diagonally into a
        corner and resolving both at once has to guess which axis caused
        the overlap, and it guesses wrong often enough to leave the
        player stuck on flat ground.
        """
        moved = self.vx + self._drift
        self.x += moved
        if moved > 0:
            column = math.floor(self.x + 1 - EPSILON)
            if any(self.solid(column, row) for row in self._rows()):
                self.x = column - 1.0
                self.vx = 0.0
        elif moved < 0:
            column = math.floor(self.x)
            if any(self.solid(column, row) for row in self._rows()):
                self.x = float(column + 1)
                self.vx = 0.0

    def _move_y(self) -> None:
        self.y += self.vy
        self.on_ground = False
        if self.vy > 0:
            row = math.floor(self.y + 1 - EPSILON)
            if any(self.solid(column, row) for column in self._columns()):
                self.y = row - 1.0
                self.vy = 0.0
                self.on_ground = True
        elif self.vy < 0:
            row = math.floor(self.y)
            if any(self.solid(column, row) for column in self._columns()):
                self.y = float(row + 1)
                self.vy = 0.0

    def _rows(self) -> Iterator:
        yield from range(math.floor(self.y), math.floor(self.y + 1 - EPSILON) + 1)

    def _columns(self) -> Iterator:
        yield from range(math.floor(self.x), math.floor(self.x + 1 - EPSILON) + 1)

    def _support_cells(self) -> list:
        """The cells directly beneath the player's feet."""
        row = math.floor(self.y + 1 - EPSILON) + 1
        return [(column, row) for column in self._columns()]

    def _underfoot(self) -> frozenset:
        return frozenset(self._support_cells())

    def _land_on_what_is_underfoot(self) -> None:
        """Bounce off a pad, and take away a crumbling tile once left."""
        underfoot = self._underfoot() if self.on_ground else frozenset()

        left_behind = self._standing_on - underfoot
        crumbling = left_behind & self.level.crumble
        if crumbling:
            # A crumbling tile holds you exactly once. It goes the moment
            # you step off, so a row of them is a route you cannot retrace.
            self.crumbled = self.crumbled | crumbling
        self._standing_on = underfoot

        if underfoot & self.level.bounce:
            self.vy = BOUNCE_VELOCITY
            self.on_ground = False
            self._jumping = False

    def _resolve_contacts(self) -> Event:
        if self.y >= self.level.height:
            self.alive = False
            return Event.DIED

        deadly = self.level.spikes | self.enemy_cells()
        if any(self._touching(cell, HAZARD_REACH) for cell in deadly):
            self.alive = False
            return Event.DIED

        self._maybe_teleport()

        taken = {coin for coin in self.coins if self._touching(coin, PICKUP_REACH)}
        if taken:
            self.coins = self.coins - taken
            return Event.COIN

        if self.goal_open and self._touching(self.level.goal, PICKUP_REACH):
            self.won = True
            return Event.WON

        return Event.NONE

    def _maybe_teleport(self) -> None:
        """Step into one portal, come out of the other, still moving.

        The latch is what stops the pair throwing the player back and
        forth forever: arriving does not count as entering, and only
        leaving the far tile arms the portals again.
        """
        if not self.level.portals:
            return
        entered = [
            cell for cell in self.level.portals if self._touching(cell, PICKUP_REACH)
        ]
        if not entered:
            self._in_portal = False
            return
        if self._in_portal:
            return
        destination = self.level.portals[entered[0]]
        self.x, self.y = float(destination[0]), float(destination[1])
        self._in_portal = True

    def _touching(self, cell: tuple, reach: float) -> bool:
        return abs(self.x - cell[0]) < reach and abs(self.y - cell[1]) < reach


def _towards(value: float, target: float, step: float) -> float:
    """Move ``value`` towards ``target`` by at most ``step``."""
    if value < target:
        return min(value + step, target)
    return max(value - step, target)
