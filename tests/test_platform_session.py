"""Every screen, every transition, and a frame for each one.

Written the way the Game of Life session tests are: the session takes a
sink, so a recording function stands in for the panel and the exact
pixels can be read back. The rule being enforced is the same one -- if
something changed, the panel was told.
"""

from __future__ import annotations

import pytest

from pi_menu.display.protocol import FRAME_BYTES
from pi_menu.platformer import render
from pi_menu.platformer.levels import LEVELS
from pi_menu.platformer.progress import Progress
from pi_menu.platformer.session import (
    BACK,
    DOWN,
    FLASH_TICKS,
    LEFT,
    PLAY_ENTRY,
    PICKER_ENTRY,
    RIGHT,
    SELECT,
    UP,
    PlatformSession,
    Screen,
)


class Recorder:
    """Collects the frames a session pushes."""

    def __init__(self):
        self.frames: list[bytes] = []

    def __call__(self, framebuffer: bytes) -> None:
        self.frames.append(framebuffer)

    @property
    def last(self) -> bytes:
        return self.frames[-1]


@pytest.fixture
def session(tmp_path):
    recorder = Recorder()
    progress = Progress(tmp_path / "progress.json")
    return PlatformSession(recorder, progress=progress), recorder


# -- opening -------------------------------------------------------------


def test_opening_the_session_shows_the_menu(session):
    game, recorder = session

    assert game.screen is Screen.MENU
    assert len(recorder.frames) == 1
    assert recorder.last == render.draw_menu(PLAY_ENTRY, phase=0)


def test_every_frame_is_the_full_size(session):
    game, recorder = session
    game.press(DOWN)
    game.press(SELECT)
    game.tick()

    assert all(len(frame) == FRAME_BYTES for frame in recorder.frames)


def test_the_menu_starts_on_the_first_unfinished_level(tmp_path):
    progress = Progress(tmp_path / "p.json")
    progress.mark(LEVELS[0].id)
    progress.mark(LEVELS[1].id)

    game = PlatformSession(Recorder(), progress=progress)

    assert game.index == 2


def test_a_finished_game_starts_back_at_the_first_level(tmp_path):
    progress = Progress(tmp_path / "p.json")
    for level in LEVELS:
        progress.mark(level.id)

    game = PlatformSession(Recorder(), progress=progress)

    assert game.index == 0


# -- the menu ------------------------------------------------------------


def test_down_moves_to_the_levels_entry(session):
    game, _ = session

    game.press(DOWN)

    assert game.menu_entry == PICKER_ENTRY


def test_up_moves_back_to_play(session):
    game, _ = session
    game.press(DOWN)

    game.press(UP)

    assert game.menu_entry == PLAY_ENTRY


def test_the_menu_selection_does_not_wrap_past_the_ends(session):
    game, _ = session
    game.press(UP)
    assert game.menu_entry == PLAY_ENTRY

    game.press(DOWN)
    game.press(DOWN)
    assert game.menu_entry == PICKER_ENTRY


def test_choosing_play_starts_the_level(session):
    game, _ = session

    game.press(SELECT)

    assert game.screen is Screen.PLAY
    assert game.world.level is LEVELS[0]


def test_choosing_levels_opens_the_picker(session):
    game, _ = session
    game.press(DOWN)

    game.press(SELECT)

    assert game.screen is Screen.PICKER


def test_every_menu_press_pushes_a_frame(session):
    game, recorder = session
    before = len(recorder.frames)

    game.press(DOWN)
    game.press(UP)

    assert len(recorder.frames) == before + 2


# -- the picker ----------------------------------------------------------


@pytest.fixture
def picker(session):
    game, recorder = session
    game.press(DOWN)
    game.press(SELECT)
    return game, recorder


def test_right_moves_the_cursor_along(picker):
    game, _ = picker
    start = game.index

    game.press(RIGHT)

    assert game.index == start + 1


def test_down_moves_the_cursor_a_whole_row(picker):
    game, _ = picker
    game.index = 0

    game.press(DOWN)

    assert game.index == render.PICKER_COLUMNS


def test_the_cursor_stops_at_the_first_level(picker):
    game, _ = picker
    game.index = 0

    game.press(LEFT)
    game.press(UP)

    assert game.index == 0


def test_the_cursor_stops_at_the_last_level(picker):
    game, _ = picker
    game.index = len(LEVELS) - 1

    game.press(RIGHT)
    game.press(DOWN)

    assert game.index == len(LEVELS) - 1


def test_choosing_a_level_plays_it(picker):
    game, _ = picker
    game.index = 3

    game.press(SELECT)

    assert game.screen is Screen.PLAY
    assert game.world.level is LEVELS[3]


def test_back_returns_to_the_menu(picker):
    game, _ = picker

    game.press(BACK)

    assert game.screen is Screen.MENU


def test_the_picker_shows_which_levels_are_finished(tmp_path):
    progress = Progress(tmp_path / "p.json")
    progress.mark(LEVELS[2].id)
    recorder = Recorder()
    game = PlatformSession(recorder, progress=progress)
    game.press(DOWN)
    game.press(SELECT)

    assert 2 in game.finished_indexes()


# -- playing -------------------------------------------------------------


@pytest.fixture
def playing(session):
    game, recorder = session
    game.press(SELECT)
    return game, recorder


