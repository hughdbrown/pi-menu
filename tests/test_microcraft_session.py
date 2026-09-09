"""Every screen, every way between them, and a frame for each."""

from __future__ import annotations

import random

import pytest

from pi_menu.display.protocol import FRAME_BYTES, pixel_offset
from pi_menu.microcraft import render, tiles
from pi_menu.microcraft.inventory import Stack
from pi_menu.microcraft.player import JUMP_KEY, LEFT, RIGHT
from pi_menu.microcraft.session import (
    BACK_KEY,
    BREAK,
    CURSOR_DOWN,
    CURSOR_LEFT,
    CURSOR_RIGHT,
    CURSOR_UP,
    DROP,
    INVENTORY,
    LAYER,
    SELECT,
    TICK_MS,
    Screen,
    Session,
)
from pi_menu.microcraft.terrain import BACK, FRONT


class Recorder:
    def __init__(self):
        self.frames = []

    def __call__(self, frame: bytes) -> None:
        self.frames.append(frame)

    @property
    def last(self) -> bytes:
        return self.frames[-1]


def colour_at(frame: bytes, x: int, y: int) -> tuple:
    off = pixel_offset(x, y)
    return tuple(frame[off : off + 3])


@pytest.fixture
def game():
    recorder = Recorder()
    session = Session(recorder, seed=12345, rng=random.Random(1), wall_clock=lambda: 1_700_000_000)
    return session, recorder


def start(session: Session) -> None:
    session.cursor = [8, 6]
    session.press(SELECT)
    assert session.screen is Screen.WORLD


def put_cursor(session: Session, x: int, y: int) -> None:
    session.cursor = [x, y]


# -- opening -------------------------------------------------------------------


def test_the_session_opens_on_the_menu_with_a_frame_pushed(game):
    session, recorder = game
    assert session.screen is Screen.MENU
    assert len(recorder.frames) == 1 and len(recorder.last) == FRAME_BYTES
    # The panel and button are on screen, with the cursor inverting the button.
    assert colour_at(recorder.last, 3, 4) == render.PANEL_COLOUR


def test_a_fresh_session_picks_a_seed_and_a_seeded_one_repeats(game):
    session, _ = game
    other = Session(lambda f: None, seed=12345, rng=random.Random(1))
    assert other.player.x == session.player.x and other.player.y == session.player.y
    free = Session(lambda f: None)
    assert isinstance(free.seed, int)


def test_enter_on_the_button_starts_and_elsewhere_does_not(game):
    session, _ = game
    put_cursor(session, 0, 0)
    session.press(SELECT)
    assert session.screen is Screen.MENU
    put_cursor(session, 11, 7)
    session.press(SELECT)
    assert session.screen is Screen.WORLD


def test_the_demo_keeps_the_world_alive_behind_the_menu(game):
    session, recorder = game
    before = len(recorder.frames)
    for _ in range(10):
        session.tick()
    assert len(recorder.frames) == before + 10
    assert session.demo.index == 0 and session.demo.elapsed == pytest.approx(10 * TICK_MS)
    assert session.now_ms == pytest.approx(10 * TICK_MS)


def test_the_player_spawns_standing_on_dry_land_at_noon(game):
    session, _ = game
    gen = session.world.gen
    assert not gen.is_water_column(session.player.x)
    assert session.player.y == gen.front_height(session.player.x) - 1
    assert session.day.local_day_frac(session.player.x, 0) == pytest.approx(0.5)


# -- the cursor ------------------------------------------------------------------


def test_the_cursor_moves_one_pixel_and_stops_at_the_edges(game):
    session, recorder = game
    session.press(CURSOR_RIGHT)
    assert session.cursor == [9, 6]
    session.press(CURSOR_DOWN)
    assert session.cursor == [9, 7]
    for _ in range(20):
        session.press(CURSOR_LEFT)
        session.press(CURSOR_UP)
    assert session.cursor == [0, 0]
    assert len(recorder.frames) > 40  # every press pushed a frame


