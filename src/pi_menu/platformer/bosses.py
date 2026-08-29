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
#: Ticks to fall, to stay buried, and to pull back out. Slowed on
#: 2026-08-29: a fist that takes longer coming down is one you can see
#: arriving, which is the difference between a fight you read and one
#: you are simply caught by.
FIST_FALL = 18
FIST_HOLD = 12
FIST_RISE = 16
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
        Wave(ticks=182, fist_period=102, fireballs=(Fireball(30, 13, -0.210),)),
        Wave(
            ticks=208,
            fist_period=80,
            fireballs=(Fireball(20, 13, -0.238), Fireball(95, 12, -0.238)),
        ),
    ),
)

#: Level 30. Throws in pairs, high and low, so ducking is not enough.
WYRM = BossKind(
    name="wyrm",
    hue="viridian",
    waves=(
        Wave(ticks=195, fist_period=87, fireballs=_volley(30, (13, 10), -0.224)),
        Wave(ticks=221, fist_period=72, fireballs=_volley(25, (13, 11), -0.266)
             + _volley(100, (12, 9), -0.266)),
        Wave(ticks=221, fist_period=65, fireballs=_volley(20, (13, 11, 9), -0.280)),
    ),
)

#: Level 45. Fast fists, and fireballs that come in at a crawl so they
#: are still there when the next one arrives.
MOLOCH = BossKind(
    name="moloch",
    hue="brass",
    waves=(
        Wave(ticks=195, fist_period=72, fireballs=_volley(25, (13, 12), -0.154)),
        Wave(
            ticks=234,
            fist_period=61,
            fireballs=_volley(20, (13, 11), -0.168) + _volley(110, (12, 10), -0.210),
        ),
        Wave(
            ticks=247,
            fist_period=55,
            fireballs=_volley(15, (13, 12, 10), -0.182)
            + _volley(110, (13, 11), -0.252),
        ),
    ),
)

#: Level 60. Everything the others do, and it does not let up.
BALROG = BossKind(
    name="balrog",
    hue="crimson",
    waves=(
        Wave(ticks=195, fist_period=70, fireballs=_volley(25, (13, 11), -0.238)),
        Wave(
            ticks=221,
            fist_period=61,
            fireballs=_volley(20, (13, 12, 10), -0.252) + _volley(105, (13, 11), -0.196),
        ),
        Wave(
            ticks=234,
            fist_period=52,
            fireballs=_volley(15, (13, 11, 9), -0.280) + _volley(100, (12, 10), -0.210),
        ),
        Wave(
            ticks=247,
            fist_period=46,
            fireballs=_volley(12, (13, 12, 11), -0.294)
            + _volley(90, (13, 11, 9), -0.238),
        ),
    ),
)

BOSSES = (IMP, WYRM, MOLOCH, BALROG)
