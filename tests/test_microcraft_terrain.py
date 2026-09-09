"""The world is deterministic, loops, and is shaped the way the rules say."""

from __future__ import annotations

import pytest

from pi_menu.microcraft import noise, tiles
from pi_menu.microcraft.terrain import (
    BACK,
    CHUNK_W,
    FRONT,
    GRASS_LINE_Y,
    SEA_LEVEL,
    TREE_LINE_Y,
    WORLD_H,
    WORLD_PERIOD,
    WORLD_RADIUS,
    Generator,
    World,
)

SEEDS = (1, 42, 123456789, 2147483646)


# -- noise -----------------------------------------------------------------


def test_hash2_is_repeatable_and_in_the_unit_interval():
    for seed in SEEDS:
        values = [noise.hash2(x, y, 7, seed) for x in range(-50, 50) for y in range(0, 30)]
        assert all(0.0 <= v < 1.0 for v in values)
        assert values == [noise.hash2(x, y, 7, seed) for x in range(-50, 50) for y in range(0, 30)]


def test_different_cells_and_seeds_hash_differently():
    assert noise.hash2(1, 2, 3, 4) != noise.hash2(2, 1, 3, 4)
    assert noise.hash2(1, 2, 3, 4) != noise.hash2(1, 2, 3, 5)
    assert noise.hash2(1, 2, 3, 4) != noise.hash2(1, 2, 4, 4)


def test_hash2_spreads_evenly():
    values = [noise.hash2(x, 0, 1, 99) for x in range(20000)]
    assert 0.48 < sum(values) / len(values) < 0.52


def test_noise1d_interpolates_between_lattice_values():
    v0 = noise.noise1d(10, 1, 1.0, 5)
    v1 = noise.noise1d(11, 1, 1.0, 5)
    mid = noise.noise1d(10.5, 1, 1.0, 5)
    assert min(v0, v1) <= mid <= max(v0, v1)


def test_wrap_x_folds_both_ends_and_leaves_the_middle_alone():
    assert noise.wrap_x(0) == 0
    assert noise.wrap_x(WORLD_RADIUS) == -WORLD_RADIUS
    assert noise.wrap_x(-WORLD_RADIUS) == -WORLD_RADIUS
    assert noise.wrap_x(WORLD_RADIUS + 5) == -WORLD_RADIUS + 5
    assert noise.wrap_x(-WORLD_RADIUS - 5) == WORLD_RADIUS - 5
    assert noise.wrap_x(3 * WORLD_PERIOD + 17) == 17
    assert noise.wrap_x(12.25) == 12.25


def test_round_half_up_matches_javascript():
    assert noise.round_half_up(2.5) == 3
    assert noise.round_half_up(3.5) == 4
    assert noise.round_half_up(-2.5) == -2
    assert noise.round_half_up(2.4) == 2


# -- heights ---------------------------------------------------------------


@pytest.fixture(params=SEEDS)
def gen(request):
    return Generator(request.param)


def test_heights_are_the_same_all_the_way_round(gen):
    for x in (0, 17, -400, 999):
        assert gen.front_height(x) == gen.front_height(x + WORLD_PERIOD)
        assert gen.front_height(x) == gen.front_height(x - 2 * WORLD_PERIOD)
        assert gen.back_height(x) == gen.back_height(x + WORLD_PERIOD)


def test_the_background_never_rises_more_than_five_above_the_front(gen):
    for x in range(-300, 300):
        assert gen.back_height(x) >= gen.front_height(x) - 5


def test_the_ground_stays_inside_the_world(gen):
    for x in range(-WORLD_RADIUS, WORLD_RADIUS, 7):
        assert 0 < gen.front_height(x) < WORLD_H - 3


def test_open_ocean_has_its_bed_below_sea_level(gen):
    oceans = [x for x in range(-WORLD_RADIUS, WORLD_RADIUS) if gen.ocean_factor(x) >= 1]
    for x in oceans[:200]:
        assert gen.front_height(x) > SEA_LEVEL
        assert gen.surface_ref(x) == SEA_LEVEL


def test_the_spawn_is_on_dry_land(gen):
    x = gen.find_spawn_x()
    assert -WORLD_RADIUS <= x < WORLD_RADIUS
    assert not gen.is_water_column(x)


# -- chunks ----------------------------------------------------------------


def column(world: World, layer: int, x: int) -> bytearray:
    wx = int(noise.wrap_x(x))
    index = wx // CHUNK_W
    return world.chunk(layer, index)[wx - index * CHUNK_W]


def test_a_chunk_is_thirty_two_columns_of_the_full_depth():
    grid = Generator(1).generate_chunk(0, FRONT)
    assert len(grid) == CHUNK_W
    assert all(len(col) == WORLD_H for col in grid)


def test_a_dry_column_is_sky_grass_dirt_dirt_then_stone_or_ore(gen):
    world = World(gen.seed)
    # The spawn is dry but may be a sandy shore tile or a bare summit;
    # walk east to the first ordinary grassy column.
    x = gen.find_spawn_x()
    while (
        gen.is_water_column(x - 1)
        or gen.is_water_column(x + 1)
        or gen.front_height(x) <= GRASS_LINE_Y
    ):
        x += 1
    surf = gen.front_height(x)
    col = column(world, FRONT, x)
    assert col[surf] == tiles.GRASS
    assert col[surf + 1] == tiles.DIRT and col[surf + 2] == tiles.DIRT
    assert col[surf + 3] in (tiles.STONE, tiles.COAL_ORE, tiles.IRON_ORE, tiles.COPPER_ORE)
    assert all(t in (tiles.SKY, tiles.LEAF, tiles.WOOD) for t in col[:surf])


