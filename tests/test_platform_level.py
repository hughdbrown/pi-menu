"""The level format, and every way a hand-drawn map can be wrong.

Levels are drawn by hand in ``levels.py``, so the parser's job is to
refuse a bad one at import time rather than let it fail halfway through
a game where the only symptom is a player standing in mid-air.
"""

from __future__ import annotations

import pytest

from pi_menu.platformer.level import Level, LevelError

SIMPLE = [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..@.......o........G",
    "....................",
    "..........===.......",
    "....................",
    ".......^............",
    "....................",
    "====================",
]


def level(rows=None) -> Level:
    return Level("test", rows or SIMPLE)


# -- reading a good map --------------------------------------------------


def test_a_level_knows_its_size():
    board = level()
    assert (board.width, board.height) == (20, 16)


def test_solid_tiles_are_solid_and_gaps_are_not():
    board = level()
    assert board.solid(0, 15) is True
    assert board.solid(10, 11) is True
    assert board.solid(0, 0) is False


def test_walking_off_either_side_is_blocked():
    board = level()
    assert board.solid(-1, 9) is True
    assert board.solid(board.width, 9) is True


def test_the_top_of_the_level_is_a_ceiling():
    """A jump that left the map would put the player off the panel."""
    assert level().solid(5, -1) is True


def test_below_the_floor_is_open_so_a_fall_can_kill():
    assert level().solid(5, 16) is False


def test_the_spawn_and_goal_are_found():
    board = level()
    assert board.spawn == (2, 9)
    assert board.goal == (19, 9)


def test_coins_and_spikes_are_listed():
    board = level()
    assert board.coins == frozenset({(10, 9)})
    assert board.spikes == frozenset({(7, 13)})


def test_the_spawn_and_goal_glyphs_leave_empty_space_behind():
    """Standing on your own spawn tile must not be standing in a wall."""
    board = level()
    assert board.solid(*board.spawn) is False
    assert board.solid(*board.goal) is False


def test_a_level_carries_its_id():
    assert level().id == "test"


# -- refusing a bad map --------------------------------------------------


def _rows_with(row_index: int, text: str) -> list[str]:
    rows = list(SIMPLE)
    rows[row_index] = text
    return rows


def test_ragged_rows_are_refused():
    with pytest.raises(LevelError, match="same width"):
        Level("bad", _rows_with(0, "..."))


def test_the_wrong_height_is_refused():
    with pytest.raises(LevelError, match="16 rows"):
        Level("bad", SIMPLE[:-1])


def test_an_unknown_glyph_is_refused():
    with pytest.raises(LevelError, match="unknown"):
        Level("bad", _rows_with(0, "X" + "." * 19))


def test_a_level_with_no_spawn_is_refused():
    with pytest.raises(LevelError, match="one spawn"):
        Level("bad", _rows_with(9, "..........o........G"))


def test_a_level_with_two_spawns_is_refused():
    with pytest.raises(LevelError, match="one spawn"):
        Level("bad", _rows_with(0, "@..................."))


def test_a_level_with_no_goal_is_refused():
    with pytest.raises(LevelError, match="one goal"):
        Level("bad", _rows_with(9, "..@.......o........."))


def test_a_level_narrower_than_the_panel_is_refused():
    narrow = [row[:8] for row in SIMPLE]
    with pytest.raises(LevelError, match="at least 16"):
        Level("bad", narrow)
