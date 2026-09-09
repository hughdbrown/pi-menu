"""What actually reaches the LEDs for the world and each screen."""

from __future__ import annotations

import random

import pytest

from pi_menu.display.protocol import FRAME_BYTES
from pi_menu.microcraft import palette, render, sky, tiles
from pi_menu.microcraft.canvas import Canvas
from pi_menu.microcraft.inventory import CRAFT, HOTBAR, OUTPUT, Inventory, Stack
from pi_menu.microcraft.player import Breaker, Drops, Player
from pi_menu.microcraft.terrain import BACK, FRONT, World
from pi_menu.microcraft.weather import Weather

SKY_ROW = 120  # open sky in every seed
STARS = sky.make_stars(random.Random(1))


@pytest.fixture
def scene():
    world = World(31)
    weather = Weather(world, random.Random(2), 0.0)
    weather.clouds, weather.mini_clouds = [], []
    return world, weather


def draw(world, weather, cam_x, cam_y, **extra) -> Canvas:
    canvas = Canvas()
    render.draw_world(
        canvas, world, weather, cam_x, cam_y,
        sky_frac=0.5, moon_phase=0.5, stars=STARS, now_ms=0, ref_y=cam_y + 4, **extra
    )
    return canvas


def tile_pixels(canvas: Canvas, bx: int, by: int) -> tuple:
    return tuple(canvas.get(bx * 2 + dx, by * 2 + dy) for dy in range(2) for dx in range(2))


# -- the world ---------------------------------------------------------------


def test_a_world_frame_is_a_full_frame_of_sky_where_nothing_is_built(scene):
    world, weather = scene
    canvas = draw(world, weather, 0, SKY_ROW)
    assert len(canvas.to_bytes()) == FRAME_BYTES
    assert canvas.get(0, 0)[2] > 200  # noon blue


def test_front_blocks_are_drawn_at_full_brightness_and_background_dimmed(scene):
    world, weather = scene
    world.set(FRONT, 2, SKY_ROW + 3, tiles.BRICK)
    world.set(BACK, 4, SKY_ROW + 3, tiles.BRICK)
    canvas = draw(world, weather, 0, SKY_ROW)
    front = tile_pixels(canvas, 2, 3)
    back = tile_pixels(canvas, 4, 3)
    sheet, sx, sy, _ = palette.tile_art(tiles.BRICK)
    assert front == tuple(sheet[sy + dy][sx + dx] for dy in range(2) for dx in range(2))
    assert all(sum(b) < sum(f) for b, f in zip(back, front))
    assert all(max(b) > 20 for b in back)  # dimmed, still lit


def test_the_front_hides_the_background_behind_it(scene):
    world, weather = scene
    world.set(BACK, 2, SKY_ROW + 3, tiles.LAVA)
    world.set(FRONT, 2, SKY_ROW + 3, tiles.STONE)
    canvas = draw(world, weather, 0, SKY_ROW)
    sheet, sx, sy, _ = palette.tile_art(tiles.STONE)
    assert tile_pixels(canvas, 2, 3) == tuple(sheet[sy + dy][sx + dx] for dy in range(2) for dx in range(2))


def test_left_flowing_water_is_the_mirror_of_right_flowing(scene):
    world, weather = scene
    world.set(FRONT, 1, SKY_ROW + 2, tiles.WATER_FLOW_R1)
    world.set(FRONT, 3, SKY_ROW + 2, tiles.WATER_FLOW_L1)
    canvas = draw(world, weather, 0, SKY_ROW)
    right = tile_pixels(canvas, 1, 2)
    left = tile_pixels(canvas, 3, 2)
    assert left == (right[1], right[0], right[3], right[2])


