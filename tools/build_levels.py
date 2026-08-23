#!/usr/bin/env python3
"""Generate ``src/pi_menu/platformer/levels.py`` from compact level specs.

The levels ship as literal ASCII art because that is what is readable in
a diff and at a glance. They are not written that way. Every level here
is a handful of lines -- floor runs with the pits punched out, then
lists of coins, spikes, tracks and special tiles -- and this paints the
rows from them.

Three mistakes are invisible in the finished art and all three have
happened: a row one character short, a coin drawn on top of a mover's
track (which splits it into two stubs that barely move), and enemy pens
of unequal length (which multiplies the level's period and puts the
solver's search out of reach). Painting from a spec removes the first
outright; ``tests/test_platform_levels.py`` catches the rest.

    python3 tools/build_levels.py            # rewrite levels.py
    python3 tools/build_levels.py --show 13  # print one level

Always run the tests afterwards. A level that cannot be won is a level
the solver will refuse.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PANEL = 16
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "pi_menu" / "platformer" / "levels.py"


def art(width, height=PANEL, solid=(), spikes=(), coins=(), spawn=None, goal=None,
        ice=(), bounce=(), crumble=(), belt_left=(), belt_right=(),
        track_h=(), track_v=(), enemies=(), portals=(),
        ladders=(), one_way=(), updraft=(), blinking=(), boss=None):
    """Paint one level. Runs are ``(row, x0, x1)``; columns ``(x, y0, y1)``."""
    rows = [["."] * width for _ in range(height)]

    def paint(runs, glyph):
        for row, x0, x1 in runs:
            for x in range(x0, x1 + 1):
                rows[row][x] = glyph

    def paint_v(runs, glyph):
        for column, y0, y1 in runs:
            for y in range(y0, y1 + 1):
                rows[y][column] = glyph

    drawn = {}

    def dots(cells, glyph):
        for x, y in cells:
            # A coin drawn on a track splits the track into two stubs that
            # barely move, and the finished ASCII gives no hint of it. It
            # has happened twice, so it is an error rather than a surprise.
            if rows[y][x] in "-|Hu":
                raise ValueError(
                    f"{glyph!r} at ({x}, {y}) is drawn on top of "
                    f"{rows[y][x]!r}, which would cut it in two"
                )
            rows[y][x] = glyph

    paint(solid, "=")
    paint(ice, "i")
    paint(bounce, "b")
    paint(crumble, "c")
    paint(belt_left, "<")
    paint(belt_right, ">")
    paint(one_way, "_")
    paint(blinking, "x")
    paint(track_h, "-")
    paint_v(track_v, "|")
    paint_v(ladders, "H")
    paint_v(updraft, "u")
    dots(spikes, "^")
    dots(enemies, "E")
    dots(portals, "p")
    dots(coins, "o")
    if boss is not None:
        rows[boss[1]][boss[0]] = "B"
    rows[spawn[1]][spawn[0]] = "@"
    rows[goal[1]][goal[0]] = "G"
    return ["".join(r) for r in rows]


def ground(width, gaps=(), rows=None, height=PANEL):
    """Solid floor across the width, minus the given ``(x0, x1)`` pits."""
    rows = rows if rows is not None else (height - 2, height - 1)
    runs = []
    for row in rows:
        x = 0
        for g0, g1 in sorted(gaps):
            if g0 > x:
                runs.append((row, x, g0 - 1))
            x = g1 + 1
        if x <= width - 1:
            runs.append((row, x, width - 1))
    return runs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--show", type=int, help="print level N (from 1) and exit")
    args = parser.parse_args(argv)

    from level_specs import SPECS, BLURBS, ORDER

    if args.show:
        name = ORDER[args.show - 1]
        rows = art(**SPECS[name])
        print(f"--- {args.show}. {name} ({len(rows[0])}x{len(rows)}) ---")
        for y, row in enumerate(rows):
            print(f"{y:2} {row}")
        return 0

    out = [_HEADER]
    for name in ORDER:
        rows = art(**SPECS[name])
        constant = name.upper().replace("-", "_")
        out.append("")
        out.append(f"#: {BLURBS[name]}")
        out.append(f"{constant} = Level(")
        out.append(f'    "{name}",')
        out.append("    [")
        out.extend(f'        "{row}",' for row in rows)
        out.append("    ],")
        boss = SPECS[name].get("boss")
        if boss is not None:
            out.append(f"    boss={boss[2]},")
        out.append(")")

    out += ["", "", "#: Play order. The picker numbers them from one in this order.", "LEVELS = ("]
    out += [f"    {name.upper().replace('-', '_')}," for name in ORDER]
    out += [
        ")",
        "",
        "",
        "def title(index: int) -> str:",
        '    """A human label for the level at ``index``, numbered from one."""',
        "    return f\"{index + 1}. {LEVELS[index].id.replace('-', ' ')}\"",
        "",
    ]
    TARGET.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {len(ORDER)} levels to {TARGET.relative_to(ROOT)}")
    return 0


_HEADER = '''"""The levels, as ASCII maps.

Generated by ``tools/build_levels.py`` from the specs in
``tools/level_specs.py``. Edit those and regenerate rather than editing
this file: a row one character short is invisible here and fatal there.

The glyphs are the ones :mod:`pi_menu.platformer.level` reads::

    .  empty          ^  spike           -  horizontal mover track
    =  solid          G  goal            |  vertical mover track
    @  spawn          i  ice             E  enemy
    o  coin           b  bounce pad      p  portal (in pairs)
    c  crumbling      H  ladder          B  boss
    _  one-way        u  updraft         x  blinking block
    <  belt, pushes left                 >  belt, pushes right

Levels are at least as wide as the panel and between sixteen and
thirty-two rows tall. The camera follows the player in both directions.

Every one of these has been searched by ``tests/platform_solver.py``,
which plays the level with the real physics and finds a sequence of key
presses that finishes it. A map that cannot be won fails the test suite,
which is the only practical way to be sure: a coin one cell too high
looks exactly like a coin one cell lower.

A level's *period* is how long until every moving thing is back where it
started, and it is the multiplier on that search. Two enemies pacing
pens of different lengths gave one level a period of 2184 and put the
search beyond reach; matching the pens brought it to 24. That is why the
pens are the sizes they are.
"""

from __future__ import annotations

from .bosses import BALROG, IMP, MOLOCH, WYRM
from .level import Level
'''

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
