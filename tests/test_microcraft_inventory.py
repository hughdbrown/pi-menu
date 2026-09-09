"""Stacks move, merge and split the way the HTML's screens do; recipes match."""

from __future__ import annotations

import pytest

from pi_menu.microcraft import tiles
from pi_menu.microcraft.inventory import (
    BACKPACK,
    CRAFT,
    HOTBAR,
    OUTPUT,
    TABLE,
    TABLE_OUTPUT,
    Inventory,
    Recipe,
    Stack,
)
from pi_menu.microcraft.tiles import (
    COBBLESTONE, CRAFTING_TABLE, DIRT, IRON_AXE, STICK, STONE, STONE_AXE,
    STONE_PICKAXE, STONE_SWORD, WOOD, WOOD_PLANKS,
)


@pytest.fixture
def bag():
    return Inventory(starter_kit=False)


# -- the starter kit ------------------------------------------------------


def test_the_starter_kit_matches_the_html():
    inv = Inventory()
    assert inv.hotbar[0] == Stack(tiles.GRASS, 5)
    assert inv.hotbar[1] == Stack(DIRT, 16)
    assert inv.hotbar[7] is None
    assert inv.backpack[0] == Stack(STICK, 6)
    assert inv.backpack[16] == Stack(tiles.SAND, 16)
    assert inv.backpack[17] is None
    assert inv.selected == 1 and inv.held == Stack(DIRT, 16)
    assert inv.held_text() == "dirt x16"


# -- the hotbar -----------------------------------------------------------


def test_only_a_full_slot_can_be_selected(bag):
    bag.hotbar[3] = Stack(STONE, 2)
    bag.select_slot(3)
    assert bag.selected == 3
    bag.select_slot(5)
    assert bag.selected == 3
    bag.select_slot(99)
    assert bag.selected == 3


def test_dropping_one_empties_the_slot_at_zero(bag):
    bag.hotbar[1] = Stack(STONE, 2)
    assert bag.drop_one_held() == STONE
    assert bag.held == Stack(STONE, 1)
    assert bag.drop_one_held() == STONE
    assert bag.held is None
    assert bag.drop_one_held() is None


# -- picking things up ------------------------------------------------------


def test_pickup_tops_up_a_partial_stack_before_opening_a_new_slot(bag):
    bag.hotbar[0] = Stack(DIRT, 15)
    assert bag.pickup(DIRT)
    assert bag.hotbar[0] == Stack(DIRT, 16)
    assert bag.pickup(DIRT)
    assert bag.hotbar[1] == Stack(DIRT, 1)


def test_pickup_prefers_the_hotbar_and_then_the_backpack(bag):
    for i in range(8):
        bag.hotbar[i] = Stack(STONE, 16)
    assert bag.pickup(DIRT)
    assert bag.backpack[0] == Stack(DIRT, 1)


def test_tools_never_stack(bag):
    assert bag.pickup(IRON_AXE) and bag.pickup(IRON_AXE)
    assert bag.hotbar[0] == Stack(IRON_AXE, 1) and bag.hotbar[1] == Stack(IRON_AXE, 1)


def test_a_full_inventory_refuses_and_reports_what_did_not_fit(bag):
    for i in range(8):
        bag.hotbar[i] = Stack(STONE, 16)
    for i in range(32):
        bag.backpack[i] = Stack(STONE, 16)
    assert not bag.pickup(DIRT)
    bag.backpack[31] = Stack(STONE, 14)
    assert bag.add_items(STONE, 5) == 2
    assert bag.take_back(Stack(DIRT, 3)) == Stack(DIRT, 3)
    bag.backpack[31] = None
    assert bag.take_back(Stack(DIRT, 20)) == Stack(DIRT, 4)


# -- slot clicks ------------------------------------------------------------


def test_a_press_selects_and_a_press_on_the_same_slot_puts_down(bag):
    bag.hotbar[0] = Stack(STONE, 3)
    bag.slot_click(HOTBAR, 0, 0)
    assert bag.selection == (HOTBAR, 0)
    bag.slot_click(HOTBAR, 0, 1000)
    assert bag.selection is None


def test_pressing_an_empty_slot_with_nothing_held_does_nothing(bag):
    bag.slot_click(BACKPACK, 4, 0)
    assert bag.selection is None


def test_a_held_stack_moves_into_an_empty_slot_and_swaps_with_a_stranger(bag):
    bag.hotbar[0] = Stack(STONE, 3)
    bag.backpack[2] = Stack(DIRT, 7)
    bag.slot_click(HOTBAR, 0, 0)
    bag.slot_click(BACKPACK, 5, 100)
    assert bag.hotbar[0] is None and bag.backpack[5] == Stack(STONE, 3)
    assert bag.selection is None
    bag.slot_click(BACKPACK, 5, 200)
    bag.slot_click(BACKPACK, 2, 300)
    assert bag.backpack[2] == Stack(STONE, 3) and bag.backpack[5] == Stack(DIRT, 7)


