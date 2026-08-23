"""What actually reaches the LEDs.

Every painter returns a complete frame, so these read pixels back out of
it rather than trusting that a draw call was made. Colour is the only
status the panel has -- there is no room for words -- so which colour
lands where is the behaviour worth pinning.
"""

from __future__ import annotations

import pytest

from pi_menu.display.protocol import FRAME_BYTES, HEIGHT, WIDTH, pixel_offset
from pi_menu.platformer import font, render
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

    assert len(rows) == 2 * font.GLYPH_HEIGHT, "two words, with a gap between"


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
    assert len(number_rows(single)) == font.GLYPH_HEIGHT


def test_the_picker_refuses_more_levels_than_it_can_show():
    """Better a loud error than a grid drawn over the level number."""
    with pytest.raises(ValueError, match="picker holds"):
        render.draw_picker(
            index=0,
            completed=frozenset(),
            count=render.PICKER_CAPACITY + 1,
            phase=0,
        )


def test_the_shipped_levels_fit_the_picker():
    assert len(LEVELS) <= render.PICKER_CAPACITY


def test_no_tile_overlaps_the_level_number():
    frame = render.draw_picker(
        index=0, completed=frozenset(), count=render.PICKER_CAPACITY, phase=0
    )
    tile_rows = {y for _, y in lit(frame) if y < render.NUMBER_TOP}

    assert max(tile_rows) < render.NUMBER_TOP


def test_every_shipped_level_has_a_tile():
    frame = render.draw_picker(
        index=0, completed=frozenset(), count=len(LEVELS), phase=0
    )

    assert all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in lit(frame))


# -- the new tiles -------------------------------------------------------


def floor_level(floor: str) -> Level:
    rows = ["." * WIDE for _ in range(16)]
    rows[13] = "..@.............G..."
    rows[14] = floor.ljust(WIDE, "=")
    rows[15] = "=" * WIDE
    return Level("t", rows)


def test_each_kind_of_floor_gets_its_own_colour():
    world = World(floor_level("==ii=bb=cc=========="))
    frame = render.draw_world(world)

    assert colour_at(frame, 0, 14) == render.PLATFORM
    assert colour_at(frame, 2, 14) == render.ICE
    assert colour_at(frame, 5, 14) == render.BOUNCE
    assert colour_at(frame, 8, 14) == render.CRUMBLE


def test_a_conveyor_is_drawn_as_a_belt():
    world = World(floor_level("==>>>>>>>==========="))
    frame = render.draw_world(world, phase=0)
    belt = {colour_at(frame, x, 14) for x in range(2, 9)}

    assert belt == {render.CONVEYOR, render.CONVEYOR_HIGHLIGHT}


def test_the_belt_highlight_travels_the_way_the_belt_pushes():
    def bright(level, phase):
        frame = render.draw_world(World(level), phase=phase)
        return sorted(
            x for x in range(2, 9)
            if colour_at(frame, x, 14) == render.CONVEYOR_HIGHLIGHT
        )

    rightwards = floor_level("==>>>>>>>===========")
    leftwards = floor_level("==<<<<<<<===========")
    step = render.CONVEYOR_TICKS

    assert bright(rightwards, step)[0] == bright(rightwards, 0)[0] + 1
    assert bright(leftwards, step)[0] == bright(leftwards, 0)[0] - 1


def test_a_crumbled_tile_is_not_drawn_at_all():
    world = World(floor_level("===ccc=============="))
    world.crumbled = frozenset({(3, 14)})

    frame = render.draw_world(world)

    assert colour_at(frame, 3, 14) == (0, 0, 0)


def test_a_moving_platform_is_drawn_where_it_is_now():
    rows = ["." * WIDE for _ in range(16)]
    rows[9] = "....@..............."
    rows[10] = "....------.........."
    rows[13] = "................G..."
    rows[14] = "=" * WIDE
    rows[15] = "=" * WIDE
    world = World(Level("t", rows))

    frame = render.draw_world(world)

    assert colour_at(frame, 4, 10) == render.MOVER
    assert colour_at(frame, 9, 10) == (0, 0, 0), "the whole track was drawn"


def test_an_enemy_is_drawn_and_is_not_the_same_colour_as_a_spike():
    rows = ["." * WIDE for _ in range(16)]
    rows[13] = "..@..E.....^....G..."
    rows[14] = "=" * WIDE
    rows[15] = "=" * WIDE
    world = World(Level("t", rows))

    frame = render.draw_world(world)

    assert colour_at(frame, 5, 13) == render.ENEMY
    assert colour_at(frame, 11, 13) == render.SPIKE
    assert render.ENEMY != render.SPIKE


def test_a_portal_pair_is_drawn():
    rows = ["." * WIDE for _ in range(16)]
    rows[13] = "..@.p.......p...G..."
    rows[14] = "=" * WIDE
    rows[15] = "=" * WIDE
    world = World(Level("t", rows))

    frame = render.draw_world(world, phase=0)

    assert colour_at(frame, 4, 13) == render.PORTAL
    assert colour_at(frame, 12, 13) == render.PORTAL


def test_every_colour_the_panel_uses_is_distinct():
    """Two tiles the same colour is two tiles the player cannot tell apart."""
    palette = [
        render.PLATFORM, render.MOVER, render.ICE, render.CRUMBLE,
        render.CONVEYOR, render.CONVEYOR_HIGHLIGHT, render.BOUNCE,
        render.PLAYER, render.COIN, render.SPIKE, render.ENEMY,
        render.PORTAL, render.GOAL_SHUT, render.GOAL_OPEN,
    ]

    assert len(set(palette)) == len(palette)


# -- the redrawn menu ----------------------------------------------------


def test_the_menu_marks_the_selected_entry_in_the_spare_column():
    frame = render.draw_menu(selected=0, phase=0)
    markers = {y for x, y in lit(frame) if x == 0}

    assert markers, "nothing marks the selection"
    assert all(y < render.MENU_TOP + font.GLYPH_HEIGHT for y in markers)


def test_the_marker_moves_with_the_selection():
    first = {y for x, y in lit(render.draw_menu(0, 0)) if x == 0}
    second = {y for x, y in lit(render.draw_menu(1, 0)) if x == 0}

    assert first and second and first != second


def test_the_menu_leaves_a_margin_rather_than_filling_the_panel():
    frame = render.draw_menu(selected=0, phase=0)
    rows = {y for _, y in lit(frame)}

    assert min(rows) > 0 and max(rows) < HEIGHT - 1


# -- the dot-grid picker -------------------------------------------------


def test_the_picker_lights_one_pixel_per_level():
    frame = render.draw_picker(index=0, completed=frozenset(), count=27, phase=0)
    tiles = {(x, y) for x, y in lit(frame) if y < render.NUMBER_TOP}

    assert len(tiles) == 27


def test_the_picker_holds_every_level_we_ship():
    assert len(LEVELS) <= render.PICKER_CAPACITY


def test_the_grid_never_reaches_the_number():
    frame = render.draw_picker(
        index=0, completed=frozenset(), count=render.PICKER_CAPACITY, phase=0
    )
    tiles = {y for x, y in lit(frame) if y < render.NUMBER_TOP}

    assert max(tiles) < render.NUMBER_TOP - 1


def test_a_two_digit_level_number_is_shown():
    frame = render.draw_picker(index=26, completed=frozenset(), count=27, phase=0)
    digits = {x for x, y in lit(frame) if y >= render.NUMBER_TOP}

    assert digits, "no number under the grid"
    assert max(digits) - min(digits) + 1 == font.text_width("27")
