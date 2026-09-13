"""The tile catalogue agrees with itself and with the art."""

from __future__ import annotations

import pytest

from pi_menu.microcraft import palette, sprites, tiles


def test_every_named_thing_has_art_and_every_drawn_thing_has_a_name():
    drawable = set(tiles.SHEET_POS) | set(tiles.ITEM_SHEET_POS)
    assert drawable == set(tiles.NAMES)


def test_blocks_and_items_never_share_an_id():
    assert not (set(tiles.SHEET_POS) & tiles.ITEMS)
    assert all(kind >= 100 for kind in tiles.ITEMS)
    assert all(kind < 100 for kind in tiles.SHEET_POS)


def test_the_sheets_are_the_sizes_the_html_declares():
    assert len(sprites.BLOCK_SHEET) == 16 and len(sprites.BLOCK_SHEET[0]) == 16
    assert len(sprites.ITEM_SHEET) == 16 and len(sprites.ITEM_SHEET[0]) == 16
    assert len(sprites.FLUID_SHEET) == 4 and len(sprites.FLUID_SHEET[0]) == 8
    assert len(sprites.FIRE_SHEET) == 2 and len(sprites.FIRE_SHEET[0]) == 8
    assert len(sprites.BREAK_SHEET) == 2 and len(sprites.BREAK_SHEET[0]) == 8
    assert len(sprites.UI_SHEET) == 16
    assert len(sprites.CRAFT_BUTTON) == 2 and len(sprites.CRAFT_BUTTON[0]) == 2


def test_grass_is_green_on_top_and_water_is_blue():
    assert palette.AVERAGE_COLOUR[tiles.GRASS][1] > palette.AVERAGE_COLOUR[tiles.GRASS][0]
    r, g, b = palette.AVERAGE_COLOUR[tiles.WATER]
    assert b > r and b > g


def test_items_have_transparent_corners_but_blocks_do_not():
    sheet, sx, sy, _ = palette.tile_art(tiles.STICK)
    assert sheet[sy][sx] in (None, (0, 0, 0))  # the stick's top-left pixel is empty
    sheet, sx, sy, _ = palette.tile_art(tiles.DIRT)
    assert all(sheet[sy + dy][sx + dx] is not None for dy in range(2) for dx in range(2))


def test_left_flowing_fluids_mirror_the_right_facing_art():
    assert palette.tile_art(tiles.WATER_FLOW_L2)[3] is True
    assert palette.tile_art(tiles.WATER_FLOW_R2)[3] is False
    assert palette.tile_art(tiles.WATER_FLOW_L2)[1:3] == palette.tile_art(tiles.WATER_FLOW_R2)[1:3]


def test_fluid_metadata_covers_every_fluid_and_nothing_else():
    assert tiles.FLUIDS == set(tiles.FLUID_META)
    assert tiles.SKY not in tiles.FLUIDS
    assert tiles.solid(tiles.STONE) and not tiles.solid(tiles.WATER_FLOW_R1)
    assert not tiles.solid(tiles.SKY)


@pytest.mark.parametrize(
    "fluid, level, direction, expected",
    [
        (tiles.LAVA_KIND, 0, None, tiles.LAVA_FLOW_DOWN),
        (tiles.LAVA_KIND, 0, tiles.LEFTWARD, tiles.LAVA_FLOW_DOWN),
        (tiles.WATER_KIND, 1, tiles.RIGHTWARD, tiles.WATER_FLOW_R1),
        (tiles.WATER_KIND, 3, tiles.LEFTWARD, tiles.WATER_FLOW_L3),
        (tiles.LAVA_KIND, 2, tiles.LEFTWARD, tiles.LAVA_FLOW_L2),
    ],
)
def test_flow_tiles_are_built_from_fluid_level_and_direction(fluid, level, direction, expected):
    assert tiles.flow_tile_for(fluid, level, direction) == expected


def test_the_flow_tile_table_round_trips_through_the_metadata():
    for kind, meta in tiles.FLUID_META.items():
        if meta.is_source:
            continue
        assert tiles.flow_tile_for(meta.fluid, meta.level, meta.direction) == kind


def test_lava_and_water_are_told_apart_in_every_state():
    assert tiles.is_lava(tiles.LAVA) and tiles.is_lava(tiles.LAVA_FLOW_L3)
    assert tiles.is_water(tiles.WATER_FLOW_DOWN) and not tiles.is_water(tiles.LAVA)
    assert not tiles.is_lava(tiles.STONE)


def test_tools_and_buckets_stack_to_one_and_blocks_to_sixteen():
    assert tiles.stack_max_for(tiles.IRON_AXE) == 1
    assert tiles.stack_max_for(tiles.BUCKET_WATER) == 1
    assert tiles.stack_max_for(tiles.DIRT) == 16
    assert tiles.stack_max_for(tiles.STICK) == 16


def test_the_right_tool_speeds_its_own_blocks_and_nothing_else():
    assert tiles.break_time_ms(tiles.STONE) == 4000
    assert tiles.break_time_ms(tiles.STONE, tiles.IRON_PICKAXE) == pytest.approx(880)
    assert tiles.break_time_ms(tiles.WOOD, tiles.STONE_AXE) == 1250
    assert tiles.break_time_ms(tiles.WOOD, tiles.IRON_PICKAXE) == 2500
    assert tiles.break_time_ms(tiles.DIRT, tiles.IRON_AXE) == 1500
    assert tiles.break_time_ms(9999) == tiles.DEFAULT_BREAK_MS


def test_the_ui_background_colour_is_the_sheet_s_grey():
    assert palette.UI_BG_COLOUR == sprites.UI_SHEET[0][tiles.UI_BG_X]
    assert palette.UI_BG_COLOUR == (156, 156, 156)
