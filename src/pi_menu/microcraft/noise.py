"""Deterministic hashing and value noise, plus the world's wrap.

Everything about the terrain is a pure function of world coordinates and
a seed, never of the order things were asked for, so any chunk can be
generated on demand and always comes out the same. The hash mirrors the
HTML's ``Math.imul`` mixer in 32-bit integer arithmetic.
"""

from __future__ import annotations

import math

MASK = 0xFFFFFFFF

#: Walking this far east brings you back where you started.
WORLD_RADIUS = 1000
WORLD_PERIOD = WORLD_RADIUS * 2


def wrap_x(x: float) -> float:
    """Fold any x into the one canonical copy of the looping world.

    Works for floats as well as ints, so a player mid-step wraps as
    smoothly as a block coordinate does.
    """
    return ((x + WORLD_RADIUS) % WORLD_PERIOD + WORLD_PERIOD) % WORLD_PERIOD - WORLD_RADIUS


def round_half_up(value: float) -> int:
    """JavaScript's ``Math.round``: halves go up, not to even."""
    return math.floor(value + 0.5)


def hash2(x: int, y: int, seed: int, world_seed: int) -> float:
    """A repeatable number in ``[0, 1)`` for a cell and a purpose."""
    h = ((x * 374761393 + y * 668265263 + (seed + world_seed) * 2246822519) & MASK)
    h = (h * 2654435761) & MASK
    h = (h ^ (h >> 15)) & MASK
    h = (h * 2246822519) & MASK
    h = (h ^ (h >> 13)) & MASK
    return h / 4294967296.0


def hash1(x: int, seed: int, world_seed: int) -> float:
    return hash2(x, 0, seed, world_seed)


def noise1d(x: float, seed: int, freq: float, world_seed: int) -> float:
    """Smooth value noise along one axis."""
    xf = x * freq
    x0 = math.floor(xf)
    t = xf - x0
    v0 = hash1(x0, seed, world_seed)
    v1 = hash1(x0 + 1, seed, world_seed)
    s = t * t * (3 - 2 * t)
    return v0 + (v1 - v0) * s
