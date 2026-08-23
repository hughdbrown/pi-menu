"""A side-scrolling platform game for the Stellar Unicorn.

Named ``platformer`` rather than ``platform`` so that it can never be
mistaken for the standard library module of that name.
"""

from .level import Level, LevelError

__all__ = ["Level", "LevelError"]
