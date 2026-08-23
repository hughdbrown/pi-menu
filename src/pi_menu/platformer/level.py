"""One platform level, read from an ASCII map. No I/O, no display, no Tk.

A level is a list of equal-length strings, exactly sixteen rows tall --
the height of the panel -- and at least sixteen columns wide. Levels are
wider than the panel so the camera has somewhere to go.

Most of the map is static, and the moving parts are static descriptions
of movement: a mover's track and an enemy's patrol are both drawn in the
ASCII, and where each one *is* at any moment is a pure function of the
tick. Nothing here changes as a level is played, which is what lets the
level solver treat time as one more coordinate instead of having to
model a simulation inside its search.
"""

from __future__ import annotations

from math import gcd

from ..display.protocol import HEIGHT, WIDTH

EMPTY = "."
SOLID = "="
SPAWN = "@"
COIN = "o"
SPIKE = "^"
GOAL = "G"
ICE = "i"
BOUNCE = "b"
CRUMBLE = "c"
CONVEYOR_LEFT = "<"
CONVEYOR_RIGHT = ">"
TRACK_H = "-"
TRACK_V = "|"
ENEMY = "E"
PORTAL = "p"

GLYPHS = frozenset(
    {
        EMPTY, SOLID, SPAWN, COIN, SPIKE, GOAL, ICE, BOUNCE, CRUMBLE,
        CONVEYOR_LEFT, CONVEYOR_RIGHT, TRACK_H, TRACK_V, ENEMY, PORTAL,
    }
)

#: Tiles you can stand on. Everything here is solid; they differ in what
#: happens once you are standing there.
FLOOR_GLYPHS = frozenset({SOLID, ICE, BOUNCE, CRUMBLE, CONVEYOR_LEFT, CONVEYOR_RIGHT})

#: How long a moving platform is, along its track.
MOVER_LENGTH = 2
#: Ticks between one whole-cell step of a mover or an enemy. The panel
#: can only draw them on whole pixels, so they step rather than glide.
MOVER_TICKS = 6
ENEMY_TICKS = 6

#: More crumbling tiles than this in one level and the solver's search
#: space doubles per tile for no gain in the level.
MAX_CRUMBLE = 4


class LevelError(ValueError):
    """A map that cannot be played.

    Levels are drawn by hand in :mod:`pi_menu.platformer.levels`, not
    supplied by whoever is playing, so a bad one is a mistake in this
    source tree. Refusing it at import time turns what would otherwise be
    a player standing in mid-air into a message naming the level.
    """


