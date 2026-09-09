"""Walking, jumping, swimming, digging, building and picking things up."""

from __future__ import annotations

import pytest

from pi_menu.microcraft import player as phys
from pi_menu.microcraft import tiles
from pi_menu.microcraft.inventory import Inventory, Stack
from pi_menu.microcraft.noise import WORLD_RADIUS
from pi_menu.microcraft.player import (
    JUMP_KEY,
    LEFT,
    RIGHT,
    Breaker,
    Drops,
    Player,
    camera,
    place_at,
)
from pi_menu.microcraft.sim import StickLighter
from pi_menu.microcraft.terrain import BACK, FRONT, WORLD_H, World

FLOOR = 130  # a stone row built high in the open sky
STAND = FLOOR - 1  # where a one-block player rests on it


def dry(x: int, y: int) -> bool:
    return False


def wet(x: int, y: int) -> bool:
    return True


@pytest.fixture
def world():
    w = World(21)
    for x in range(-30, 31):
        w.set(FRONT, x, FLOOR, tiles.STONE)
    return w


def settle(player: Player, world: World, held=frozenset(), swim=dry, steps: int = 120) -> None:
    for _ in range(steps):
        player.step(world, held, swim)


# -- moving --------------------------------------------------------------------


def test_the_player_falls_and_stops_flush_on_the_ground(world):
    p = Player(0, FLOOR - 8)
    speeds = []
    for _ in range(120):
        p.step(world, frozenset(), dry)
        speeds.append(p.vy)
    assert p.y == STAND and p.vy == 0
    assert max(speeds) <= phys.MAX_FALL + 1e-9


def test_walking_moves_and_letting_go_coasts_to_a_stop(world):
    p = Player(0, STAND)
    settle(p, world, frozenset({RIGHT}), steps=10)
    assert p.x == pytest.approx(0.8)
    settle(p, world, steps=20)
    assert 0.8 < p.x < 1.0
    settle(p, world, frozenset({LEFT}), steps=5)
    assert p.x < 0.8


def test_a_wall_stops_the_walk_but_not_the_fall(world):
    world.set(FRONT, 5, STAND, tiles.STONE)
    world.set(FRONT, 5, STAND - 1, tiles.STONE)
    p = Player(0, STAND)
    settle(p, world, frozenset({RIGHT}), steps=120)
    assert p.x == 4.0
    # Open a pit under the player: pinned against the wall, they still drop.
    world.set(FRONT, 4, FLOOR, tiles.SKY)
    world.set(FRONT, 4, FLOOR + 5, tiles.STONE)
    for y in range(STAND, FLOOR + 5):
        world.set(FRONT, 5, y, tiles.STONE)
    settle(p, world, frozenset({RIGHT}), steps=120)
    assert p.x == 4.0 and p.y == FLOOR + 4


def test_a_jump_rises_two_and_a_half_blocks_and_lands_again(world):
    p = Player(0, STAND)
    p.step(world, frozenset({JUMP_KEY}), dry)
    assert p.vy == pytest.approx(-phys.JUMP + phys.GRAV)
    lowest = STAND
    for _ in range(120):
        p.step(world, frozenset(), dry)
        lowest = min(lowest, p.y)
    assert STAND - 3 < lowest < STAND - 2
    assert p.y == STAND


def test_you_cannot_jump_in_mid_air(world):
    p = Player(0, STAND - 5)
    p.step(world, frozenset({JUMP_KEY}), dry)
    assert p.vy > 0


def test_a_ceiling_stops_a_jump_flush_beneath_it(world):
    world.set(FRONT, 0, STAND - 2, tiles.STONE)
    p = Player(0, STAND)
    p.step(world, frozenset({JUMP_KEY}), dry)
    for _ in range(10):
        p.step(world, frozenset(), dry)
    assert p.y >= STAND - 1


def test_water_is_buoyant_and_a_stroke_swims_up(world):
    p = Player(0, FLOOR - 10)
    for _ in range(60):
        p.step(world, frozenset(), wet)
        assert p.vy <= phys.MAX_FALL_IN_FLUID + 1e-9
    y_before = p.y
    for _ in range(30):
        p.step(world, frozenset({JUMP_KEY}), wet)
        assert p.vy >= -phys.MAX_SWIM_UP - 1e-9
    assert p.y < y_before


def test_the_core_lets_you_out_at_the_antipode(world):
    p = Player(10, WORLD_H - 1.5)
    p.step(world, frozenset(), dry)
    assert p.x == pytest.approx(10 - WORLD_RADIUS) or p.x == pytest.approx(10 + WORLD_RADIUS)
    assert p.y == world.gen.front_height(round(p.x)) - 1


def test_the_world_wraps_under_your_feet(world):
    p = Player(WORLD_RADIUS - 0.05, STAND)
    world.set(FRONT, WORLD_RADIUS, FLOOR, tiles.STONE)
    p.step(world, frozenset({RIGHT}), dry)
    assert -WORLD_RADIUS <= p.x < -WORLD_RADIUS + 1