def test_a_tick_moves_the_player(playing):
    game, _ = playing
    game.press(RIGHT)
    start = game.world.x

    for _ in range(10):
        game.tick()

    assert game.world.x > start


def test_letting_go_of_a_key_stops_the_player(playing):
    game, _ = playing
    game.press(RIGHT)
    for _ in range(10):
        game.tick()

    game.release(RIGHT)
    for _ in range(10):
        game.tick()

    assert game.world.vx == pytest.approx(0.0)


def test_every_tick_pushes_a_frame(playing):
    game, recorder = playing
    before = len(recorder.frames)

    game.tick()
    game.tick()

    assert len(recorder.frames) == before + 2


def test_starting_a_level_forgets_keys_held_in_the_menu(session):
    game, _ = session
    game.press(RIGHT)  # nudging the menu

    game.press(SELECT)

    assert game.held == frozenset()


def test_back_abandons_the_level_for_the_menu(playing):
    game, _ = playing

    game.press(BACK)

    assert game.screen is Screen.MENU


# -- dying ---------------------------------------------------------------


def _die(game):
    """Drop the player out of the world, which is one of the two ways to die."""
    game.world.y = float(game.world.level.height)
    game.tick()


def test_dying_flashes_and_then_restarts_the_level(playing):
    game, recorder = playing
    game.press(RIGHT)
    for _ in range(6):
        game.tick()
    moved = game.world.x

    _die(game)
    assert game.screen is Screen.DEAD
    for _ in range(FLASH_TICKS + 1):
        game.tick()

    assert game.screen is Screen.PLAY
    assert game.world.x < moved, "the player was not put back on the spawn"
    assert game.world.alive is True


def test_the_death_flash_is_red(playing):
    game, recorder = playing
    _die(game)

    frames = []
    for _ in range(FLASH_TICKS):
        game.tick()
        frames.append(recorder.last)

    assert render.flash(render.DEATH_FLASH) in frames


def test_dying_puts_the_coins_back(playing):
    game, _ = playing
    game.world.coins = frozenset()

    _die(game)
    for _ in range(FLASH_TICKS + 1):
        game.tick()

    assert game.world.coins == LEVELS[0].coins


# -- winning -------------------------------------------------------------


def _win(game):
    """Put the player on the goal with every coin already taken."""
    game.world.coins = frozenset()
    game.world.x, game.world.y = (float(n) for n in game.world.level.goal)
    game.tick()


def test_winning_records_the_level(playing):
    game, _ = playing

    _win(game)

    assert game.progress.is_done(LEVELS[0].id)


def test_winning_moves_on_to_the_next_level(playing):
    game, _ = playing

    _win(game)
    assert game.screen is Screen.WON
    for _ in range(FLASH_TICKS + 1):
        game.tick()

    assert game.screen is Screen.PLAY
    assert game.world.level is LEVELS[1]


def test_winning_the_last_level_returns_to_the_menu(session):
    game, _ = session
    game.index = len(LEVELS) - 1
    game.press(SELECT)

    _win(game)
    for _ in range(FLASH_TICKS + 1):
        game.tick()

    assert game.screen is Screen.MENU


def test_the_win_flash_is_green(playing):
    game, recorder = playing
    _win(game)

    frames = []
    for _ in range(FLASH_TICKS):
        game.tick()
        frames.append(recorder.last)

    assert render.flash(render.WIN_FLASH) in frames


# -- what the window says ------------------------------------------------


def test_the_status_names_the_screen(session):
    game, _ = session
    assert "menu" in game.status_text().lower()

    game.press(SELECT)
    assert "1." in game.status_text()


def test_the_status_counts_the_coins_left(playing):
    game, _ = playing

    assert str(len(LEVELS[0].coins)) in game.status_text()


# -- all the way to the panel --------------------------------------------


def test_the_game_reaches_the_real_panel(pico, tmp_path):
    """Menu, picker and gameplay must all light real LEDs.

    Everything above this file is checked against a recording sink, which
    proves the frames are right but not that they survive the trip. This
    drives the actual Pico firmware over a pseudo-terminal, so a frame
    that the wire protocol mangles fails here.
    """
    pytest.importorskip("serial")
    from pi_menu.display.serial_link import SerialDisplay

    firmware, path = pico
    display = SerialDisplay(port=path, brightness=1.0)

    def sink(framebuffer: bytes) -> None:
        display.set_frame(framebuffer)
        display.show()

    def lit_on_panel():
        return {
            position
            for position, colour in firmware.graphics.pixels.items()
            if colour != (0, 0, 0)
        }

    try:
        game = PlatformSession(
            sink, progress=Progress(tmp_path / "p.json"), levels=LEVELS[:2]
        )

        # The menu: the words are on the panel.
        menu_pixels = lit_on_panel()
        assert menu_pixels, "the menu never reached the LEDs"

        # The picker: a different screen lights different LEDs.
        game.press(DOWN)
        game.press(SELECT)
        assert lit_on_panel() != menu_pixels

        # Gameplay: the player is on the panel, in the right colour.
        game.press(BACK)
        game.press(UP)
        game.press(SELECT)
        game.tick()
        assert game.screen is Screen.PLAY
        player_x, player_y = game.world.pixel
        assert firmware.graphics.pixels[(player_x, player_y)] == render.PLAYER
    finally:
        display.close()
