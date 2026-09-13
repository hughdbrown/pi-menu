"""The panel draws the HTML's own art, sheet for sheet."""

from __future__ import annotations

from pi_menu.microcraft import palette, sprites, tiles


def pattern(kind: int) -> tuple:
    sheet, sx, sy, _ = palette.tile_art(kind)
    return tuple(sheet[sy + dy][sx + dx] for dy in range(2) for dx in range(2))


def test_every_sheet_is_the_html_art_untouched():
    assert palette.BLOCK_SHEET is sprites.BLOCK_SHEET
    assert palette.ITEM_SHEET is sprites.ITEM_SHEET
    assert palette.FLUID_SHEET is sprites.FLUID_SHEET
    assert palette.UI_SHEET is sprites.UI_SHEET
    assert palette.FIRE_SHEET is sprites.FIRE_SHEET
    assert palette.BREAK_SHEET is sprites.BREAK_SHEET
    assert palette.FURNACE_PROGRESS_SHEET is sprites.FURNACE_PROGRESS_SHEET
    assert palette.FURNACE_OXYGEN_BUTTON is sprites.FURNACE_OXYGEN_BUTTON
    assert palette.SPIDER_SHEET is sprites.SPIDER_SHEET
    assert palette.CRAFT_BUTTON is sprites.CRAFT_BUTTON


def test_tile_art_addresses_every_block_and_item_inside_its_sheet():
    for kind in list(tiles.SHEET_POS) + list(tiles.ITEM_SHEET_POS) + list(tiles.FLUID_SHEET_POS):
        sheet, sx, sy, mirrored = palette.tile_art(kind)
        assert 0 <= sy + 1 < len(sheet) and 0 <= sx + 1 < len(sheet[0]), kind
        assert mirrored is (kind in tiles.MIRRORED_TILES)
    assert pattern(tiles.WATER_FLOW_L1) == pattern(tiles.WATER_FLOW_R1)  # same art, mirrored on draw


def test_lift_raises_the_floor_but_keeps_black_and_transparent():
    assert palette.lift(None) is None
    assert palette.lift((0, 0, 0)) == (0, 0, 0)
    assert palette.lift((1, 1, 1))[0] >= palette.FLOOR
    assert palette.lift((255, 255, 255)) == (255, 255, 255)
    r, g, b = palette.lift((200, 100, 0))
    assert r > g > b


def test_flat_colours_match_the_html_fill_styles():
    assert palette.FUEL_FILL == (0xFF, 0x6C, 0x00)
    assert palette.HEAT_FILL == (0xFF, 0x00, 0x00)
    assert palette.BAR_BACKGROUND == (0x13, 0x13, 0x13)
    assert palette.UI_SHEET[0][tiles.UI_EXIT_X][0] == 255


def test_average_colours_are_the_mean_of_the_html_tile():
    assert palette.AVERAGE_COLOUR[tiles.LAVA][0] > 200
    assert palette.AVERAGE_COLOUR[tiles.WATER][2] > 150
    for kind in tiles.SHEET_POS:
        assert len(palette.AVERAGE_COLOUR[kind]) == 3


def test_every_empty_slot_is_solid_black():
    assert palette.SLOT_COLOUR == (0, 0, 0)
    for dy in range(0, 16, 2):
        for dx in range(0, 16, 2):
            assert palette.slot_colour(dx, dy) == (0, 0, 0)
            assert palette.slot_tile(dx, dy) == (((0, 0, 0), (0, 0, 0)), ((0, 0, 0), (0, 0, 0)))
