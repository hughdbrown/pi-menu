"""The camera window, which is the only thing the panel ever shows.

Levels are wider than the panel and may be taller, so what matters is
that the window follows the player without ever showing anything past
the edges of the level -- a scrolled-past edge reads as a hole in the
world.
"""

from __future__ import annotations

from pi_menu.display.protocol import HEIGHT, WIDTH
from pi_menu.platformer.camera import window_x, window_y


def test_the_window_centres_on_the_player():
    assert window_x(24.0, level_width=48) == 24 - WIDTH // 2


def test_the_window_stops_at_the_left_edge():
    assert window_x(0.0, level_width=48) == 0
    assert window_x(3.0, level_width=48) == 0


def test_the_window_stops_at_the_right_edge():
    assert window_x(47.0, level_width=48) == 48 - WIDTH
    assert window_x(40.0, level_width=48) == 48 - WIDTH


def test_a_level_no_wider_than_the_panel_never_scrolls():
    assert window_x(9.0, level_width=WIDTH) == 0


def test_the_window_never_leaves_the_level():
    for x in range(0, 48):
        left = window_x(float(x), level_width=48)
        assert 0 <= left <= 48 - WIDTH


# -- following upwards as well -------------------------------------------


def test_the_window_centres_vertically_on_the_player():
    assert window_y(20.0, level_height=32) == 20 - HEIGHT // 2


def test_the_window_stops_at_the_top_of_the_level():
    assert window_y(0.0, level_height=32) == 0
    assert window_y(4.0, level_height=32) == 0


def test_the_window_stops_at_the_bottom_of_the_level():
    assert window_y(31.0, level_height=32) == 32 - HEIGHT
    assert window_y(28.0, level_height=32) == 32 - HEIGHT


def test_a_level_no_taller_than_the_panel_never_scrolls():
    for y in range(HEIGHT):
        assert window_y(float(y), level_height=HEIGHT) == 0


def test_the_window_never_leaves_a_tall_level():
    for y in range(32):
        top = window_y(float(y), level_height=32)
        assert 0 <= top <= 32 - HEIGHT
