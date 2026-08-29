"""Every screen, every transition, and a frame for each one.

Written the way the Game of Life session tests are: the session takes a
sink, so a recording function stands in for the panel and the exact
pixels can be read back. The rule being enforced is the same one -- if
something changed, the panel was told.
"""

from __future__ import annotations

import pytest

from pi_menu.display.protocol import FRAME_BYTES
from pi_menu.platformer import world as physics
from pi_menu.platformer import render
from pi_menu.platformer.levels import LEVELS
from pi_menu.platformer.progress import Progress
from pi_menu.platformer.session import (
    AUTO_ENTRY,
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
    assert recorder.last == render.draw_menu(PLAY_ENTRY, phase=0, sound="music")


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

    for _ in range(4):
        game.press(DOWN)
    assert game.menu_entry == AUTO_ENTRY


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


def test_a_key_still_held_when_the_level_starts_stays_held(session):
    """The window only reports a press when a key goes from up to down.

    So dropping held keys here would leave the player unable to move
    until they let go of a key they were already holding.
    """
    game, _ = session
    game.press(RIGHT)

    game.press(SELECT)

    assert game.held == frozenset({physics.RIGHT})


def test_a_key_held_through_a_death_survives_the_restart(playing):
    game, _ = playing
    game.press(RIGHT)
    held = game.held

    _die(game)
    for _ in range(FLASH_TICKS + 1):
        game.tick()

    assert game.held == held


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
    """Put the player on the goal with nothing left standing in the way."""
    game.world.coins = frozenset()
    game.world.boss_done = True  # boss levels also gate the goal on this
    game.world.boss_tick = None
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


# -- one whole level, through the keys the player actually presses -------


@pytest.mark.parametrize("index", [0, len(LEVELS) - 1], ids=["first", "last"])
def test_a_level_can_be_finished_by_pressing_keys(tmp_path, index):
    """The solver finds the route; this proves the plumbing carries it.

    Everything else here pokes the session's state directly. This takes
    a winning move sequence and replays it as presses and releases
    through the same path the window uses, so a mistake in the key
    mapping, the held-key set or the tick order shows up as a level that
    cannot be completed. The last level is included because it is the
    one that uses ice, a ferry, a belt, an enemy, a crumbling floor and
    a bounce pad -- every moving part at once.
    """
    from platform_solver import HOLD_TICKS, solve

    chosen = LEVELS[index]
    to_session = {physics.LEFT: LEFT, physics.RIGHT: RIGHT, physics.JUMP: UP}
    recorder = Recorder()
    game = PlatformSession(
        recorder, progress=Progress(tmp_path / "p.json"), levels=[chosen]
    )
    game.press(SELECT)
    assert game.screen is Screen.PLAY

    down = set()
    for move in solve(chosen):
        wanted = {to_session[key] for key in move}
        for key in wanted - down:
            game.press(key)
        for key in down - wanted:
            game.release(key)
        down = wanted
        for _ in range(HOLD_TICKS):
            game.tick()
            if game.screen is not Screen.PLAY:
                break
        if game.screen is not Screen.PLAY:
            break

    assert game.screen is Screen.WON
    assert game.progress.is_done(chosen.id)


# -- the music -----------------------------------------------------------


class MusicRecorder:
    """Collects the notes a session's music sends."""

    def __init__(self):
        self.notes = []

    def __call__(self, channel, waveform, hertz, volume):
        self.notes.append((channel, waveform, hertz, volume))


@pytest.fixture
def musical(tmp_path):
    from pi_menu import music as chiptune

    notes = MusicRecorder()
    game = PlatformSession(
        Recorder(),
        progress=Progress(tmp_path / "p.json"),
        music=chiptune.Player(notes),
    )
    return game, notes


def test_the_menu_plays_the_title_tune(musical):
    from pi_menu import music as chiptune

    game, _ = musical

    assert game.music.tune is chiptune.TITLE


def test_starting_a_level_changes_the_tune(musical):
    from pi_menu import music as chiptune

    game, _ = musical
    game.press(SELECT)

    assert game.music.tune is not chiptune.TITLE


def test_the_last_level_plays_the_finale(musical):
    from pi_menu import music as chiptune

    game, _ = musical
    game.index = len(LEVELS) - 1
    game.press(SELECT)

    assert game.music.tune is chiptune.FINALE


def test_dying_plays_the_death_sting(playing_musical):
    from pi_menu import music as chiptune

    game = playing_musical
    game.world.y = float(game.world.level.height)
    game.tick()

    assert game.music.tune is chiptune.DEATH


def test_a_tick_moves_the_music_on(musical):
    game, notes = musical
    before = len(notes.notes)

    for _ in range(30):
        game.tick()

    assert len(notes.notes) > before


def test_leaving_the_game_silences_the_panel(musical):
    game, notes = musical
    for _ in range(10):
        game.tick()
    notes.notes.clear()

    game.silence()

    assert notes.notes
    assert all(note[3] == 0 for note in notes.notes)


@pytest.fixture
def playing_musical(tmp_path):
    from pi_menu import music as chiptune

    game = PlatformSession(
        Recorder(),
        progress=Progress(tmp_path / "p.json"),
        music=chiptune.Player(MusicRecorder()),
    )
    game.press(SELECT)
    return game


# -- auto-play -----------------------------------------------------------


@pytest.fixture
def auto(session):
    game, recorder = session
    game.press(DOWN)
    game.press(DOWN)
    game.press(SELECT)
    return game, recorder


def test_the_third_menu_entry_starts_auto_play(auto):
    game, _ = auto

    assert game.screen is Screen.PLAY
    assert game.auto is True
    assert game.world.level is LEVELS[0]


def test_a_level_chosen_in_the_picker_carries_into_auto_play(tmp_path):
    """LVLS, move the cursor, Esc, AUTO: auto-play starts on that level.

    It used to start at level one regardless, which read as the picker
    throwing the selection away.
    """
    game = PlatformSession(Recorder(), progress=Progress(tmp_path / "p.json"))
    game.press(DOWN)
    game.press(SELECT)  # into the picker
    for _ in range(5):
        game.press(RIGHT)  # cursor to level 6
    game.press(BACK)  # back to the menu, selection kept

    game.press(DOWN)  # PLAY -> LVLS
    game.press(DOWN)  # LVLS -> AUTO
    game.press(SELECT)

    assert game.auto is True
    assert game.world.level is LEVELS[5]


def test_auto_play_plays_without_any_keys_held(auto):
    game, _ = auto
    start = game.world.x

    for _ in range(30):
        game.tick()

    assert game.world.x != start, "the pilot never moved the player"


def test_auto_play_wins_the_level_and_moves_to_the_next(auto):
    game, _ = auto
    from pi_menu.platformer.routes import ROUTES, TICKS_PER_MOVE

    budget = len(ROUTES[LEVELS[0].id]) * TICKS_PER_MOVE + FLASH_TICKS + 20
    for _ in range(budget):
        game.tick()
        if game.world is not None and game.world.level is LEVELS[1]:
            break

    assert game.world.level is LEVELS[1]
    assert game.auto is True, "auto-play stopped at the level change"


def test_right_skips_to_the_next_level_in_auto_play(auto):
    game, _ = auto

    game.press(RIGHT)

    assert game.world.level is LEVELS[1]
    assert game.auto is True


def test_left_from_the_first_level_wraps_to_the_last(auto):
    game, _ = auto

    game.press(LEFT)

    assert game.world.level is LEVELS[-1]


def test_escape_leaves_auto_play(auto):
    game, _ = auto

    game.press(BACK)

    assert game.screen is Screen.MENU
    assert game.auto is False


def test_ordinary_play_is_not_auto(session):
    game, _ = session
    game.press(SELECT)

    assert game.auto is False


def test_the_status_says_it_is_auto_playing(auto):
    game, _ = auto

    assert "auto-play" in game.status_text()


def test_arrow_keys_do_not_skip_levels_in_ordinary_play(session):
    game, _ = session
    game.press(SELECT)

    game.press(RIGHT)

    assert game.world.level is LEVELS[0]


# -- the sound setting ---------------------------------------------------


def _session_with_sound(tmp_path, sound):
    from pi_menu import music as chiptune
    from pi_menu.platformer.sound_settings import Sound  # noqa: F401

    notes = MusicRecorder()
    game = PlatformSession(
        Recorder(),
        progress=Progress(tmp_path / "p.json"),
        music=chiptune.Player(notes),
        sound=sound,
    )
    return game, notes


def test_sound_off_never_makes_a_sound(tmp_path):
    from pi_menu.platformer.sound_settings import Sound

    game, notes = _session_with_sound(tmp_path, Sound.OFF)
    game.press(SELECT)
    for _ in range(30):
        game.tick()

    assert game.music.tune is None
    assert notes.notes == []


def test_effects_mode_plays_no_background_tune(tmp_path):
    from pi_menu.platformer.sound_settings import Sound

    game, notes = _session_with_sound(tmp_path, Sound.EFFECTS)
    game.press(SELECT)
    for _ in range(30):
        game.tick()

    # Standing still: no events, so nothing to hear.
    assert game.music.tune is None
    assert notes.notes == []


def test_a_jump_blips_in_effects_mode(tmp_path):
    from pi_menu import music as chiptune
    from pi_menu.platformer.sound_settings import Sound

    game, notes = _session_with_sound(tmp_path, Sound.EFFECTS)
    game.press(SELECT)
    for _ in range(5):
        game.tick()  # land on the ground first
    game.press(UP)
    game.tick()

    assert game.music.tune is chiptune.JUMP_BLIP
    assert notes.notes, "the jump made no sound"


def test_a_coin_blips_somewhere_in_an_auto_run(tmp_path):
    from pi_menu import music as chiptune
    from pi_menu.platformer.sound_settings import Sound

    game, _ = _session_with_sound(tmp_path, Sound.EFFECTS)
    game.start(0, auto=True)

    heard = False
    for _ in range(600):
        game.tick()
        if game.music.tune is chiptune.COIN_BLIP:
            heard = True
            break
    assert heard, "the route collects every coin, yet no coin blipped"


def test_the_death_jingle_still_plays_in_effects_mode(tmp_path):
    from pi_menu import music as chiptune
    from pi_menu.platformer.sound_settings import Sound

    game, _ = _session_with_sound(tmp_path, Sound.EFFECTS)
    game.press(SELECT)
    game.world.y = float(game.world.level.height)
    game.tick()

    assert game.music.tune is chiptune.DEATH


def test_switching_sound_off_silences_immediately(musical):
    from pi_menu.platformer.sound_settings import Sound

    game, _ = musical
    assert game.music.tune is not None

    game.set_sound(Sound.OFF)

    assert game.music.tune is None


def test_switching_back_to_music_resumes_the_tune(musical):
    from pi_menu import music as chiptune
    from pi_menu.platformer.sound_settings import Sound

    game, _ = musical
    game.set_sound(Sound.OFF)
    game.set_sound(Sound.MUSIC)

    assert game.music.tune is chiptune.TITLE


def test_left_and_right_cycle_the_sound_on_the_menu(tmp_path):
    from pi_menu.platformer.sound_settings import Sound

    game, _ = _session_with_sound(tmp_path, Sound.MUSIC)

    game.press(RIGHT)
    assert game.sound is Sound.EFFECTS
    game.press(RIGHT)
    assert game.sound is Sound.OFF
    game.press(RIGHT)
    assert game.sound is Sound.MUSIC
    game.press(LEFT)
    assert game.sound is Sound.OFF


def test_cycling_the_sound_saves_the_choice(tmp_path):
    from pi_menu import music as chiptune
    from pi_menu.platformer.sound_settings import Sound

    saved = []
    game = PlatformSession(
        Recorder(),
        progress=Progress(tmp_path / "p.json"),
        music=chiptune.Player(MusicRecorder()),
        sound_saver=saved.append,
    )
    game.press(RIGHT)

    assert saved == [Sound.EFFECTS]


def test_the_menu_shows_which_sound_is_chosen(tmp_path):
    from pi_menu.platformer.sound_settings import Sound

    game, _ = _session_with_sound(tmp_path, Sound.MUSIC)
    frames = {}
    for mode in Sound:
        game.set_sound(mode)
        game.push()
        frames[mode] = game.framebuffer()

    assert len(set(frames.values())) == len(frames), (
        "every sound mode must look different on the menu"
    )
