"""The demons: what they look like, and the shape of each fight.

A boss is an eight-by-eight demon drawn *behind* the level. You never
touch it and it is never in your way. It fights through the arena
instead: fists that come down out of the sky where you are standing, and
fireballs thrown across it on a script.

There is no health bar and no way to hurt it. A fight is a fixed number
of waves, each harder than the last, and surviving to the end is what
makes it withdraw and opens the goal. That keeps the fight a thing you
read rather than a damage race -- and it keeps the level solver honest,
because the only reactive part is where the fists aim.

Each kind throws something different. That is the whole variety: the
fists are the same everywhere, and the fireballs are what you learn.
"""

from __future__ import annotations

from dataclasses import dataclass

#: A fist is three cells wide and two deep.
FIST_WIDTH = 3
FIST_HEIGHT = 2
#: Ticks to fall, to stay buried, and to pull back out.
FIST_FALL = 12
FIST_HOLD = 10
FIST_RISE = 12
FIST_TOTAL = FIST_FALL + FIST_HOLD + FIST_RISE

#: Fists aim at whole even columns. Halving the number of places one can
#: land halves what the solver has to keep track of, and at three cells
#: wide the player cannot tell the difference.
AIM_STEP = 2

#: How far ahead of the demon the fight begins.
ARENA_LEAD = 14

#: The demon, eight by eight. Horns, a heavy brow, and a jaw.
DEMON = (
    "#......#",
    "##....##",
    ".######.",
    ".######.",
    ".######.",
    "..####..",
    ".#.##.#.",
    "##....##",
)
#: Drawn brighter than the body, and pulsing.
DEMON_EYES = ((2, 3), (5, 3))
#: Lights up while a fireball is on its way.
DEMON_MOUTH = ((3, 5), (4, 5))


@dataclass(frozen=True)
class Fireball:
    """One thrown fireball: when it leaves, how high, and how fast."""

    #: Ticks after the wave starts.
    offset: int
    #: Row it travels along, as a level coordinate.
    row: int
    #: Cells per tick. Negative travels left, away from the demon.
    speed: float


@dataclass(frozen=True)
class Wave:
    """One stretch of a fight."""

    ticks: int
    #: Ticks between one fist and the next.
    fist_period: int
    fireballs: tuple = ()


@dataclass(frozen=True)
class BossKind:
    """A demon and the fight it puts up."""

    name: str
    #: Which of the renderer's demon colours to draw it in.
    hue: str
    waves: tuple

    @property
    def duration(self) -> int:
        return sum(wave.ticks for wave in self.waves)

    def wave_at(self, boss_tick: int):
        """The wave running at ``boss_tick``, and how far into it we are."""
        start = 0
        for wave in self.waves:
            if boss_tick < start + wave.ticks:
                return wave, boss_tick - start
            start += wave.ticks
        return self.waves[-1], self.waves[-1].ticks - 1


def _volley(offset: int, rows, speed: float) -> tuple:
    """Several fireballs abreast, at different heights."""
    return tuple(Fireball(offset, row, speed) for row in rows)


#: Level 15. Slow, and it only throws low. Something to learn on.
IMP = BossKind(
    name="imp",
    hue="ember",
    waves=(
        Wave(ticks=140, fist_period=70, fireballs=(Fireball(30, 13, -0.30),)),
        Wave(
            ticks=160,
            fist_period=55,
            fireballs=(Fireball(20, 13, -0.34), Fireball(95, 12, -0.34)),
        ),
    ),
)

#: Level 30. Throws in pairs, high and low, so ducking is not enough.
WYRM = BossKind(
    name="wyrm",
    hue="viridian",
    waves=(
        Wave(ticks=150, fist_period=60, fireballs=_volley(30, (13, 10), -0.32)),
        Wave(ticks=170, fist_period=50, fireballs=_volley(25, (13, 11), -0.38)
             + _volley(100, (12, 9), -0.38)),
        Wave(ticks=170, fist_period=45, fireballs=_volley(20, (13, 11, 9), -0.40)),
    ),
)

#: Level 45. Fast fists, and fireballs that come in at a crawl so they
#: are still there when the next one arrives.
MOLOCH = BossKind(
    name="moloch",
    hue="brass",
    waves=(
        Wave(ticks=150, fist_period=50, fireballs=_volley(25, (13, 12), -0.22)),
        Wave(
            ticks=180,
            fist_period=42,
            fireballs=_volley(20, (13, 11), -0.24) + _volley(110, (12, 10), -0.30),
        ),
        Wave(
            ticks=190,
            fist_period=38,
            fireballs=_volley(15, (13, 12, 10), -0.26)
            + _volley(110, (13, 11), -0.36),
        ),
    ),
)

#: Level 60. Everything the others do, and it does not let up.
BALROG = BossKind(
    name="balrog",
    hue="crimson",
    waves=(
        Wave(ticks=150, fist_period=48, fireballs=_volley(25, (13, 11), -0.34)),
        Wave(
            ticks=170,
            fist_period=42,
            fireballs=_volley(20, (13, 12, 10), -0.36) + _volley(105, (13, 11), -0.28),
        ),
        Wave(
            ticks=180,
            fist_period=36,
            fireballs=_volley(15, (13, 11, 9), -0.40) + _volley(100, (12, 10), -0.30),
        ),
        Wave(
            ticks=190,
            fist_period=32,
            fireballs=_volley(12, (13, 12, 11), -0.42)
            + _volley(90, (13, 11, 9), -0.34),
        ),
    ),
)

BOSSES = (IMP, WYRM, MOLOCH, BALROG)