class Mover:
    """A platform that slides back and forth along a drawn track.

    The track is the run of ``-`` or ``|`` in the map. The platform is
    :data:`MOVER_LENGTH` cells of it, and where along the track it sits
    is a triangle wave in the tick count -- so a mover has no state of
    its own and a level can be rewound by rewinding the clock.
    """

    def __init__(self, cells: list, horizontal: bool) -> None:
        self.cells = cells
        self.horizontal = horizontal
        self.span = len(cells) - MOVER_LENGTH
        if self.span < 1:
            raise LevelError(
                f"a mover track must be at least {MOVER_LENGTH + 1} cells long, "
                f"got {len(cells)} at {cells[0]}"
            )
        self.period = 2 * self.span * MOVER_TICKS

    def offset(self, tick: int) -> int:
        """How far along the track the platform starts, at ``tick``."""
        step = (tick // MOVER_TICKS) % (2 * self.span)
        return step if step <= self.span else 2 * self.span - step

    def occupied(self, tick: int) -> list:
        start = self.offset(tick)
        return self.cells[start : start + MOVER_LENGTH]

    def step_delta(self, tick: int) -> tuple:
        """How far the platform moved between ``tick - 1`` and ``tick``."""
        before, after = self.offset(tick - 1), self.offset(tick)
        moved = after - before
        return (moved, 0) if self.horizontal else (0, moved)


class Enemy:
    """A walker that paces its ledge and turns at a wall or a drop.

    The whole patrol is worked out once, when the level is parsed, so
    where an enemy is at any tick is a lookup rather than a simulation.
    Enemies cannot be jumped on. On a screen this size an enemy is a
    single pixel, and a one-pixel hitbox you are meant to land on
    precisely is a coin flip, not a skill.
    """

    def __init__(self, start: tuple, level: "Level") -> None:
        self.path = self._walk(start, level)
        self.period = len(self.path) * ENEMY_TICKS

    @staticmethod
    def _walk(start: tuple, level: "Level") -> list:
        x, y = start
        direction = 1
        seen = {}
        path = []
        while (x, y, direction) not in seen:
            seen[(x, y, direction)] = len(path)
            path.append((x, y))
            ahead = x + direction
            blocked = level.static_solid(ahead, y)
            over_a_drop = not level.static_solid(ahead, y + 1)
            if blocked or over_a_drop:
                direction = -direction
                ahead = x + direction
                if level.static_solid(ahead, y) or not level.static_solid(ahead, y + 1):
                    break  # penned in on both sides: it stands still
            x = ahead
        loop_starts_at = seen[(x, y, direction)] if (x, y, direction) in seen else 0
        return path[loop_starts_at:] or [start]

    def at(self, tick: int) -> tuple:
        return self.path[(tick // ENEMY_TICKS) % len(self.path)]


class Level:
    """A parsed map: what is solid, what moves, and where everything sits."""

    def __init__(self, id: str, rows: list) -> None:
        self.id = id
        self.rows = list(rows)
        self._check_shape()

        self.height = len(self.rows)
        self.width = len(self.rows[0])

        found: dict = {glyph: set() for glyph in GLYPHS}
        for y, row in enumerate(self.rows):
            for x, glyph in enumerate(row):
                if glyph not in GLYPHS:
                    raise LevelError(
                        f"level {id!r}: unknown glyph {glyph!r} at ({x}, {y})"
                    )
                found[glyph].add((x, y))

        self._solid = frozenset().union(*(found[g] for g in FLOOR_GLYPHS))
        self.coins = frozenset(found[COIN])
        self.spikes = frozenset(found[SPIKE])
        self.ice = frozenset(found[ICE])
        self.bounce = frozenset(found[BOUNCE])
        self.crumble = frozenset(found[CRUMBLE])
        self.conveyors = {
            **{cell: -1 for cell in found[CONVEYOR_LEFT]},
            **{cell: 1 for cell in found[CONVEYOR_RIGHT]},
        }
        self.portals = self._pair_portals(found[PORTAL])

        self.spawn = self._only(found[SPAWN], "spawn")
        self.goal = self._only(found[GOAL], "goal")

        if len(self.crumble) > MAX_CRUMBLE:
            raise LevelError(
                f"level {id!r}: {len(self.crumble)} crumbling tiles, at most "
                f"{MAX_CRUMBLE} -- each one doubles the level solver's search"
            )

        self.movers = self._find_movers(found[TRACK_H], found[TRACK_V])
        self.enemies = [Enemy(cell, self) for cell in sorted(found[ENEMY])]
        self.period = self._period()

    # -- parsing ---------------------------------------------------------

    def _check_shape(self) -> None:
        if len(self.rows) != HEIGHT:
            raise LevelError(
                f"level {self.id!r}: must be {HEIGHT} rows tall, got {len(self.rows)}"
            )
        widths = {len(row) for row in self.rows}
        if len(widths) != 1:
            raise LevelError(
                f"level {self.id!r}: every row must be the same width, "
                f"got {sorted(widths)}"
            )
        if widths.pop() < WIDTH:
            raise LevelError(
                f"level {self.id!r}: must be at least {WIDTH} columns wide"
            )

    def _only(self, cells: set, what: str) -> tuple:
        if len(cells) != 1:
            raise LevelError(
                f"level {self.id!r}: needs exactly one {what}, found {len(cells)}"
            )
        return next(iter(cells))

    def _pair_portals(self, cells: set) -> dict:
        """Link the two portal tiles to each other, if there are any."""
        if not cells:
            return {}
        if len(cells) != 2:
            raise LevelError(
                f"level {self.id!r}: portals come in pairs, found {len(cells)}"
            )
        first, second = sorted(cells)
        return {first: second, second: first}

    def _find_movers(self, horizontal: set, vertical: set) -> list:
        """Turn each run of track glyphs into one mover."""
        movers = [
            Mover(run, horizontal=True) for run in _runs(horizontal, along_x=True)
        ]
        movers += [
            Mover(run, horizontal=False) for run in _runs(vertical, along_x=False)
        ]
        return movers

    def _period(self) -> int:
        """How long until every moving thing is back where it started."""
        period = 1
        for mover in self.movers:
            period = _lcm(period, mover.period)
        for enemy in self.enemies:
            period = _lcm(period, enemy.period)
        return period

    # -- reading ---------------------------------------------------------

    def static_solid(self, x: int, y: int) -> bool:
        """Solid ignoring anything that moves.

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

    def mover_cells(self, tick: int) -> frozenset:
        cells = set()
        for mover in self.movers:
            cells.update(mover.occupied(tick))
        return frozenset(cells)

    def enemy_cells(self, tick: int) -> frozenset:
        return frozenset(enemy.at(tick) for enemy in self.enemies)

    @property
    def moves(self) -> bool:
        """Does anything in this level move on its own?"""
        return bool(self.movers or self.enemies)

    def __repr__(self) -> str:
        return (
            f"Level({self.id!r}, {self.width}x{self.height}, "
            f"coins={len(self.coins)}, movers={len(self.movers)}, "
            f"enemies={len(self.enemies)}, period={self.period})"
        )


def _runs(cells: set, along_x: bool) -> list:
    """Group cells into maximal straight runs, in drawing order."""
    runs = []
    remaining = set(cells)
    for cell in sorted(remaining):
        if cell not in remaining:
            continue
        step = (1, 0) if along_x else (0, 1)
        # Walk back to the start of this run, then forwards along it.
        x, y = cell
        while (x - step[0], y - step[1]) in remaining:
            x, y = x - step[0], y - step[1]
        run = []
        while (x, y) in remaining:
            remaining.discard((x, y))
            run.append((x, y))
            x, y = x + step[0], y + step[1]
        runs.append(run)
    return runs


def _lcm(a: int, b: int) -> int:
    return a * b // gcd(a, b)
