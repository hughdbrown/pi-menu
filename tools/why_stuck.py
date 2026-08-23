#!/usr/bin/env python3
"""Show which cells of a level the player can actually get to.

    python3 tools/why_stuck.py the-shaft

Coins are frozen -- never collected -- so the search does not multiply
by every subset of them and the map comes back in a second or two. That
makes it an approximation of what the solver sees, which is all a
diagnosis needs: it names the coin or the goal that nothing can touch.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(Path(__file__).resolve().parent)]

from check_levels import build  # noqa: E402
from platform_solver import HOLD_TICKS, _key, moves_for  # noqa: E402
from pi_menu.platformer.world import World  # noqa: E402

CAP = 300_000


def reachable(level):
    start = World(level)
    moves = moves_for(level)
    seen = {_key(start)}
    stack = [start]
    cells = set()
    while stack and len(seen) < CAP:
        world = stack.pop()
        cells.add(world.pixel)
        for move in moves:
            attempt = copy.copy(world)
            for _ in range(HOLD_TICKS):
                attempt.step(move)
                attempt.coins = level.coins  # frozen: keeps the search small
                if not attempt.alive:
                    break
            if not attempt.alive:
                continue
            key = _key(attempt)
            if key not in seen:
                seen.add(key)
                stack.append(attempt)
    return cells, len(seen)


def touchable(cells, target, reach=0.8):
    return any(
        abs(x - target[0]) < reach + 0.5 and abs(y - target[1]) < reach + 0.5
        for x, y in cells
    )


def main(name):
    level = build(name)
    cells, states = reachable(level)
    print(f"{name}: {len(cells)} cells reachable, {states} states searched\n")
    for y, row in enumerate(level.rows):
        marked = "".join(
            "*" if (x, y) in cells and ch == "." else ch for x, ch in enumerate(row)
        )
        print(f"{y:2} {marked}")
    print()
    for coin in sorted(level.coins):
        print(f"  coin {coin}: {'reachable' if touchable(cells, coin) else 'NO'}")
    print(f"  goal {level.goal}: {'reachable' if touchable(cells, level.goal) else 'NO'}")


if __name__ == "__main__":
    main(sys.argv[1])
