"""Every tile lights up on the LEDs, and no two neighbours look alike."""

from __future__ import annotations

import itertools

import pytest

from pi_menu.microcraft import palette, sprites, tiles


def pattern(kind: int) -> tuple:
    sheet, sx, sy, _ = palette.tile_art(kind)
    return tuple(sheet[sy + dy][sx + dx] for dy in range(2) for dx in range(2))


def distance(a: tuple, b: tuple) -> int:
    """Summed channel difference over the four pixels; None counts as black."""
    total = 0
    for pa, pb in zip(a, b):
        pa = pa or (0, 0, 0)
        pb = pb or (0, 0, 0)
        total += sum(abs(x - y) for x, y in zip(pa, pb))
    return total


BLOCKS = sorted(tiles.SHEET_POS)
ITEMS = sorted(tiles.ITEM_SHEET_POS)


def test_every_block_is_bright_enough_to_read_on_the_panel():
    for kind in BLOCKS:
        lit = [p for p in pattern(kind) if p is not None]
        brightest = max(max(p) for p in lit)
        assert brightest >= 120, tiles.NAMES[kind]
        # At most two of the four pixels may sit near the floor (coal flecks).
        dark = sum(1 for p in lit if max(p) < palette.FLOOR)
        assert dark <= 2, tiles.NAMES[kind]


def test_every_item_has_a_lit_pixel_and_tools_keep_their_outline():
    for kind in ITEMS:
        pixels = pattern(kind)
        assert any(p is not None and max(p) >= 120 for p in pixels), tiles.NAMES[kind]
    # Tools and sticks are shapes on an empty-slot tile; ingots fill it.
    for kind in tiles.TOOL_TYPES | {tiles.STICK}:
        assert any(p is None for p in pattern(kind)), tiles.NAMES[kind]
    assert all(p is not None for p in pattern(tiles.IRON))


def test_no_two_blocks_share_a_look():
    for a, b in itertools.combinations(BLOCKS, 2):
        assert distance(pattern(a), pattern(b)) >= 150, (tiles.NAMES[a], tiles.NAMES[b])


def test_the_stone_family_is_told_apart_by_more_than_a_shade():
    family = (tiles.STONE, tiles.COBBLESTONE, tiles.COAL_ORE, tiles.IRON_ORE,
              tiles.COPPER_ORE, tiles.FURNACE, tiles.CLAY)
    for a, b in itertools.combinations(family, 2):
        assert distance(pattern(a), pattern(b)) >= 200, (tiles.NAMES[a], tiles.NAMES[b])


def test_grass_and_leaves_and_the_wood_family_stay_distinct():
    assert distance(pattern(tiles.GRASS), pattern(tiles.LEAF)) >= 200
    for a, b in itertools.combinations(
        (tiles.DIRT, tiles.WOOD, tiles.WOOD_PLANKS, tiles.CRAFTING_TABLE, tiles.BRICK, tiles.SAND), 2
    ):
        assert distance(pattern(a), pattern(b)) >= 200, (tiles.NAMES[a], tiles.NAMES[b])


def test_the_flow_tiles_thin_out_as_they_taper_and_mirror_for_the_left():
    for down, one, two, three in (
        (tiles.WATER_FLOW_DOWN, tiles.WATER_FLOW_R1, tiles.WATER_FLOW_R2, tiles.WATER_FLOW_R3),
        (tiles.LAVA_FLOW_DOWN, tiles.LAVA_FLOW_R1, tiles.LAVA_FLOW_R2, tiles.LAVA_FLOW_R3),
    ):
        lit = [sum(1 for p in pattern(k) if p is not None) for k in (down, one, two, three)]
        assert lit[0] == 4 and lit[0] > lit[1] > lit[2] > lit[3] >= 1
    assert palette.tile_art(tiles.WATER_FLOW_L1)[3] is True
    assert pattern(tiles.WATER_FLOW_L1) == pattern(tiles.WATER_FLOW_R1)  # same art, mirrored on draw


def test_lift_raises_the_floor_but_keeps_black_and_transparent():
    assert palette.lift(None) is None
    assert palette.lift((0, 0, 0)) == (0, 0, 0)
    assert palette.lift((1, 1, 1))[0] >= palette.FLOOR
    assert palette.lift((255, 255, 255)) == (255, 255, 255)
    r, g, b = palette.lift((200, 100, 0))
    assert r > g > b


def test_ui_and_fire_are_lifted_but_the_crack_stays_dark():
    # The new HTML's UI sheet uses black as transparency for the empty slot;
    # the red exit button tile is the first non-transparent pixel.
    assert palette.UI_SHEET[0][tiles.UI_EXIT_X][0] == 255
    assert palette.FIRE_SHEET[1][0] != sprites.FIRE_SHEET[1][0]
    assert palette.BREAK_SHEET is sprites.BREAK_SHEET


def test_average_colours_follow_the_panel_palette():
    assert palette.AVERAGE_COLOUR[tiles.LAVA][0] == 255
    assert palette.AVERAGE_COLOUR[tiles.WATER][2] == 255
    assert max(palette.AVERAGE_COLOUR[tiles.STONE]) >= 100


def test_every_empty_slot_is_solid_black():
    assert palette.SLOT_COLOUR == (0, 0, 0)
    for dy in range(0, 16, 2):
        for dx in range(0, 16, 2):
            assert palette.slot_colour(dx, dy) == (0, 0, 0)
            assert palette.slot_tile(dx, dy) == (((0, 0, 0), (0, 0, 0)), ((0, 0, 0), (0, 0, 0)))
