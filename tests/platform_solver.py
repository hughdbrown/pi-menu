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
from collections import deque

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

DEFAULT_NODE_CAP = 400_000


class Unwinnable(Exception):
    """The search gave up. The level, not the search, is the suspect."""


def _key(world: World):
    """What makes two states interchangeable.

    The jump latches belong here as much as the position does. A player
    who is already holding Up cannot jump again without letting go, so
    two states that agree on where the player is and disagree on whether
    Up is held are not the same state at all -- collapsing them lets the
    search prune a route it could actually have taken.

    So does the world's own clock. Once platforms slide and enemies
    pace, standing in one place at two different moments is two
    different situations, and the same jump is a landing in one and a
    death in the other. ``dynamic_key`` carries the tick within the
    level's period, which tiles have crumbled, and whether a portal has
    just been used.
    """
    return (
        round(world.x * POSITION_SCALE),
        round(world.y * POSITION_SCALE),
        round(world.vx * VELOCITY_SCALE),
        round(world.vy * VELOCITY_SCALE),
        world.on_ground,
        world.dynamic_key(),
        world._jump_was_held,
        world._jumping,
        world._coyote,
        world._buffer,
        world.coins,
    )


#: Stands in for "you cannot get there from here" without being infinite,
#: so a state behind a wall is still explored, just last.
UNREACHABLE = 9_999


def _inside(level: Level, cell: tuple) -> bool:
    """Within the level proper.

    Everything below the floor counts as open -- that is how falling out
    of the world kills -- so a flood fill that only asks what is solid
    runs off the bottom of the map for ever.
    """
    x, y = cell
    return 0 <= x < level.width and 0 <= y < level.height


def _distance_field(level: Level, target: tuple) -> dict:
    """How many cells each open square is from ``target``.

    A flood fill over open ground, ignoring gravity entirely and linking
    the two portal tiles at no cost. It is a crude measure of distance --
    it will happily float upwards through thin air -- but it is a *map*,
    where straight-line distance is not, and that difference is the whole
    point. Guided by straight-line distance the search walks up to the
    wall in ``two-doors`` and mills about there, because the far side is
    close in a way it cannot use. This sends it back to the portal.
    """
    distance = {target: 0}
    queue = deque([target])
    while queue:
        x, y = queue.popleft()
        neighbours = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        linked = level.portals.get((x, y))
        if linked is not None:
            neighbours.append(linked)
        for cell in neighbours:
            if cell in distance or not _inside(level, cell):
                continue
            if level.static_solid(*cell):
                continue
            distance[cell] = distance[(x, y)] + 1
            queue.append(cell)
    return distance


def _costing(level: Level):
    """Score states by coins left, then by how far the nearest one is."""
    fields = {
        target: _distance_field(level, target)
        for target in list(level.coins) + [level.goal]
    }

    def cost(world: World) -> float:
        here = world.pixel
        targets = world.coins or {world.level.goal}
        nearest = min(fields[target].get(here, UNREACHABLE) for target in targets)
        return len(world.coins) * 100.0 + nearest

    return cost


def solve(level: Level, node_cap: int = DEFAULT_NODE_CAP) -> list[frozenset]:
    """Return the moves that finish ``level``, or raise :class:`Unwinnable`."""
    start = World(level)
    cost = _costing(level)
    heap = [(cost(start), 0, start, [])]
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
            heapq.heappush(heap, (cost(attempt), counter, attempt, moves + [move]))

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
