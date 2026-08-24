"""Replaying a recorded route, one tick at a time.

Auto-play does not think. The level solver already found a winning
sequence of key presses for every level -- that is how the levels are
proved winnable -- and ``tools/solve_routes.py`` ships those sequences
as :mod:`pi_menu.platformer.routes`. This just feeds them back into the
same ``World.step`` the keyboard feeds, so what auto-play shows is a
genuine playthrough under the real physics, not a scripted animation.
"""

from __future__ import annotations

from . import world as physics

#: How a move is packed into one hex character of a route string.
KEY_BITS = {
    physics.LEFT: 1,
    physics.RIGHT: 2,
    physics.JUMP: 4,
    physics.DOWN: 8,
}

#: The solver holds each move for this many ticks; replay must match.
TICKS_PER_MOVE = 2

_BITS_KEY = {bit: key for key, bit in KEY_BITS.items()}


def decode(route: str) -> list:
    """A route string back into per-move held-key sets."""
    moves = []
    for character in route:
        bits = int(character, 16)
        moves.append(
            frozenset(key for bit, key in _BITS_KEY.items() if bits & bit)
        )
    return moves


class Autopilot:
    """Feeds a route out tick by tick, then holds nothing."""

    def __init__(self, route: str) -> None:
        self._moves = decode(route)
        self._tick = 0

    def held(self) -> frozenset:
        """The keys the route holds down on the current tick."""
        index = self._tick // TICKS_PER_MOVE
        if index >= len(self._moves):
            return frozenset()
        return self._moves[index]

    def advance(self) -> None:
        self._tick += 1

    @property
    def exhausted(self) -> bool:
        """True once the route has run out of moves.

        A fresh route wins before this; an exhausted one means the level
        or the physics changed after the route was recorded.
        """
        return self._tick >= len(self._moves) * TICKS_PER_MOVE