def test_a_burning_block_wears_the_fire_overlay(scene):
    world, weather = scene
    world.set(FRONT, 2, SKY_ROW + 3, tiles.WOOD_PLANKS)
    plain = tile_pixels(draw(world, weather, 0, SKY_ROW), 2, 3)
    world.burning[(FRONT, 2, SKY_ROW + 3)] = 10
    burning = tile_pixels(draw(world, weather, 0, SKY_ROW), 2, 3)
    assert burning != plain
    assert any(p[0] == 255 and p[2] < 100 for p in burning)  # orange flame pixels


def test_the_player_is_a_bright_two_by_two(scene):
    world, weather = scene
    player = Player(3, SKY_ROW + 3)
    canvas = draw(world, weather, 0, SKY_ROW, player=player)
    assert tile_pixels(canvas, 3, 3) == (render.PLAYER_COLOUR,) * 4


def test_the_hotbar_runs_along_the_bottom_with_the_selected_slot_blinking(scene):
    world, weather = scene
    bag = Inventory()
    player = Player(3, SKY_ROW + 3)
    canvas = draw(world, weather, 0, SKY_ROW, player=player, inventory=bag)
    assert tile_pixels(canvas, 1, 7) == (render.WHITE,) * 4  # slot 1, blink on at t=0
    sheet, sx, sy, _ = palette.tile_art(tiles.GRASS)
    assert tile_pixels(canvas, 0, 7) == tuple(sheet[sy + dy][sx + dx] for dy in range(2) for dx in range(2))
    assert tile_pixels(canvas, 7, 7) == (palette.UI_SHEET[0][0], palette.UI_SHEET[0][1],
                                          palette.UI_SHEET[1][0], palette.UI_SHEET[1][1])
    later = Canvas()
    render.draw_hotbar(later, bag, now_ms=render.BLINK_MS)
    assert tile_pixels(later, 1, 7) != (render.WHITE,) * 4


def test_the_demo_shows_no_player_and_no_hotbar(scene):
    world, weather = scene
    canvas = draw(world, weather, 0, SKY_ROW)
    assert canvas.get(2, 15)[2] > 150  # sky, not a hotbar tile


def test_the_crack_overlay_darkens_the_block_being_broken(scene):
    world, weather = scene
    world.set(FRONT, 2, SKY_ROW + 3, tiles.SAND)
    bag, breaker = Inventory(starter_kit=False), Breaker()
    player = Player(5, SKY_ROW + 3)
    breaker.key = (FRONT, 2, SKY_ROW + 3)
    breaker.progress = 1400  # of 1500: last frame of the crack
    canvas = draw(world, weather, 0, SKY_ROW, player=player, breaker=breaker, inventory=bag)
    sheet, sx, sy, _ = palette.tile_art(tiles.SAND)
    plain = tuple(sheet[sy + dy][sx + dx] for dy in range(2) for dx in range(2))
    cracked = tile_pixels(canvas, 2, 3)
    assert cracked != plain and sum(sum(p) for p in cracked) < sum(sum(p) for p in plain)


def test_a_dropped_item_is_one_pixel_in_its_average_colour(scene):
    world, weather = scene
    drops = Drops()
    drops.spawn(tiles.COAL, 1, 2, SKY_ROW + 3, now_ms=0)
    player = Player(5, SKY_ROW + 3)
    canvas = draw(world, weather, 0, SKY_ROW, player=player, drops=drops)
    assert canvas.get(4, 6) == palette.AVERAGE_COLOUR[tiles.COAL]


# -- the screens ------------------------------------------------------------


