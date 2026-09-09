"""Fluids spread and recede, fire burns and drowns, grass grows and dies."""

from __future__ import annotations

import random

import pytest

from pi_menu.microcraft import sim, tiles
from pi_menu.microcraft.terrain import BACK, FRONT, World

#: Rows this high are open sky in every seed, so tests can build freely.
SKY_ROW = 120


class AlwaysRoll:
    """A stand-in RNG that always rolls the same number."""

    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


@pytest.fixture
def world():
    return World(7)


def shelf(world: World, x0: int, x1: int, y: int, layer: int = FRONT) -> None:
    for x in range(x0, x1 + 1):
        world.set(layer, x, y, tiles.STONE)


def row(world: World, y: int, x0: int, x1: int, layer: int = FRONT) -> list:
    return [world.get(layer, x, y) for x in range(x0, x1 + 1)]


# -- fluids ----------------------------------------------------------------


def test_a_source_on_a_shelf_spreads_and_tapers_to_level_three(world):
    shelf(world, -10, 10, SKY_ROW + 1)
    world.set(FRONT, 0, SKY_ROW, tiles.WATER)

    sim.simulate_fluids(world, 0, SKY_ROW)
    # Fed from the left, a tile flows rightward, and the other way about.
    assert row(world, SKY_ROW, -1, 1) == [tiles.WATER_FLOW_L1, tiles.WATER, tiles.WATER_FLOW_R1]

    for _ in range(4):
        sim.simulate_fluids(world, 0, SKY_ROW)
    assert row(world, SKY_ROW, -4, 4) == [
        tiles.SKY,
        tiles.WATER_FLOW_L3, tiles.WATER_FLOW_L2, tiles.WATER_FLOW_L1,
        tiles.WATER,
        tiles.WATER_FLOW_R1, tiles.WATER_FLOW_R2, tiles.WATER_FLOW_R3,
        tiles.SKY,
    ]


def test_a_source_over_air_falls_and_pools_when_it_lands(world):
    shelf(world, -10, 10, SKY_ROW + 3)
    world.set(FRONT, 0, SKY_ROW, tiles.LAVA)

    sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, 0, SKY_ROW + 1) == tiles.LAVA_FLOW_DOWN
    # The source itself is unsupported, so it can only reach one block sideways.
    assert row(world, SKY_ROW, -2, 2) == [
        tiles.SKY, tiles.LAVA_FLOW_L1, tiles.LAVA, tiles.LAVA_FLOW_R1, tiles.SKY
    ]

    for _ in range(6):
        sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, 0, SKY_ROW + 2) == tiles.LAVA_FLOW_DOWN
    # Landed on the shelf, it pools out to level three and no further.
    landed = row(world, SKY_ROW + 2, -8, 8)
    assert tiles.LAVA_FLOW_R3 in landed and tiles.LAVA_FLOW_L3 in landed
    assert landed[0] == tiles.SKY and landed[-1] == tiles.SKY


def test_a_falling_tile_in_mid_air_feeds_nothing_sideways(world):
    shelf(world, -10, 10, SKY_ROW + 3)
    world.set(FRONT, 0, SKY_ROW, tiles.WATER_FLOW_DOWN)  # a stray drip, unfed
    sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, 1, SKY_ROW) == tiles.SKY
    assert world.get(FRONT, -1, SKY_ROW) == tiles.SKY
    assert world.get(FRONT, 0, SKY_ROW) == tiles.SKY  # and, unfed, it is gone

    world.set(FRONT, 0, SKY_ROW + 2, tiles.WATER_FLOW_DOWN)  # the same drip, landed
    sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, 1, SKY_ROW + 2) == tiles.WATER_FLOW_R1
    assert world.get(FRONT, -1, SKY_ROW + 2) == tiles.WATER_FLOW_L1


def test_removing_the_source_makes_the_flow_recede(world):
    shelf(world, -10, 10, SKY_ROW + 1)
    world.set(FRONT, 0, SKY_ROW, tiles.WATER)
    for _ in range(5):
        sim.simulate_fluids(world, 0, SKY_ROW)
    world.set(FRONT, 0, SKY_ROW, tiles.SKY)

    for _ in range(4):
        sim.simulate_fluids(world, 0, SKY_ROW)
    assert all(t == tiles.SKY for t in row(world, SKY_ROW, -5, 5))


