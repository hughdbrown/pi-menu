"""Which sixteen-by-sixteen window of a level the panel is showing.

Split out from the renderer because clamping is the whole of it, and a
clamp that is off by one is invisible in a screenshot but obvious in a
test.
"""

from __future__ import annotations

from ..display.protocol import HEIGHT, WIDTH


def window_x(player_x: float, level_width: int) -> int:
    """The leftmost column of the visible window.

    The window is centred on the player and then clamped to the level,
    so the first and last screens hold still instead of scrolling past
    the end into empty space.
    """
    return _clamp(int(round(player_x)) - WIDTH // 2, level_width - WIDTH)


def window_y(player_y: float, level_height: int) -> int:
    """The topmost row of the visible window.

    Levels no taller than the panel never scroll, which is most of them;
    the clamp handles that without the caller having to know.
    """
    return _clamp(int(round(player_y)) - HEIGHT // 2, level_height - HEIGHT)


def _clamp(value: int, limit: int) -> int:
    return max(0, min(value, limit))
