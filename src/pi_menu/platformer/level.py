"""One platform level, read from an ASCII map. No I/O, no display, no Tk.

A level is a list of equal-length strings, exactly sixteen rows tall --
the height of the panel -- and at least sixteen columns wide. Levels are
wider than the panel so the camera has somewhere to go.
"""

from __future__ import annotations

from ..display.protocol import HEIGHT, WIDTH

EMPTY = "."
SOLID = "="
SPAWN = "@"
COIN = "o"
SPIKE = "^"
GOAL = "G"

GLYPHS = frozenset({EMPTY, SOLID, SPAWN, COIN, SPIKE, GOAL})


class LevelError(ValueError):
    """A map that cannot be played.

    Levels are drawn by hand in :mod:`pi_menu.platformer.levels`, not
    supplied by whoever is playing, so a bad one is a mistake in this
    source tree. Refusing it at import time turns what would otherwise be
    a player standing in mid-air into a message naming the level.
    """


class Level:
    """A parsed map: what is solid, and where everything sits."""

    def __init__(self, id: str, rows: list[str]) -> None:
        self.id = id
        self.rows = list(rows)
        self._check_shape()

        self.height = len(self.rows)
        self.width = len(self.rows[0])

        solid: set[tuple[int, int]] = set()
        coins: set[tuple[int, int]] = set()
        spikes: set[tuple[int, int]] = set()
        spawns: list[tuple[int, int]] = []
        goals: list[tuple[int, int]] = []

        for y, row in enumerate(self.rows):
            for x, glyph in enumerate(row):
                if glyph not in GLYPHS:
                    raise LevelError(
                        f"level {id!r}: unknown glyph {glyph!r} at ({x}, {y})"
                    )
                if glyph == SOLID:
                    solid.add((x, y))
                elif glyph == COIN:
                    coins.add((x, y))
                elif glyph == SPIKE:
                    spikes.add((x, y))
                elif glyph == SPAWN:
                    spawns.append((x, y))
                elif glyph == GOAL:
                    goals.append((x, y))

        if len(spawns) != 1:
            raise LevelError(f"level {id!r}: needs exactly one spawn, found {len(spawns)}")
        if len(goals) != 1:
            raise LevelError(f"level {id!r}: needs exactly one goal, found {len(goals)}")

        self._solid = frozenset(solid)
        self.coins = frozenset(coins)
        self.spikes = frozenset(spikes)
        self.spawn = spawns[0]
        self.goal = goals[0]

    def _check_shape(self) -> None:
        if len(self.rows) != HEIGHT:
            raise LevelError(
                f"level {self.id!r}: must be {HEIGHT} rows tall, got {len(self.rows)}"
            )
        widths = {len(row) for row in self.rows}
        if len(widths) != 1:
            raise LevelError(
                f"level {self.id!r}: every row must be the same width, got {sorted(widths)}"
            )
        width = widths.pop()
        if width < WIDTH:
            raise LevelError(
                f"level {self.id!r}: must be at least {WIDTH} columns wide, got {width}"
            )

    # -- reading ---------------------------------------------------------

    def solid(self, x: int, y: int) -> bool:
        """Can the player stand on, or be stopped by, this cell?

        Off the left and right edges is solid, so the player cannot walk
        out of the level. Above the top is solid too: a jump that left
        the map would put the player somewhere the panel cannot show.
        Below the floor is *not* solid -- falling out of the world is how
        a bottomless pit kills.
        """
        if x < 0 or x >= self.width or y < 0:
            return True
        if y >= self.height:
            return False
        return (x, y) in self._solid

    def is_spike(self, x: int, y: int) -> bool:
        return (x, y) in self.spikes

    def __repr__(self) -> str:
        return (
            f"Level({self.id!r}, {self.width}x{self.height}, "
            f"coins={len(self.coins)}, spikes={len(self.spikes)})"
        )