def test_after_a_second_still_the_player_snaps_to_the_pixel_grid(world):
    p = Player(0.3, STAND)
    for _ in range(59):
        p.step(world, frozenset(), dry)
    assert p.x == pytest.approx(0.3)  # the wrap adds float dust, as in JS
    for _ in range(3):
        p.step(world, frozenset(), dry)
    assert p.x == 0.5


def test_the_camera_centres_the_player_and_clamps_to_the_world():
    assert camera(8, 8) == (4, 4)
    assert camera(8.4, 2) == (4, 0)
    assert camera(0, WORLD_H) == (-4, WORLD_H - 8)
    assert camera(0.5, 0.5) == (-3, 0)  # halves round up, as in JS


# -- drops ---------------------------------------------------------------------


def test_a_drop_falls_lands_and_is_picked_up_after_the_grace_period(world):
    drops, bag, p = Drops(), Inventory(starter_kit=False), Player(0, STAND)
    drops.spawn(tiles.COAL, 3, 0, STAND - 4, now_ms=0)
    for _ in range(30):
        drops.update(world, p, bag, now_ms=100)
    drop = drops.items[0]
    assert drop.landed and drop.y == STAND
    assert bag.hotbar[0] is None  # too soon
    drops.update(world, p, bag, now_ms=400)
    assert not drops.items and bag.hotbar[0] == Stack(tiles.COAL, 3)


def test_a_drop_with_no_room_stays_on_the_ground(world):
    drops, bag, p = Drops(), Inventory(starter_kit=False), Player(0, STAND)
    for i in range(8):
        bag.hotbar[i] = Stack(tiles.STONE, 16)
    for i in range(32):
        bag.backpack[i] = Stack(tiles.STONE, 16)
    bag.backpack[31] = Stack(tiles.COAL, 15)
    drops.spawn(tiles.COAL, 3, 0, STAND, now_ms=0)
    for _ in range(5):
        drops.update(world, p, bag, now_ms=1000)
    assert drops.items[0].count == 2 and bag.backpack[31] == Stack(tiles.COAL, 16)


def test_a_drop_elsewhere_is_left_alone(world):
    drops, bag, p = Drops(), Inventory(starter_kit=False), Player(0, STAND)
    drops.spawn(tiles.COAL, 1, 3, STAND, now_ms=0)
    for _ in range(5):
        drops.update(world, p, bag, now_ms=1000)
    assert drops.items and bag.hotbar[0] is None


# -- breaking --------------------------------------------------------------------


def test_holding_break_on_dirt_takes_its_time_then_takes_the_block(world):
    world.set(FRONT, 2, STAND, tiles.DIRT)
    bag, drops, b = Inventory(starter_kit=False), Drops(), Breaker()
    for _ in range(29):
        b.update(50, True, (2, STAND), FRONT, world, bag, drops, 0)
    assert world.get(FRONT, 2, STAND) == tiles.DIRT
    assert 0.9 < b.fraction(world, bag) < 1.0
    b.update(50, True, (2, STAND), FRONT, world, bag, drops, 0)
    assert world.get(FRONT, 2, STAND) == tiles.SKY
    assert bag.hotbar[0] == Stack(tiles.DIRT, 1)
    assert b.key is None


def test_the_right_tool_is_quicker(world):
    world.set(FRONT, 2, STAND, tiles.STONE)
    bag, drops, b = Inventory(starter_kit=False), Drops(), Breaker()
    bag.hotbar[1] = Stack(tiles.IRON_PICKAXE, 1)
    for _ in range(18):  # 900 ms > 880 ms
        b.update(50, True, (2, STAND), FRONT, world, bag, drops, 0)
    assert world.get(FRONT, 2, STAND) == tiles.SKY


def test_letting_go_or_moving_the_cursor_starts_again(world):
    world.set(FRONT, 2, STAND, tiles.DIRT)
    world.set(FRONT, 3, STAND, tiles.DIRT)
    bag, drops, b = Inventory(starter_kit=False), Drops(), Breaker()
    for _ in range(20):
        b.update(50, True, (2, STAND), FRONT, world, bag, drops, 0)
    b.update(50, False, (2, STAND), FRONT, world, bag, drops, 0)
    assert b.progress == 0
    for _ in range(20):
        b.update(50, True, (2, STAND), FRONT, world, bag, drops, 0)
    b.update(50, True, (3, STAND), FRONT, world, bag, drops, 0)
    assert b.key == (FRONT, 3, STAND) and b.progress == 50


def test_air_and_water_cannot_be_broken(world):
    world.set(FRONT, 2, STAND, tiles.WATER)
    bag, drops, b = Inventory(starter_kit=False), Drops(), Breaker()
    for _ in range(200):
        b.update(50, True, (2, STAND), FRONT, world, bag, drops, 0)
        b.update(50, True, (3, STAND), FRONT, world, bag, drops, 0)
    assert world.get(FRONT, 2, STAND) == tiles.WATER and b.key is None


