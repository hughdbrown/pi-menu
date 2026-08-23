"""Which sixteen columns of a level the panel is showing.

Split out from the renderer because clamping is the whole of it, and a
clamp that is off by one is invisible in a screenshot but obvious in a
test.
"""

from __future__ import annotations

from ..display.protocol import WIDTH


def window_x(player_x: float, level_width: int) -> int:
    """The leftmost column of the visible window.

    The window is centred on the player and then clamped to the level,
    so the first and last screens hold still instead of scrolling past
    the end into empty space.
    """
    left = int(round(player_x)) - WIDTH // 2
    return max(0, min(left, level_width - WIDTH))