def test_like_stacks_merge_and_the_overflow_stays_behind(bag):
    bag.hotbar[0] = Stack(STONE, 10)
    bag.hotbar[1] = Stack(STONE, 9)
    bag.slot_click(HOTBAR, 0, 0)
    bag.slot_click(HOTBAR, 1, 100)
    assert bag.hotbar[1] == Stack(STONE, 16)
    assert bag.hotbar[0] == Stack(STONE, 3)


def test_two_quick_presses_arm_a_split_and_the_next_press_halves(bag):
    bag.hotbar[0] = Stack(STONE, 9)
    bag.slot_click(HOTBAR, 0, 0)
    bag.slot_click(HOTBAR, 0, 100)  # a quick second press arms the split
    assert bag.split_armed and bag.selection == (HOTBAR, 0)
    bag.slot_click(BACKPACK, 0, 200)
    assert bag.backpack[0] == Stack(STONE, 4) and bag.hotbar[0] == Stack(STONE, 5)
    assert bag.selection is None and not bag.split_armed


def test_a_slow_second_press_puts_the_stack_down_instead(bag):
    bag.hotbar[0] = Stack(STONE, 9)
    bag.slot_click(HOTBAR, 0, 0)
    bag.slot_click(HOTBAR, 0, 1000)
    assert not bag.split_armed and bag.selection is None


def test_a_split_onto_a_like_stack_respects_the_stack_size(bag):
    bag.hotbar[0] = Stack(STONE, 10)
    bag.hotbar[1] = Stack(STONE, 14)
    bag.split_stack((HOTBAR, 0), (HOTBAR, 1))
    assert bag.hotbar[1] == Stack(STONE, 16)
    assert bag.hotbar[0] == Stack(STONE, 8)


def test_a_split_onto_a_different_kind_or_of_one_item_is_refused(bag):
    bag.hotbar[0] = Stack(STONE, 10)
    bag.hotbar[1] = Stack(DIRT, 1)
    bag.split_stack((HOTBAR, 0), (HOTBAR, 1))
    assert bag.hotbar[0] == Stack(STONE, 10) and bag.hotbar[1] == Stack(DIRT, 1)
    bag.hotbar[2] = Stack(STONE, 1)
    bag.split_stack((HOTBAR, 2), (HOTBAR, 3))
    assert bag.hotbar[2] == Stack(STONE, 1) and bag.hotbar[3] is None


# -- recipes ------------------------------------------------------------------


def test_a_log_anywhere_on_the_bench_makes_four_planks(bag):
    bag.craft[2] = Stack(WOOD, 3)
    assert bag.bench_recipe() == Recipe(WOOD_PLANKS, 4, (0, 0, 1, 0))


def test_two_planks_stacked_on_the_left_make_sticks_and_four_make_a_table(bag):
    bag.craft[0] = Stack(WOOD_PLANKS, 1)
    bag.craft[2] = Stack(WOOD_PLANKS, 1)
    assert bag.bench_recipe() == Recipe(STICK, 4, (1, 0, 1, 0))
    bag.craft[1] = Stack(WOOD_PLANKS, 1)
    assert bag.bench_recipe() is None
    bag.craft[3] = Stack(WOOD_PLANKS, 1)
    assert bag.bench_recipe() == Recipe(CRAFTING_TABLE, 1, (1, 1, 1, 1))


def test_an_empty_or_unmatched_bench_makes_nothing(bag):
    assert bag.bench_recipe() is None
    bag.craft[0] = Stack(STONE, 1)
    assert bag.bench_recipe() is None


def test_picking_from_the_output_crafts_once_and_consumes_then(bag):
    bag.craft[1] = Stack(WOOD, 2)
    bag.bench_output_click(0)
    assert bag.craft_output[0] == Stack(WOOD_PLANKS, 4)
    assert bag.craft[1] == Stack(WOOD, 1)
    assert bag.selection == (OUTPUT, 0)
    # Pressing again while holding it just re-selects; nothing more is made.
    bag.bench_output_click(100)
    assert bag.craft[1] == Stack(WOOD, 1)
    bag.slot_click(HOTBAR, 0, 200)
    assert bag.hotbar[0] == Stack(WOOD_PLANKS, 4) and bag.craft_output[0] is None


def test_the_output_cannot_be_taken_with_a_full_hand(bag):
    bag.hotbar[0] = Stack(STONE, 1)
    bag.craft[0] = Stack(WOOD, 1)
    bag.slot_click(HOTBAR, 0, 0)
    bag.bench_output_click(10)
    assert bag.craft_output[0] is None and bag.craft[0] == Stack(WOOD, 1)


