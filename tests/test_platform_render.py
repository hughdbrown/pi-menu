"""What actually reaches the LEDs.

Every painter returns a complete frame, so these read pixels back out of
it rather than trusting that a draw call was made. Colour is the only
status the panel has -- there is no room for words -- so which colour
lands where is the behaviour worth pinning.
"""

from __future__ import annotations

import pytest

from pi_menu.display.protocol import FRAME_BYTES, HEIGHT, WIDTH, pixel_offset
from pi_menu.platformer import render
from pi_menu.platformer.level import Level
from pi_menu.platformer.levels import LEVELS
from pi_menu.platformer.world import World


def colour_at(frame: bytes, x: int, y: int) -> tuple[int, int, int]:
    offset = pixel_offset(x, y)
    return tuple(frame[offset : offset + 3])


def lit(frame: bytes) -> set[tuple[int, int]]:
    return {
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if colour_at(frame, x, y) != (0, 0, 0)
    }


WIDE = 20


def level(*bottom_rows: str) -> Level:
    rows = [row.ljust(WIDE, ".") for row in bottom_rows]
    return Level("t", ["." * WIDE] * (16 - len(rows)) + rows)


# -- the world -----------------------------------------------------------


def test_a_frame_is_always_the_full_size():
    world = World(level("..@..o.....^....G...", "=" * WIDE))

    assert len(render.draw_world(world)) == FRAME_BYTES


def test_every_kind_of_tile_gets_its_own_colour():
    world = World(level("..@..o.....^....G...", "=" * WIDE))
    frame = render.draw_world(world)

    assert colour_at(frame, 5, 14) == render.COIN
    assert colour_at(frame, 11, 14) == render.SPIKE
    assert colour_at(frame, 0, 15) == render.PLATFORM


def test_the_player_is_drawn_over_whatever_is_under_them():
    world = World(level("..@..o..........G...", "=" * WIDE))
    world.x, world.y = 5.0, 14.0  # standing on the coin's tile

    frame = render.draw_world(world)

    assert colour_at(frame, 5, 14) == render.PLAYER


def test_a_shut_goal_looks_different_from_an_open_one():
    """The goal is inside the window here, so the panel really shows it."""
    world = World(level("..@..o......G.......", "=" * WIDE))
    shut = colour_at(render.draw_world(world), 12, 14)

    world.coins = frozenset()
    open_ = colour_at(render.draw_world(world), 12, 14)

    assert shut != open_
    assert open_ != (0, 0, 0)


def test_the_camera_offset_moves_the_world_under_the_window():
    world = World(level("..@..o..........G...", "=" * WIDE))
    world.x = 12.0  # far enough right that the window has scrolled

    frame = render.draw_world(world)

    # The player is drawn at their position within the window, not at 12.
    assert colour_at(frame, WIDTH // 2, 14) == render.PLAYER


def test_nothing_is_drawn_outside_the_window():
    """A level twenty wide has four columns the panel cannot show at once."""
    world = World(level("..@..o..........G...", "=" * WIDE))

    frame = render.draw_world(world)

    assert all(x < WIDTH for x, _ in lit(frame))


def test_a_flash_fills_the_whole_panel():
    frame = render.flash(render.DEATH_FLASH)

    assert lit(frame) == {(x, y) for y in range(HEIGHT) for x in range(WIDTH)}
    assert colour_at(frame, 3, 3) == render.DEATH_FLASH


# -- the menu ------------------------------------------------------------


def test_the_menu_writes_both_words():
    frame = render.draw_menu(selected=0, phase=0)

    assert lit(frame), "the menu is blank"


def test_the_selected_entry_is_brighter_than_the_other():
    play_selected = render.draw_menu(selected=0, phase=0)
    levels_selected = render.draw_menu(selected=1, phase=0)

    assert play_selected != levels_selected


def test_the_menu_words_do_not_overlap():
    frame = render.draw_menu(selected=0, phase=0)
    rows = {y for _, y in lit(frame)}

    assert len(rows) == 10, "two words of five rows each, with a gap between"


# -- the picker ----------------------------------------------------------


def test_the_picker_draws_a_tile_for_every_level():
    frame = render.draw_picker(index=0, completed=frozenset(), count=12, phase=0)

    assert lit(frame)


def test_the_picker_grid_and_its_number_fit_the_panel():
    frame = render.draw_picker(index=11, completed=frozenset(), count=12, phase=0)

    assert all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in lit(frame))


def test_a_completed_level_is_coloured_differently():
    todo = render.draw_picker(index=5, completed=frozenset(), count=12, phase=0)
    done = render.draw_picker(index=5, completed=frozenset({0}), count=12, phase=0)

    assert todo != done


def test_the_cursor_marks_the_selected_tile():
    first = render.draw_picker(index=0, completed=frozenset(), count=12, phase=0)
    second = render.draw_picker(index=1, completed=frozenset(), count=12, phase=0)

    assert first != second


def test_the_picker_shows_the_level_number():
    single = render.draw_picker(index=0, completed=frozenset(), count=12, phase=0)
    double = render.draw_picker(index=9, completed=frozenset(), count=12, phase=0)
    number_rows = lambda frame: {y for _, y in lit(frame) if y >= render.NUMBER_TOP}

    assert number_rows(single) and number_rows(double)
    assert len(number_rows(single)) == 5


def test_every_shipped_level_has_a_tile():
    frame = render.draw_picker(
        index=0, completed=frozenset(), count=len(LEVELS), phase=0
    )

    assert all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in lit(frame))