def test_a_flooded_column_holds_water_from_sea_level_to_a_sandy_bed(gen):
    world = World(gen.seed)
    flooded = [x for x in range(-WORLD_RADIUS, WORLD_RADIUS) if gen.is_water_column(x)]
    assert flooded, "every seed floods somewhere"
    x = flooded[len(flooded) // 2]
    surf = gen.front_height(x)
    col = column(world, FRONT, x)
    assert all(t == tiles.WATER for t in col[SEA_LEVEL:surf])
    assert col[surf] in (tiles.SAND, tiles.CLAY)
    assert col[surf + 1] in (tiles.SAND, tiles.CLAY)
    # The background has no water: it is scenery, not something to swim in.
    back_surf = gen.back_height(x)
    assert all(t == tiles.SKY for t in column(world, BACK, x)[SEA_LEVEL:back_surf])


def test_the_shore_tile_beside_water_is_sand(gen):
    world = World(gen.seed)
    for x in range(-WORLD_RADIUS, WORLD_RADIUS):
        if not gen.is_water_column(x) and gen.is_water_column(x + 1):
            assert column(world, FRONT, x)[gen.front_height(x)] == tiles.SAND
            return
    pytest.fail("no shoreline found")


def test_high_ground_is_bare_stone(gen):
    world = World(gen.seed)
    peaks = [x for x in range(-WORLD_RADIUS, WORLD_RADIUS) if gen.front_height(x) <= GRASS_LINE_Y]
    if not peaks:
        pytest.skip("this seed has no mountain tall enough")
    x = peaks[0]
    assert column(world, FRONT, x)[gen.front_height(x)] == tiles.STONE


def test_trees_stand_on_grass_with_a_trunk_of_four_and_a_canopy(gen):
    world = World(gen.seed)
    for cell in range(-150, 150):
        tree = gen.tree_in_cell(cell, FRONT)
        if tree is None:
            continue
        x, surf = tree
        col = column(world, FRONT, x)
        assert col[surf] == tiles.GRASS
        assert all(col[surf + dy] == tiles.WOOD for dy in range(-4, 0))
        assert col[surf - 5] == tiles.LEAF and col[surf - 6] == tiles.LEAF
        assert column(world, FRONT, x - 2)[surf - 5] == tiles.LEAF
        assert not gen.is_water_column(x + 2) and not gen.is_water_column(x - 2)
        assert surf > TREE_LINE_Y
        return
    pytest.fail("no tree in 300 cells")


def test_the_core_is_lava_and_the_shallows_are_not():
    world = World(3)
    x = world.gen.find_spawn_x()
    col = column(world, FRONT, x)
    assert col[WORLD_H - 1] == tiles.LAVA
    surf = world.gen.front_height(x)
    assert tiles.LAVA not in col[surf : surf + 40]
    deep = col[WORLD_H - 60 :]
    assert sum(1 for t in deep if t == tiles.LAVA) > len(deep) // 2


def test_ore_is_rare_and_only_in_stone():
    grid = Generator(5).generate_chunk(0, FRONT)
    cells = [t for col in grid for t in col[300:600]]
    ores = sum(1 for t in cells if t in (tiles.COAL_ORE, tiles.IRON_ORE, tiles.COPPER_ORE))
    assert 0.02 < ores / len(cells) < 0.08


# -- the world -------------------------------------------------------------


def test_get_and_set_round_trip_across_a_chunk_edge():
    world = World(9)
    for x in (CHUNK_W - 1, CHUNK_W, -1, 0, WORLD_RADIUS - 1):
        world.set(FRONT, x, 100, tiles.BRICK)
        assert world.get(FRONT, x, 100) == tiles.BRICK
        assert world.get(FRONT, x + WORLD_PERIOD, 100) == tiles.BRICK
        assert world.get(BACK, x, 100) == tiles.SKY


def test_above_the_world_is_sky_and_below_it_is_stone():
    world = World(9)
    assert world.get(FRONT, 5, -1) == tiles.SKY
    assert world.get(FRONT, 5, WORLD_H) == tiles.STONE
    world.set(FRONT, 5, -1, tiles.BRICK)  # silently ignored
    assert world.get(FRONT, 5, -1) == tiles.SKY


def test_chunks_are_made_once_and_kept():
    world = World(9)
    world.get(FRONT, 3, 250)
    world.get(FRONT, 4, 251)
    assert world.chunks_loaded == 1
    world.set(FRONT, 3, 250, tiles.BRICK)
    world.get(FRONT, 40, 250)
    assert world.chunks_loaded == 2
    assert world.get(FRONT, 3, 250) == tiles.BRICK


def test_solid_and_fluid_helpers_read_the_front_layer():
    world = World(9)
    world.set(FRONT, 0, 100, tiles.WATER)
    world.set(BACK, 0, 101, tiles.STONE)
    assert world.fluid_at(0, 100) and not world.solid_at(0, 100)
    assert not world.solid_at(0, 101)
    assert world.is_open_water_surface(0, 100)
    world.set(FRONT, 0, 99, tiles.DIRT)
    assert not world.is_open_water_surface(0, 100)