def test_air_between_two_sources_becomes_a_source(world):
    shelf(world, -10, 10, SKY_ROW + 1)
    world.set(FRONT, -1, SKY_ROW, tiles.WATER)
    world.set(FRONT, 1, SKY_ROW, tiles.WATER)
    sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, 0, SKY_ROW) == tiles.WATER


def test_a_wall_stops_the_flow(world):
    shelf(world, -10, 10, SKY_ROW + 1)
    world.set(FRONT, 2, SKY_ROW, tiles.STONE)
    world.set(FRONT, 0, SKY_ROW, tiles.WATER)
    for _ in range(5):
        sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, 1, SKY_ROW) == tiles.WATER_FLOW_R1
    assert world.get(FRONT, 2, SKY_ROW) == tiles.STONE
    assert world.get(FRONT, 3, SKY_ROW) == tiles.SKY


def test_water_and_lava_flow_independently_and_on_both_layers(world):
    shelf(world, -10, 10, SKY_ROW + 1)
    shelf(world, -10, 10, SKY_ROW + 1, layer=BACK)
    world.set(FRONT, 0, SKY_ROW, tiles.WATER)
    world.set(BACK, 0, SKY_ROW, tiles.LAVA)
    sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, 1, SKY_ROW) == tiles.WATER_FLOW_R1
    assert world.get(BACK, 1, SKY_ROW) == tiles.LAVA_FLOW_R1


def test_nothing_happens_outside_the_simulation_box(world):
    far = sim.BLOCK_SIM_RADIUS + 5
    shelf(world, far - 5, far + 5, SKY_ROW + 1)
    world.set(FRONT, far, SKY_ROW, tiles.WATER)
    sim.simulate_fluids(world, 0, SKY_ROW)
    assert world.get(FRONT, far + 1, SKY_ROW) == tiles.SKY
    sim.simulate_fluids(world, far, SKY_ROW)
    assert world.get(FRONT, far + 1, SKY_ROW) == tiles.WATER_FLOW_R1


# -- fire ------------------------------------------------------------------


def test_a_plank_beside_lava_catches_and_burns_away(world):
    shelf(world, -10, 10, SKY_ROW + 1)
    world.set(FRONT, 0, SKY_ROW, tiles.WOOD_PLANKS)
    world.set(FRONT, 1, SKY_ROW, tiles.LAVA)

    # Igniting and the first tick of burning share a call, as in the HTML,
    # so the block is gone on the thirtieth call.
    sim.simulate_fire(world, 0, SKY_ROW)
    assert world.burning[(FRONT, 0, SKY_ROW)] == sim.BURN_DURATION_TICKS - 1

    for _ in range(sim.BURN_DURATION_TICKS - 2):
        sim.simulate_fire(world, 0, SKY_ROW)
        assert world.get(FRONT, 0, SKY_ROW) == tiles.WOOD_PLANKS
    sim.simulate_fire(world, 0, SKY_ROW)
    assert world.get(FRONT, 0, SKY_ROW) == tiles.SKY
    assert (FRONT, 0, SKY_ROW) not in world.burning


def test_stone_beside_lava_does_not_burn(world):
    world.set(FRONT, 0, SKY_ROW, tiles.STONE)
    world.set(FRONT, 1, SKY_ROW, tiles.LAVA)
    sim.simulate_fire(world, 0, SKY_ROW)
    assert not world.burning


def test_water_puts_a_fire_out_and_the_block_survives(world):
    world.set(FRONT, 0, SKY_ROW, tiles.WOOD)
    world.burning[(FRONT, 0, SKY_ROW)] = 10
    world.set(FRONT, 0, SKY_ROW - 1, tiles.WATER_FLOW_DOWN)
    sim.simulate_fire(world, 0, SKY_ROW)
    assert not world.burning
    assert world.get(FRONT, 0, SKY_ROW) == tiles.WOOD


def test_clay_beside_a_fire_bakes_into_brick(world):
    world.set(FRONT, 0, SKY_ROW, tiles.WOOD)
    world.set(FRONT, -1, SKY_ROW, tiles.CLAY)
    world.burning[(FRONT, 0, SKY_ROW)] = 10
    sim.simulate_fire(world, 0, SKY_ROW)
    assert world.get(FRONT, -1, SKY_ROW) == tiles.BRICK


