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
from pi_menu.platformer.world import DOWN, JUMP, LEFT, RIGHT, World

#: Every combination of the three ordinary keys that differs in effect.
MOVES = (
    frozenset(),
    frozenset({LEFT}),
    frozenset({RIGHT}),
    frozenset({JUMP}),
    frozenset({LEFT, JUMP}),
    frozenset({RIGHT, JUMP}),
)

#: Down only does anything on a ladder, so it is only offered where
#: there is one. Adding it everywhere would half again the branching for
#: no reachable state the search does not already have.
LADDER_MOVES = MOVES + (
    frozenset({DOWN}),
    frozenset({LEFT, DOWN}),
    frozenset({RIGHT, DOWN}),
)


def moves_for(level: Level) -> tuple:
    return LADDER_MOVES if level.ladders else MOVES

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
    """How far each open square is from ``target``, as the player moves.

    A flood fill over open ground, linking the two portal tiles at no
    cost. It is a *map*, where straight-line distance is not: guided by
    straight-line distance the search walks up to the wall in
    ``two-doors`` and mills about there, because the far side is close
    in a way it cannot use.

    Climbing costs six a cell where walking costs one. The fill runs
    outwards from the target, so its downward step -- towards a player
    who would have to come *up* -- is the expensive one. Rated equally,
    a player bouncing under a high coin scores the same as one standing
    on the board the winning jump leaves from, and the search drowns in
    the plateau of ways to be underneath something. Three, not more: a
    jump really does climb a cell in about three ticks, and charging six
    sent the search the long way round in levels whose route simply
    jumps up a ledge -- two of them regressed from winnable to "no way
    through" before this number came down. On a ladder or in an
    updraught the cell charges one whichever way it is entered.
    """
    climb = 3
    distance = {target: 0}
    heap = [(0, target)]
    while heap:
        so_far, (x, y) = heapq.heappop(heap)
        if so_far > distance.get((x, y), UNREACHABLE):
            continue
        steps = [
            ((x + 1, y), 1),
            ((x - 1, y), 1),
            ((x, y + 1), climb),  # downwards from the target = up for the player
            ((x, y - 1), 1),
        ]
        linked = level.portals.get((x, y))
        if linked is not None:
            steps.append((linked, 1))
        for cell, price in steps:
            if not _inside(level, cell) or level.static_solid(*cell):
                continue
            if cell in level.ladders or cell in level.updrafts:
                price = 1
            candidate = so_far + price
            if candidate < distance.get(cell, UNREACHABLE):
                distance[cell] = candidate
                heapq.heappush(heap, (candidate, cell))
    return distance


#: Scores are banded so the search finishes one job before starting the
#: next: every coin, then the demon, then the goal.
COIN_BAND = 100_000
BOSS_BAND = 10_000


def _costing(level: Level):
    """Score states by what is left to do, then by how far away it is."""
    fields = {
        target: _distance_field(level, target)
        for target in list(level.coins) + [level.goal]
    }
    fight = level.boss.duration if level.boss is not None else 0

    def cost(world: World) -> float:
        here = world.pixel
        if world.coins:
            nearest = min(fields[target].get(here, UNREACHABLE) for target in world.coins)
            return len(world.coins) * COIN_BAND + nearest

        if not world.boss_done:
            if world.boss_tick is None:
                # Not in the arena yet. Head for the goal, which is past it.
                return BOSS_BAND + fields[level.goal].get(here, UNREACHABLE)
            # In the fight. The further through it, the better -- which
            # makes the search dive for the end of the fight rather than
            # sweep every way of surviving the first wave.
            return fight - world.boss_tick

        return fields[level.goal].get(here, UNREACHABLE)

    return cost


def solve(level: Level, node_cap: int = DEFAULT_NODE_CAP) -> list[frozenset]:
    """Return the moves that finish ``level``, or raise :class:`Unwinnable`."""
    start = World(level)
    cost = _costing(level)
    # Not called ``moves``: the loop below pops a variable of that name.
    alphabet = moves_for(level)
    heap = [(cost(start), 0, start, [])]
    counter = 0
    seen = {_key(start)}
    visited = 0

    while heap:
        _, _, world, moves = heapq.heappop(heap)
        visited += 1
        if visited > node_cap:
            break

        for move in alphabet:
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
    moves = moves_for(level)
    queue = [start]
    seen = {_key(start)}
    cells = set()

    while queue and len(seen) < node_cap:
        world = queue.pop()
        cells.add(world.pixel)
        for move in moves:
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
