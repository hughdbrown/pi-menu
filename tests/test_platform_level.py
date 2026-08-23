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
    assert board.static_solid(0, 15) is True
    assert board.static_solid(10, 11) is True
    assert board.static_solid(0, 0) is False


def test_walking_off_either_side_is_blocked():
    board = level()
    assert board.static_solid(-1, 9) is True
    assert board.static_solid(board.width, 9) is True


def test_the_top_of_the_level_is_a_ceiling():
    """A jump that left the map would put the player off the panel."""
    assert level().static_solid(5, -1) is True


def test_below_the_floor_is_open_so_a_fall_can_kill():
    assert level().static_solid(5, 16) is False


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
    assert board.static_solid(*board.spawn) is False
    assert board.static_solid(*board.goal) is False


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


# -- the moving parts ----------------------------------------------------

MOVING = [
    "....................",
    "....................",
    "....................",
    "....................",
    "..........|.........",
    "..........|.........",
    "..........|.........",
    "..----....|.........",
    "..........|.........",
    "....................",
    "....................",
    "....................",
    "....................",
    "..@...=..E..=......G",
    "====================",
    "====================",
]


def moving() -> Level:
    return Level("moving", MOVING)


def test_a_run_of_track_glyphs_becomes_one_mover():
    horizontal = [m for m in moving().movers if m.horizontal]

    assert len(horizontal) == 1
    assert horizontal[0].cells == [(2, 7), (3, 7), (4, 7), (5, 7)]


def test_a_vertical_run_becomes_a_vertical_mover():
    vertical = [m for m in moving().movers if not m.horizontal]

    assert len(vertical) == 1
    assert vertical[0].cells == [(10, 4), (10, 5), (10, 6), (10, 7), (10, 8)]


def test_two_separate_tracks_are_two_movers():
    rows = list(MOVING)
    rows[7] = "..----....|.---....."
    level = Level("two", rows)

    assert len([m for m in level.movers if m.horizontal]) == 2


def test_a_mover_slides_along_its_track_and_comes_back():
    mover = [m for m in moving().movers if m.horizontal][0]
    seen = {mover.offset(tick) for tick in range(mover.period)}

    assert seen == set(range(mover.span + 1))
    assert mover.offset(0) == mover.offset(mover.period)


def test_a_mover_occupies_two_cells_wherever_it_is():
    mover = [m for m in moving().movers if m.horizontal][0]

    for tick in range(0, mover.period, 3):
        assert len(mover.occupied(tick)) == 2


def test_a_track_too_short_to_move_on_is_refused():
    rows = ["." * 20 for _ in range(16)]
    rows[9] = "..@--............G.."
    rows[14] = "=" * 20
    with pytest.raises(LevelError, match="at least"):
        Level("stub", rows)


def test_an_enemy_paces_its_ledge_and_turns_at_the_drop():
    enemy = moving().enemies[0]
    columns = {x for x, _ in enemy.path}

    assert len(enemy.path) > 1, "the enemy never moved"
    assert min(columns) >= 7, "the enemy walked through the left wall"
    assert max(columns) <= 11, "the enemy walked through the right wall"


def test_an_enemy_returns_to_where_it_started():
    enemy = moving().enemies[0]

    assert enemy.at(0) == enemy.at(enemy.period)


def test_the_level_period_covers_every_moving_thing():
    level = moving()

    for mover in level.movers:
        assert level.period % mover.period == 0
    for enemy in level.enemies:
        assert level.period % enemy.period == 0


def test_a_level_with_nothing_moving_has_a_period_of_one():
    assert level().period == 1
    assert level().moves is False


def test_a_level_with_movers_says_so():
    assert moving().moves is True


# -- the new tiles -------------------------------------------------------


def _tiles(row: str) -> Level:
    rows = ["." * 20 for _ in range(16)]
    rows[13] = "..@..............G.."
    rows[14] = row.ljust(20, "=")
    rows[15] = "=" * 20
    return Level("tiles", rows)


def test_ice_bounce_crumble_and_conveyors_are_all_solid():
    level = _tiles("==ii=bb=cc=<<=>>====")

    for x in range(20):
        assert level.static_solid(x, 14) is True, x


def test_each_special_floor_is_remembered_separately():
    level = _tiles("==ii=bb=cc=<<=>>====")

    assert level.ice == frozenset({(2, 14), (3, 14)})
    assert level.bounce == frozenset({(5, 14), (6, 14)})
    assert level.crumble == frozenset({(8, 14), (9, 14)})


def test_a_conveyor_remembers_which_way_it_pushes():
    level = _tiles("==ii=bb=cc=<<=>>====")

    assert level.conveyors[(11, 14)] == -1
    assert level.conveyors[(14, 14)] == 1


def test_too_many_crumbling_tiles_are_refused():
    with pytest.raises(LevelError, match="crumbling"):
        _tiles("ccccc===============")


def test_portals_are_linked_to_each_other():
    rows = ["." * 20 for _ in range(16)]
    rows[13] = "..@.p..........p.G.."
    rows[14] = "=" * 20
    rows[15] = "=" * 20
    level = Level("portals", rows)

    assert level.portals[(4, 13)] == (15, 13)
    assert level.portals[(15, 13)] == (4, 13)


def test_a_level_with_no_portals_has_none():
    assert level().portals == {}


def test_a_single_unpaired_portal_is_refused():
    rows = ["." * 20 for _ in range(16)]
    rows[13] = "..@.p............G.."
    rows[14] = "=" * 20
    rows[15] = "=" * 20
    with pytest.raises(LevelError, match="pairs"):
        Level("lonely", rows)