def test_a_broken_block_with_nowhere_to_go_drops_on_the_ground(world):
    world.set(FRONT, 2, STAND, tiles.LEAF)
    bag, drops, b = Inventory(starter_kit=False), Drops(), Breaker()
    for i in range(8):
        bag.hotbar[i] = Stack(tiles.STONE, 16)
    for i in range(32):
        bag.backpack[i] = Stack(tiles.STONE, 16)
    for _ in range(20):
        b.update(50, True, (2, STAND), FRONT, world, bag, drops, 0)
    assert world.get(FRONT, 2, STAND) == tiles.SKY
    assert drops.items and drops.items[0].kind == tiles.LEAF


def test_breaking_targets_the_layer_it_is_told(world):
    world.set(BACK, 2, STAND, tiles.DIRT)
    bag, drops, b = Inventory(starter_kit=False), Drops(), Breaker()
    for _ in range(30):
        b.update(50, True, (2, STAND), BACK, world, bag, drops, 0)
    assert world.get(BACK, 2, STAND) == tiles.SKY


# -- placing -------------------------------------------------------------------


@pytest.fixture
def builder(world):
    bag = Inventory(starter_kit=False)
    bag.hotbar[1] = Stack(tiles.BRICK, 2)
    return world, bag, Player(0, STAND), StickLighter()


def test_placing_puts_the_held_block_down_and_counts_it_off(builder):
    world, bag, p, lighter = builder
    place_at(world, FRONT, 3, STAND, p, bag, lighter, 0)
    assert world.get(FRONT, 3, STAND) == tiles.BRICK
    assert bag.held == Stack(tiles.BRICK, 1)
    place_at(world, FRONT, 4, STAND, p, bag, lighter, 0)
    assert bag.held is None
    place_at(world, FRONT, 5, STAND, p, bag, lighter, 0)
    assert world.get(FRONT, 5, STAND) == tiles.SKY


def test_you_cannot_build_inside_yourself_or_inside_a_wall(builder):
    world, bag, p, lighter = builder
    place_at(world, FRONT, 0, STAND, p, bag, lighter, 0)
    place_at(world, FRONT, 0, FLOOR, p, bag, lighter, 0)
    assert world.get(FRONT, 0, STAND) == tiles.SKY
    assert world.get(FRONT, 0, FLOOR) == tiles.STONE
    assert bag.held == Stack(tiles.BRICK, 2)


def test_a_block_can_replace_water(builder):
    world, bag, p, lighter = builder
    world.set(FRONT, 3, STAND, tiles.WATER_FLOW_R2)
    place_at(world, FRONT, 3, STAND, p, bag, lighter, 0)
    assert world.get(FRONT, 3, STAND) == tiles.BRICK


def test_items_are_never_placed(builder):
    world, bag, p, lighter = builder
    bag.hotbar[1] = Stack(tiles.STICK, 4)
    place_at(world, FRONT, 3, STAND, p, bag, lighter, 0)
    assert world.get(FRONT, 3, STAND) == tiles.SKY and bag.held.count == 4


def test_a_bucket_scoops_and_pours(builder):
    world, bag, p, lighter = builder
    bag.hotbar[1] = Stack(tiles.BUCKET_EMPTY, 1)
    world.set(FRONT, 3, STAND, tiles.WATER_FLOW_DOWN)
    place_at(world, FRONT, 3, STAND, p, bag, lighter, 0)
    assert world.get(FRONT, 3, STAND) == tiles.SKY and bag.held.kind == tiles.BUCKET_WATER
    place_at(world, FRONT, 4, STAND, p, bag, lighter, 0)
    assert world.get(FRONT, 4, STAND) == tiles.WATER and bag.held.kind == tiles.BUCKET_EMPTY
    world.set(FRONT, 5, STAND, tiles.LAVA)
    place_at(world, FRONT, 5, STAND, p, bag, lighter, 0)
    assert bag.held.kind == tiles.BUCKET_LAVA
    place_at(world, FRONT, 6, STAND, p, bag, lighter, 0)
    assert world.get(FRONT, 6, STAND) == tiles.LAVA
    assert bag.held == Stack(tiles.BUCKET_EMPTY, 1)


def test_a_stick_tapped_on_a_plank_lights_it(builder):
    world, bag, p, lighter = builder
    bag.hotbar[1] = Stack(tiles.STICK, 1)
    world.set(FRONT, 3, STAND, tiles.WOOD_PLANKS)
    for tap in range(5):
        place_at(world, FRONT, 3, STAND, p, bag, lighter, tap * 100)
    assert (FRONT, 3, STAND) in world.burning
    assert bag.held == Stack(tiles.STICK, 1)  # the stick is not used up


def test_building_on_the_background_leaves_the_front_alone(builder):
    world, bag, p, lighter = builder
    place_at(world, BACK, 0, STAND - 3, p, bag, lighter, 0)
    assert world.get(BACK, 0, STAND - 3) == tiles.BRICK
    assert world.get(FRONT, 0, STAND - 3) == tiles.SKY
