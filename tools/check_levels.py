#!/usr/bin/env python3
"""Play every level with the real physics and report which cannot be won.

    python3 tools/check_levels.py            # all of them
    python3 tools/check_levels.py the-shaft  # just one
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(Path(__file__).resolve().parent)]

from build_levels import art  # noqa: E402
from level_specs import ORDER, SPECS  # noqa: E402
from pi_menu.platformer import bosses  # noqa: E402
from pi_menu.platformer.level import Level, LevelError  # noqa: E402
from platform_solver import Unwinnable, solve  # noqa: E402


def build(name):
    spec = dict(SPECS[name])
    boss = spec.get("boss")
    rows = art(**spec)
    kind = getattr(bosses, boss[2]) if boss else None
    return Level(name, rows, boss=kind)


def main(argv):
    wanted = argv or list(ORDER)
    failures = 0
    total = 0.0
    for index, name in enumerate(ORDER, 1):
        if name not in wanted:
            continue
        started = time.time()
        try:
            level = build(name)
        except (LevelError, ValueError) as exc:
            print(f"{index:3} {name:22} MALFORMED  {exc}")
            failures += 1
            continue
        try:
            route = solve(level)
            elapsed = time.time() - started
            total += elapsed
            print(
                f"{index:3} {name:22} ok  {len(route):4} moves {elapsed:6.1f}s  "
                f"{level.width}x{level.height} period {level.period}"
            )
        except Unwinnable as exc:
            elapsed = time.time() - started
            total += elapsed
            print(f"{index:3} {name:22} FAIL {elapsed:6.1f}s  {exc}")
            failures += 1
    print(f"\n{failures} unwinnable, {total:.1f}s total")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