def test_a_fire_whose_block_was_mined_goes_out(world):
    world.burning[(FRONT, 0, SKY_ROW)] = 10
    sim.simulate_fire(world, 0, SKY_ROW)
    assert not world.burning


def test_a_stick_lights_a_block_on_the_fifth_quick_tap(world):
    lighter = sim.StickLighter()
    for tap in range(4):
        assert lighter.tap(world, FRONT, 3, SKY_ROW, tap * 100) is False
    assert lighter.tap(world, FRONT, 3, SKY_ROW, 400) is True
    assert world.burning[(FRONT, 3, SKY_ROW)] == sim.BURN_DURATION_TICKS


def test_slow_taps_or_a_different_block_start_the_count_again(world):
    lighter = sim.StickLighter()
    for tap in range(4):
        lighter.tap(world, FRONT, 3, SKY_ROW, tap * 100)
    assert lighter.tap(world, FRONT, 3, SKY_ROW, 300 + sim.STICK_IGNITE_WINDOW_MS + 1) is False
    for tap in range(3):
        lighter.tap(world, FRONT, 4, SKY_ROW, 2000 + tap * 100)
    assert lighter.tap(world, FRONT, 3, SKY_ROW, 2300) is False
    assert not world.burning


# -- grass -----------------------------------------------------------------

#: Deep enough that the grass line does not apply and nothing is generated
#: here but stone, which the tests clear.
DEEP = 600


def meadow(world: World) -> None:
    for x in range(-12, 13):
        for y in range(DEEP - 5, DEEP):
            world.set(FRONT, x, y, tiles.SKY)
        world.set(FRONT, x, DEEP, tiles.DIRT)
    world.set(FRONT, 0, DEEP, tiles.GRASS)


def test_sunlit_dirt_beside_grass_greens_when_the_roll_allows(world):
    meadow(world)
    sim.simulate_grass(world, 0, DEEP, AlwaysRoll(0.0))
    assert row(world, DEEP, -2, 2) == [tiles.DIRT, tiles.GRASS, tiles.GRASS, tiles.GRASS, tiles.DIRT]
    sim.simulate_grass(world, 0, DEEP, AlwaysRoll(0.99))
    assert row(world, DEEP, -2, 2) == [tiles.DIRT, tiles.GRASS, tiles.GRASS, tiles.GRASS, tiles.DIRT]


def test_covered_dirt_never_greens(world):
    meadow(world)
    world.set(FRONT, 1, DEEP - 1, tiles.STONE)
    sim.simulate_grass(world, 0, DEEP, AlwaysRoll(0.0))
    assert world.get(FRONT, 1, DEEP) == tiles.DIRT
    assert world.get(FRONT, -1, DEEP) == tiles.GRASS


def test_grass_above_the_grass_line_stays_dirt(world):
    high = 200  # above GRASS_LINE_Y, open sky
    for x in range(-3, 4):
        world.set(FRONT, x, high, tiles.DIRT)
    world.set(FRONT, 0, high, tiles.GRASS)
    sim.simulate_grass(world, 0, high, AlwaysRoll(0.0))
    assert world.get(FRONT, 1, high) == tiles.DIRT


def test_covered_grass_dies_after_the_decay_time_and_recovers_if_uncovered(world):
    meadow(world)
    world.set(FRONT, 0, DEEP - 1, tiles.STONE)
    for _ in range(sim.GRASS_DECAY_TICKS - 1):
        sim.simulate_grass(world, 0, DEEP, AlwaysRoll(0.99))
    assert world.get(FRONT, 0, DEEP) == tiles.GRASS
    world.set(FRONT, 0, DEEP - 1, tiles.SKY)
    sim.simulate_grass(world, 0, DEEP, AlwaysRoll(0.99))
    assert (FRONT, 0, DEEP) not in world.grass_covered

    world.set(FRONT, 0, DEEP - 1, tiles.STONE)
    for _ in range(sim.GRASS_DECAY_TICKS):
        sim.simulate_grass(world, 0, DEEP, AlwaysRoll(0.99))
    assert world.get(FRONT, 0, DEEP) == tiles.DIRT


def test_grass_uses_the_random_source_it_is_given(world):
    meadow(world)
    rng = random.Random(1)
    sim.simulate_grass(world, 0, DEEP, rng)  # must not raise