def test_closing_the_bench_returns_ingredients_and_hands_back_what_wont_fit(bag):
    bag.craft[0] = Stack(WOOD, 2)
    bag.craft_output[0] = Stack(WOOD_PLANKS, 4)
    assert bag.close_bench() == []
    assert bag.hotbar[0] == Stack(WOOD, 2) and bag.hotbar[1] == Stack(WOOD_PLANKS, 4)
    assert all(s is None for s in bag.craft) and bag.craft_output[0] is None

    for i in range(8):
        bag.hotbar[i] = Stack(STONE, 16)
    for i in range(32):
        bag.backpack[i] = Stack(STONE, 16)
    bag.craft[3] = Stack(DIRT, 5)
    assert bag.close_bench() == [Stack(DIRT, 5)]


@pytest.mark.parametrize(
    "layout, kind",
    [
        ("CCC.S..S.", STONE_PICKAXE),
        (".C..C..S.", STONE_SWORD),
        ("CC.CS..S.", STONE_AXE),
        (".CC.SC.S.", STONE_AXE),
    ],
)
def test_the_stone_tools_need_the_full_table(bag, layout, kind):
    for i, cell in enumerate(layout):
        bag.table[i] = {"C": Stack(COBBLESTONE, 1), "S": Stack(STICK, 1)}.get(cell)
    recipe = bag.table_recipe()
    assert recipe.kind == kind and recipe.count == 1
    assert recipe.consume == tuple(0 if c == "." else 1 for c in layout)
    bag.table_output_click(0)
    assert bag.table_output[0] == Stack(kind, 1)
    assert all(s is None for s in bag.table)


def test_a_stone_tool_pattern_is_not_shiftable(bag):
    for i, cell in enumerate("...CCC.S."):  # pickaxe, one row down
        bag.table[i] = {"C": Stack(COBBLESTONE, 1), "S": Stack(STICK, 1)}.get(cell)
    assert bag.table_recipe() is None


def test_bench_recipes_work_anywhere_on_the_table_if_the_rest_is_empty(bag):
    bag.table[4] = Stack(WOOD_PLANKS, 1)
    bag.table[7] = Stack(WOOD_PLANKS, 1)
    recipe = bag.table_recipe()
    assert recipe.kind == STICK and recipe.consume == (0, 0, 0, 0, 1, 0, 0, 1, 0)
    bag.table[0] = Stack(STONE, 1)
    assert bag.table_recipe() is None
    bag.table[0] = None
    bag.table[8] = Stack(WOOD, 1)  # a log beats the shifted shapes
    assert bag.table_recipe().kind == WOOD_PLANKS


def test_closing_the_table_clears_it(bag):
    bag.table[4] = Stack(STICK, 2)
    bag.table_output[0] = Stack(STONE_SWORD, 1)
    assert bag.close_table() == []
    assert all(s is None for s in bag.table) and bag.table_output[0] is None
    assert bag.hotbar[0] == Stack(STICK, 2) and bag.hotbar[1] == Stack(STONE_SWORD, 1)


# -- screen layouts -------------------------------------------------------------


def test_the_inventory_screen_regions_tile_the_panel():
    hit = Inventory.hit_inventory
    assert hit(15, 0) == ("exit", -1) and hit(14, 1) == ("exit", -1)
    assert hit(12, 0) == ("openCraft", -1)
    assert hit(0, 0) == ("armor", 0) and hit(7, 1) == ("armor", 3)
    assert hit(3, 2) == ("qty", -1) and hit(9, 3) == ("bg", -1)
    assert hit(0, 4) == (BACKPACK, 0) and hit(15, 11) == (BACKPACK, 31)
    assert hit(5, 12) == ("bg", -1)
    assert hit(0, 14) == (HOTBAR, 0) and hit(15, 15) == (HOTBAR, 7)


def test_the_bench_screen_regions():
    hit = Inventory.hit_bench
    assert hit(14, 0) == ("exit", -1)
    assert hit(1, 1) == (CRAFT, 0) and hit(4, 4) == (CRAFT, 3) and hit(3, 2) == (CRAFT, 1)
    assert hit(8, 2) == (OUTPUT, 0) and hit(9, 3) == (OUTPUT, 0)
    assert hit(12, 2) == ("qty", -1) and hit(15, 5) == ("qty", -1)
    assert hit(0, 6) == (BACKPACK, 0) and hit(15, 13) == (BACKPACK, 31)
    assert hit(0, 14) == (HOTBAR, 0)
    assert hit(0, 0) == ("bg", -1) and hit(6, 3) == ("bg", -1)


def test_the_table_screen_regions():
    hit = Inventory.hit_table
    assert hit(15, 1) == ("exit", -1)
    assert hit(1, 0) == (TABLE, 0) and hit(6, 5) == (TABLE, 8) and hit(3, 3) == (TABLE, 4)
    assert hit(9, 2) == (TABLE_OUTPUT, 0) and hit(10, 3) == (TABLE_OUTPUT, 0)
    assert hit(13, 4) == ("qty", -1)
    assert hit(2, 7) == (BACKPACK, 1)
    assert hit(14, 15) == (HOTBAR, 7)
    assert hit(0, 0) == ("bg", -1) and hit(8, 2) == ("bg", -1)