def test_the_cursor_is_drawn_inverted_on_every_screen(game):
    session, recorder = game
    start(session)
    put_cursor(session, 3, 3)
    session.push()
    with_cursor = colour_at(recorder.last, 3, 3)
    put_cursor(session, 4, 4)
    session.push()
    without = colour_at(recorder.last, 3, 3)
    # Within one: the canvas rounds after inverting its float pixels.
    assert all(abs(a - (255 - b)) <= 1 for a, b in zip(with_cursor, without))


# -- the world -------------------------------------------------------------------


def test_held_keys_move_the_player_and_release_stops_them(game):
    session, _ = game
    start(session)
    x0 = session.player.x
    session.press(RIGHT)
    for _ in range(10):
        session.tick()
    assert session.player.x > x0
    session.release(RIGHT)
    assert RIGHT not in session.held
    x1 = session.player.x
    for _ in range(20):
        session.tick()
    assert session.player.x - x1 < 0.2


def test_a_tick_runs_three_physics_steps(game):
    session, _ = game
    start(session)
    session.press(JUMP_KEY)
    session.tick()
    session.release(JUMP_KEY)
    # One tick of a 0.32 jump minus three frames of gravity.
    assert session.player.vy == pytest.approx(-0.32 + 3 * 0.02, abs=0.02)


def test_the_status_line_names_the_held_block_the_layer_and_the_time(game):
    session, _ = game
    start(session)
    text = session.status_text()
    assert "dirt x16" in text and "front" in text and "12:00" in text
    session.press(LAYER)
    assert "background" in session.status_text()
    session.select_slot(2)
    assert "stone x16" in session.status_text()


def test_placing_and_breaking_through_the_cursor(game):
    session, _ = game
    start(session)
    put_cursor(session, 12, 6)  # block (6, 3) of the view: right of the player, at head height
    target = session.cursor_world()
    assert target is not None
    wx, wy = target
    session.world.set(FRONT, wx, wy, tiles.SKY)
    session.press(SELECT)
    assert session.world.get(FRONT, wx, wy) == tiles.DIRT
    assert session.inventory.held == Stack(tiles.DIRT, 15)

    session.press(BREAK)
    for _ in range(31):  # 1550 ms of a 1500 ms dirt block
        session.tick()
    session.release(BREAK)
    assert session.world.get(FRONT, wx, wy) == tiles.SKY
    assert session.inventory.held == Stack(tiles.DIRT, 16)


def test_the_layer_key_aims_at_the_background(game):
    session, _ = game
    start(session)
    put_cursor(session, 12, 2)
    wx, wy = session.cursor_world()
    session.world.set(BACK, wx, wy, tiles.SKY)
    session.world.set(FRONT, wx, wy, tiles.SKY)
    session.press(LAYER)
    session.press(SELECT)
    assert session.world.get(BACK, wx, wy) == tiles.DIRT
    assert session.world.get(FRONT, wx, wy) == tiles.SKY


def test_three_quick_q_presses_drop_one_of_the_held_item(game):
    session, _ = game
    start(session)
    session.press(DROP)
    session.press(DROP)
    assert not session.drops.items
    session.press(DROP)
    assert len(session.drops.items) == 1 and session.drops.items[0].kind == tiles.DIRT
    assert session.inventory.held == Stack(tiles.DIRT, 15)


def test_slow_q_presses_do_not_drop(game):
    session, _ = game
    start(session)
    for _ in range(3):
        session.press(DROP)
        for _ in range(20):
            session.tick()  # a second between presses
    assert not session.drops.items


def test_escape_from_the_world_returns_to_the_menu_and_keeps_the_world(game):
    session, _ = game
    start(session)
    session.press(RIGHT)
    for _ in range(10):
        session.tick()
    session.release(RIGHT)
    x = session.player.x
    session.press(BACK_KEY)
    assert session.screen is Screen.MENU
    start(session)
    assert session.player.x == x


# -- the inventory screens ---------------------------------------------------------


def test_e_opens_and_closes_the_inventory_and_the_world_stands_still(game):
    session, _ = game
    start(session)
    session.press(INVENTORY)
    assert session.screen is Screen.INVENTORY
    session.press(RIGHT)
    x = session.player.x
    for _ in range(10):
        session.tick()
    assert session.player.x == x
    session.release(RIGHT)
    session.press(INVENTORY)
    assert session.screen is Screen.WORLD


