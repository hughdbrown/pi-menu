"""Search a level for a way through, by playing it.

Hand-drawn maps are easy to get subtly wrong. A coin one cell too high,
a gap one cell too wide, a ledge you can reach but cannot leave -- none
of those are visible in the ASCII, and all of them make a level
unwinnable. This searches for a sequence of key presses that finishes
the level, using the real :class:`World`, so a result is a genuine
playthrough rather than an estimate of one.

Best-first rather than breadth-first: the search is looking for one
solution, not all of them, and ordering by "coins left, then distance to
the nearest thing still wanted" finds it in a fraction of the states an
exhaustive sweep would visit. Nothing is approximated -- every state
comes from stepping the world -- so a solution found is a solution that
exists. Only failure is uncertain, and failure means redrawing the level
anyway.
"""

from __future__ import annotations

import copy
import heapq

from pi_menu.platformer.level import Level
from pi_menu.platformer.world import JUMP, LEFT, RIGHT, World

#: Every combination of the three keys that differs in effect.
MOVES = (
    frozenset(),
    frozenset({LEFT}),
    frozenset({RIGHT}),
    frozenset({JUMP}),
    frozenset({LEFT, JUMP}),
    frozenset({RIGHT, JUMP}),
)

#: How long one search step holds a key down. Two ticks halves the depth
#: of the search without costing any jump the player could actually make.
HOLD_TICKS = 2

#: Positions to the quarter cell, velocities to the eighth. Coarser than
#: the simulation, so states that differ immaterially collapse together.
POSITION_SCALE = 4
VELOCITY_SCALE = 8

DEFAULT_NODE_CAP = 120_000


class Unwinnable(Exception):
    """The search gave up. The level, not the search, is the suspect."""


def _key(world: World):
    """What makes two states interchangeable.

    The jump latches belong here as much as the position does. A player
    who is already holding Up cannot jump again without letting go, so
    two states that agree on where the player is and disagree on whether
    Up is held are not the same state at all -- collapsing them lets the
    search prune a route it could actually have taken.
    """
    return (
        round(world.x * POSITION_SCALE),
        round(world.y * POSITION_SCALE),
        round(world.vx * VELOCITY_SCALE),
        round(world.vy * VELOCITY_SCALE),
        world.on_ground,
        world._jump_was_held,
        world._jumping,
        world._coyote,
        world._buffer,
        world.coins,
    )


def _cost(world: World) -> float:
    """Coins still out there, then how far the nearest one is."""
    targets = world.coins or {world.level.goal}
    nearest = min(
        abs(world.x - x) + abs(world.y - y) for x, y in targets
    )
    return len(world.coins) * 100.0 + nearest


def solve(level: Level, node_cap: int = DEFAULT_NODE_CAP) -> list[frozenset]:
    """Return the moves that finish ``level``, or raise :class:`Unwinnable`."""
    start = World(level)
    heap = [(_cost(start), 0, start, [])]
    counter = 0
    seen = {_key(start)}
    visited = 0

    while heap:
        _, _, world, moves = heapq.heappop(heap)
        visited += 1
        if visited > node_cap:
            break

        for move in MOVES:
            attempt = copy.copy(world)
            for _ in range(HOLD_TICKS):
                attempt.step(move)
                if attempt.won or not attempt.alive:
                    break
            if not attempt.alive:
                continue
            if attempt.won:
                return moves + [move]

            key = _key(attempt)
            if key in seen:
                continue
            seen.add(key)
            counter += 1
            heapq.heappush(heap, (_cost(attempt), counter, attempt, moves + [move]))

    raise Unwinnable(
        f"no way through level {level.id!r} after {visited} states "
        f"({len(seen)} seen)"
    )


def reachable_cells(level: Level, node_cap: int = DEFAULT_NODE_CAP) -> set:
    """Every cell the player can occupy. Useful for diagnosing a failure."""
    start = World(level)
    queue = [start]
    seen = {_key(start)}
    cells = set()

    while queue and len(seen) < node_cap:
        world = queue.pop()
        cells.add(world.pixel)
        for move in MOVES:
            attempt = copy.copy(world)
            for _ in range(HOLD_TICKS):
                attempt.step(move)
                if not attempt.alive:
                    break
            if not attempt.alive:
                continue
            key = _key(attempt)
            if key not in seen:
                seen.add(key)
                queue.append(attempt)
    return cells