def test_the_inventory_screen_has_its_buttons_where_the_hit_test_says():
    canvas = Canvas()
    render.draw_inventory(canvas, Inventory(), now_ms=0)
    assert canvas.get(14, 0) == palette.UI_SHEET[0][tiles.UI_EXIT_X]
    assert canvas.get(12, 0) == palette.CRAFT_BUTTON[0][0]
    assert canvas.get(0, 0) == palette.UI_SHEET[0][0]  # an empty armour slot
    assert canvas.get(3, 2) == palette.UI_BG_COLOUR  # nothing held: plain dots
    sheet, sx, sy, _ = palette.tile_art(tiles.STICK)
    assert canvas.get(1, 4) == sheet[sy][sx + 1]  # backpack slot 0 holds sticks
    assert canvas.get(0, 12) == palette.UI_BG_COLOUR
    # The hotbar's active slot only blinks in the world; here white marks a
    # picked-up stack, and nothing is picked up yet.
    sheet, sx, sy, _ = palette.tile_art(tiles.DIRT)
    assert canvas.get(2, 14) == sheet[sy][sx]


def test_holding_a_stack_lights_one_quantity_dot_per_item():
    bag = Inventory(starter_kit=False)
    bag.hotbar[0] = Stack(tiles.DIRT, 5)
    bag.slot_click(HOTBAR, 0, 0)
    canvas = Canvas()
    render.draw_inventory(canvas, bag, now_ms=0)
    dots = [canvas.get(i % 8, 2 + i // 8) for i in range(16)]
    assert dots[:5] == [render.WHITE] * 5
    assert dots[5:] == [palette.UI_BG_COLOUR] * 11
    assert tile_pixels(canvas, 0, 7) == (render.WHITE,) * 4  # the held slot blinks


def test_the_bench_previews_the_recipe_and_its_count():
    bag = Inventory(starter_kit=False)
    bag.craft[0] = Stack(tiles.WOOD, 1)
    canvas = Canvas()
    render.draw_bench(canvas, bag, now_ms=0)
    sheet, sx, sy, _ = palette.tile_art(tiles.WOOD_PLANKS)
    assert canvas.get(8, 2) == sheet[sy][sx]  # the output slot shows planks
    assert canvas.get(14, 0) == palette.UI_SHEET[0][tiles.UI_EXIT_X]
    dots = [canvas.get(12 + i % 4, 2 + i // 4) for i in range(16)]
    assert dots[:4] == [render.WHITE] * 4 and dots[4] == palette.UI_BG_COLOUR
    log_sheet, lx, ly, _ = palette.tile_art(tiles.WOOD)
    assert canvas.get(1, 1) == log_sheet[ly][lx]  # grid slot 0 at (1, 1)
    assert canvas.get(0, 0) == palette.UI_BG_COLOUR


def test_the_table_grid_starts_at_the_top_and_its_output_sits_further_right():
    bag = Inventory(starter_kit=False)
    bag.table[8] = Stack(tiles.WOOD, 1)
    canvas = Canvas()
    render.draw_table(canvas, bag, now_ms=0)
    log_sheet, lx, ly, _ = palette.tile_art(tiles.WOOD)
    assert canvas.get(5, 4) == log_sheet[ly][lx]  # slot 8 at (5, 4)
    sheet, sx, sy, _ = palette.tile_art(tiles.WOOD_PLANKS)
    assert canvas.get(9, 2) == sheet[sy][sx]
    assert canvas.get(8, 2) == palette.UI_BG_COLOUR


def test_the_opening_screen_is_a_grey_panel_with_the_play_button():
    canvas = Canvas((1, 2, 3))
    render.draw_menu(canvas)
    assert canvas.get(0, 0) == (1, 2, 3)  # the demo shows through
    assert canvas.get(3, 4) == render.PANEL_COLOUR
    assert canvas.get(4, 5) == render.BTN_PIXELS[0][0]
    assert canvas.get(7, 5) == render.PANEL_COLOUR  # a transparent button pixel
    assert render.point_in_button(4, 5) and render.point_in_button(11, 7)
    assert not render.point_in_button(12, 7) and not render.point_in_button(4, 8)


def test_the_cursor_inverts_whatever_is_under_it():
    canvas = Canvas((10, 20, 30))
    render.draw_cursor(canvas, 8, 6)
    assert canvas.get(8, 6) == (245, 235, 225)
    assert canvas.get(7, 6) == (10, 20, 30)