def test_the_inventory_exit_button_and_escape_both_close_it(game):
    session, _ = game
    start(session)
    session.press(INVENTORY)
    put_cursor(session, 15, 0)
    session.press(SELECT)
    assert session.screen is Screen.WORLD
    session.press(INVENTORY)
    session.press(BACK_KEY)
    assert session.screen is Screen.WORLD


def test_moving_a_stack_on_the_inventory_screen(game):
    session, _ = game
    start(session)
    session.press(INVENTORY)
    put_cursor(session, 0, 14)  # hotbar slot 0: grass x5
    session.press(SELECT)
    assert session.inventory.selection == ("hotbar", 0)
    put_cursor(session, 15, 11)  # backpack slot 31, empty
    session.press(SELECT)
    assert session.inventory.hotbar[0] is None
    assert session.inventory.backpack[31] == Stack(tiles.GRASS, 5)


def test_the_bench_opens_from_the_inventory_and_returns_leftovers_on_exit(game):
    session, _ = game
    start(session)
    session.press(INVENTORY)
    put_cursor(session, 12, 0)
    session.press(SELECT)
    assert session.screen is Screen.BENCH
    # Put the logs (hotbar 3) into the grid, craft planks, then leave.
    put_cursor(session, 6, 14)
    session.press(SELECT)
    put_cursor(session, 1, 1)
    session.press(SELECT)
    assert session.inventory.craft[0] == Stack(tiles.WOOD, 8)
    put_cursor(session, 8, 2)
    session.press(SELECT)
    assert session.inventory.craft_output[0] == Stack(tiles.WOOD_PLANKS, 4)
    session.press(BACK_KEY)
    assert session.screen is Screen.WORLD
    assert all(s is None for s in session.inventory.craft)
    assert Stack(tiles.WOOD_PLANKS, 4) in session.inventory.hotbar
    assert Stack(tiles.WOOD, 7) in session.inventory.hotbar + session.inventory.backpack


def test_a_placed_table_opens_the_table_screen_unless_a_stick_is_held(game):
    session, _ = game
    start(session)
    put_cursor(session, 12, 6)
    wx, wy = session.cursor_world()
    session.world.set(FRONT, wx, wy, tiles.CRAFTING_TABLE)
    session.inventory.hotbar[1] = Stack(tiles.STICK, 1)
    session.press(SELECT)
    assert session.screen is Screen.WORLD  # a stick taps to light it instead
    session.inventory.hotbar[1] = Stack(tiles.DIRT, 1)
    session.press(SELECT)
    assert session.screen is Screen.TABLE
    put_cursor(session, 14, 0)
    session.press(SELECT)
    assert session.screen is Screen.WORLD


def test_every_screen_renders_a_full_frame(game):
    session, recorder = game
    start(session)
    for screen, opener in (
        (Screen.INVENTORY, lambda: session.press(INVENTORY)),
    ):
        opener()
        assert session.screen is screen
        assert len(recorder.last) == FRAME_BYTES
        session.press(BACK_KEY)
    session.screen = Screen.BENCH
    session.push()
    assert len(recorder.last) == FRAME_BYTES
    session.screen = Screen.TABLE
    session.push()
    assert len(recorder.last) == FRAME_BYTES


# -- the clock -----------------------------------------------------------------------


def test_fluids_step_on_their_own_schedule(game):
    session, _ = game
    start(session)
    px, py = int(session.player.x), int(session.player.y)
    # A water source in the open sky above the player.
    session.world.set(FRONT, px, py - 6, tiles.WATER)
    for _ in range(4):  # 200 ms: not yet
        session.tick()
    assert session.world.get(FRONT, px, py - 5) == tiles.SKY
    session.tick()  # 250 ms: one fluid tick has run
    assert session.world.get(FRONT, px, py - 5) == tiles.WATER_FLOW_DOWN


def test_a_long_run_stays_healthy(game):
    session, recorder = game
    start(session)
    session.press(RIGHT)
    for i in range(200):
        if i == 60:
            session.release(RIGHT)
            session.press(LEFT)
        if i == 120:
            session.release(LEFT)
        session.tick()
    assert len(recorder.last) == FRAME_BYTES
    assert session.status_text()
