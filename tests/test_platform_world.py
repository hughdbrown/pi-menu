"""The physics: what the player can and cannot do.

These tests pin the reachable envelope -- how high a jump goes, how far
it carries, how forgiving the ledges are -- because that envelope is
what every level is drawn against. Change a constant and the levels
stop being winnable, so the numbers are asserted here rather than left
to be discovered by playing.
"""

from __future__ import annotations

import pytest

from pi_menu.platformer.level import Level
from pi_menu.platformer.world import (
    BOUNCE_VELOCITY,
    BUFFER_TICKS,
    COYOTE_TICKS,
    JUMP,
    JUMP_VELOCITY,
    LEFT,
    MAX_FALL_SPEED,
    RIGHT,
    Event,
    World,
)

WIDE = 20


def level(*bottom_rows: str) -> Level:
    """Build a level from its bottom rows. The sky above is empty."""
    rows = [row.ljust(WIDE, ".") for row in bottom_rows]
    sky = ["." * WIDE] * (16 - len(rows))
    return Level("t", sky + rows)


def run(world: World, ticks: int, held=frozenset()) -> list[Event]:
    return [world.step(held) for _ in range(ticks)]


def settle(world: World) -> None:
    """Let the player fall onto whatever is below the spawn.

    Bounded, because a helper that spins forever turns a failing
    assertion into a hung test run and tells you nothing.
    """
    for _ in range(200):
        if world.on_ground:
            return
        world.step(frozenset())
    raise AssertionError("the player never landed")


FLOOR = "..@.............G..."


def flat() -> World:
    return World(level(FLOOR, "=" * WIDE))


# -- falling -------------------------------------------------------------


def test_a_player_in_the_air_falls_faster_each_tick():
    world = World(level("..@.................", "....................", "..====.........G===="))
    world.step(frozenset())
    first = world.vy
    world.step(frozenset())

    assert world.vy > first > 0


def test_a_fall_stops_on_top_of_a_platform():
    world = World(level("..@.................", "....................", "..====.........G===="))

    run(world, 60)

    assert world.on_ground is True
    assert world.y == pytest.approx(14.0)


def test_a_fall_never_outruns_the_collision_check():
    """Faster than a cell a tick and the player would pass through floors."""
    world = World(
        level("..@.................", *["." * WIDE] * 11, "..........G.........", "=" * WIDE)
    )

    run(world, 40)

    assert MAX_FALL_SPEED < 1.0
    assert world.vy <= MAX_FALL_SPEED


def test_a_long_fall_cannot_pass_through_a_one_cell_floor():
    world = World(
        level(
            "..@.................",
            *["." * WIDE] * 10,
            "=" * WIDE,  # one cell thick
            "....................",
            "...............G....",
            "....................",
        )
    )

    run(world, 200)

    assert world.alive is True
    assert world.y == pytest.approx(11.0)


# -- walking -------------------------------------------------------------


def test_holding_right_moves_right():
    world = flat()
    settle(world)
    before = world.x

    run(world, 10, {RIGHT})

    assert world.x > before


def test_letting_go_brings_the_player_to_a_stop():
    world = flat()
    settle(world)
    run(world, 10, {RIGHT})

    run(world, 10)

    assert world.vx == pytest.approx(0.0)


def test_a_wall_stops_the_player_without_stopping_the_fall():
    world = World(level("..@..=..............", "..=..=.........G===="))
    settle(world)

    run(world, 40, {RIGHT})

    assert world.x < 5.0
    assert world.vx == pytest.approx(0.0)


def test_the_edge_of_the_level_is_a_wall():
    world = flat()
    settle(world)

    run(world, 60, {LEFT})

    assert world.x == pytest.approx(0.0)


# -- jumping -------------------------------------------------------------


def _jump_rise(hold_ticks: int) -> float:
    """How far the player rises from a jump held for so many ticks."""
    world = flat()
    settle(world)
    start = world.y

    highest = start
    for tick in range(80):
        held = {JUMP} if tick < hold_ticks else frozenset()
        world.step(held)
        highest = min(highest, world.y)
        if tick > hold_ticks and world.on_ground:
            break
    return start - highest


def test_a_full_jump_clears_three_cells_but_not_four():
    rise = _jump_rise(hold_ticks=40)

    assert 3.0 < rise < 4.0


def test_tapping_jump_rises_about_a_cell_and_a_half():
    rise = _jump_rise(hold_ticks=1)

    assert 1.0 < rise < 2.0


def test_holding_jump_goes_higher_than_tapping_it():
    assert _jump_rise(hold_ticks=40) > _jump_rise(hold_ticks=1) + 1.0


def test_a_running_jump_clears_a_three_cell_gap():
    world = World(level("..@.................", "===...======...G===="))
    settle(world)

    for tick in range(80):
        held = {RIGHT, JUMP} if tick < 40 else {RIGHT}
        world.step(held)
        if world.on_ground and world.x > 6.0:
            break

    assert world.alive is True
    assert world.x > 6.0


def test_you_cannot_jump_again_in_mid_air():
    world = flat()
    settle(world)
    world.step({JUMP})
    rising = world.vy

    world.step(frozenset())
    world.step({JUMP})

    assert world.vy > rising  # gravity won; the second press did nothing


# -- forgiveness ---------------------------------------------------------


def _walk_off_a_ledge() -> World:
    world = World(level("..@.................", "=====...........G==="))
    settle(world)
    for _ in range(200):
        world.step({RIGHT})
        if not world.on_ground:
            return world
    raise AssertionError("the player never left the ledge")


def test_a_jump_just_after_leaving_a_ledge_still_works():
    world = _walk_off_a_ledge()

    world.step({RIGHT, JUMP})

    assert world.vy < 0


def test_a_jump_long_after_leaving_a_ledge_does_not():
    world = _walk_off_a_ledge()
    run(world, COYOTE_TICKS + 2, {RIGHT})

    world.step({RIGHT, JUMP})

    assert world.vy > 0


def test_a_jump_pressed_just_before_landing_fires_on_landing():
    world = World(
        level("..@.................", *["." * WIDE] * 7, "..........G.........", "..====.........=====")
    )
    # Fall until landing is a couple of ticks away, then press.
    for _ in range(200):
        if world.y > 12.0:
            break
        world.step(frozenset())
    world.step({JUMP})  # the press: still airborne
    run(world, BUFFER_TICKS - 1)

    assert world.vy < 0, "the buffered jump never fired"


# -- coins, spikes and the goal ------------------------------------------


def test_walking_over_a_coin_collects_it():
    world = World(level("..@..o..........G...", "=" * WIDE))
    settle(world)

    events = run(world, 60, {RIGHT})

    assert Event.COIN in events
    assert world.coins == frozenset()


def test_the_goal_stays_shut_until_the_last_coin_is_taken():
    world = World(level("..@..o..........G...", "=" * WIDE))
    settle(world)

    assert world.goal_open is False
    run(world, 60, {RIGHT})
    assert world.goal_open is True


def test_reaching_an_open_goal_wins():
    world = World(level("..@..o.....G........", "=" * WIDE))
    settle(world)

    events = run(world, 120, {RIGHT})

    assert Event.WON in events
    assert world.won is True


def test_reaching_a_shut_goal_does_nothing():
    """The coin here is past the goal, so it cannot have been taken yet."""
    world = World(level("..@........G.....o..", "=" * WIDE))
    settle(world)

    run(world, 60, {RIGHT})

    assert world.x > 11.0, "the player never got to the goal"
    assert world.won is False


def test_a_spike_kills():
    world = World(level("..@..^..........G...", "=" * WIDE))
    settle(world)

    events = run(world, 60, {RIGHT})

    assert Event.DIED in events
    assert world.alive is False


def test_walking_under_a_spike_does_not_kill():
    """Spikes have a tighter reach than coins: overhead is survivable."""
    world = World(
        level("..@.................", "....^...............", "..........G.........", "=" * WIDE)
    )
    settle(world)

    run(world, 30, {RIGHT})

    assert world.alive is True


def test_falling_out_of_the_world_kills():
    """Nothing to land on: the spawn here is over a pit."""
    world = World(level("..@.................", "==.............G===="))

    events = run(world, 120, {RIGHT})

    assert Event.DIED in events
    assert world.alive is False


def test_a_dead_player_stops_moving():
    world = World(level("..@..^..........G...", "=" * WIDE))
    settle(world)
    run(world, 60, {RIGHT})
    resting = (world.x, world.y)

    run(world, 10, {RIGHT})

    assert (world.x, world.y) == resting


# -- restarting ----------------------------------------------------------


def test_resetting_puts_the_player_and_the_coins_back():
    world = World(level("..@..o.....^....G...", "=" * WIDE))
    settle(world)
    run(world, 90, {RIGHT})
    assert world.alive is False

    world.reset()

    assert world.alive is True
    assert world.won is False
    assert world.coins == frozenset({(5, 14)})
    assert (world.x, world.y) == (2.0, 14.0)


def test_the_player_starts_on_the_spawn_tile():
    world = flat()

    assert (world.x, world.y) == (2.0, 14.0)


def test_the_drawn_pixel_follows_the_player():
    world = flat()
    settle(world)

    assert world.pixel == (2, 14)


# -- moving platforms ----------------------------------------------------


def _mover_level() -> Level:
    """A track in mid-air, with the player starting on the platform."""
    return level(
        "....@...............",  # row 9
        "....------..........",  # row 10: the track
        "....................",
        "....................",
        "................G...",
        "=" * WIDE,
        "=" * WIDE,
    )


def test_a_moving_platform_is_something_to_stand_on():
    world = World(_mover_level())
    settle(world)

    assert world.on_ground is True
    assert world.y == pytest.approx(9.0)


def test_a_moving_platform_carries_the_player_along_with_it():
    world = World(_mover_level())
    settle(world)
    start = world.x

    run(world, 24)  # four whole-cell steps of the platform

    assert world.x > start
    assert world.on_ground is True, "the platform slid out from under them"


def test_a_platform_that_reaches_the_end_of_its_track_comes_back():
    mover = _mover_level().movers[0]

    assert mover.occupied(mover.period) == mover.occupied(0)
    assert mover.occupied(mover.period // 2) != mover.occupied(0)


def test_a_platform_counts_as_solid_where_it_is_now():
    world = World(_mover_level())
    occupied = world.level.movers[0].occupied(0)

    assert world.solid(*occupied[0]) is True
    assert world.solid(occupied[0][0], occupied[0][1] - 1) is False


def test_a_platform_that_has_moved_on_is_no_longer_solid_behind_it():
    world = World(_mover_level())
    behind = world.level.movers[0].occupied(0)[0]

    run(world, 24)

    assert world.solid(*behind) is False


def test_a_platform_can_outrun_a_player_still_falling_towards_it():
    """Carrying only applies once you are standing on it, not mid-air."""
    world = World(
        level(
            "....@...............",
            "....................",
            "....................",
            "....------..........",
            "................G...",
            "=" * WIDE,
            "=" * WIDE,
        )
    )
    mover = world.level.movers[0]

    run(world, 40)

    assert world.on_ground is True
    assert world.y > mover.cells[0][1], "they landed on a platform long gone"


# -- bounce pads ---------------------------------------------------------


def test_a_bounce_pad_throws_the_player_higher_than_a_jump():
    world = World(level("..@.............G...", "======b============="))
    settle(world)
    ground = world.y

    highest = ground
    for _ in range(60):
        world.step({RIGHT})
        highest = min(highest, world.y)

    assert ground - highest > 4.0, "the pad barely lifted them"


def test_a_bounce_pad_lifts_further_than_the_best_jump():
    assert -BOUNCE_VELOCITY > -JUMP_VELOCITY


def test_a_run_of_pads_keeps_the_player_in_the_air():
    world = World(level("..@.............G...", "===bbbbbb==========="))
    settle(world)

    airborne = 0
    for _ in range(60):
        world.step({RIGHT})
        airborne += not world.on_ground

    assert airborne > 40, "they spent most of the time on the ground"


# -- ice -----------------------------------------------------------------


def _icy() -> World:
    return World(level("..@.............G...", "==iiiiiiiiiiii======"))


def _grippy() -> World:
    return World(level("..@.............G...", "=" * WIDE))


def test_ice_lets_the_player_keep_sliding():
    world = _icy()
    settle(world)
    run(world, 40, {RIGHT})

    run(world, 10)

    assert world.vx > 0.0, "they stopped dead on ice"


def test_ordinary_ground_stops_the_player_where_ice_does_not():
    icy, grippy = _icy(), _grippy()
    for world in (icy, grippy):
        settle(world)
        run(world, 40, {RIGHT})
        run(world, 10)

    assert grippy.vx == pytest.approx(0.0)
    assert icy.vx > grippy.vx


def test_ice_is_slower_to_get_going_as_well_as_to_stop():
    icy, grippy = _icy(), _grippy()
    for world in (icy, grippy):
        settle(world)
        run(world, 4, {RIGHT})

    assert icy.vx < grippy.vx


# -- conveyors -----------------------------------------------------------


def test_a_conveyor_carries_a_player_who_is_not_walking():
    world = World(level("..@.............G...", "==>>>>>>>>=========="))
    settle(world)
    start = world.x

    run(world, 20)

    assert world.x > start


def test_a_conveyor_can_be_walked_against():
    world = World(level("..@.............G...", "==<<<<<<<<=========="))
    settle(world)
    start = world.x

    run(world, 40, {RIGHT})

    assert world.x > start, "walking against the belt got nowhere"


def test_a_conveyor_slows_the_player_down_compared_to_bare_ground():
    against = World(level("..@.............G...", "==<<<<<<<<=========="))
    plain = World(level("..@.............G...", "=" * WIDE))
    for world in (against, plain):
        settle(world)
        run(world, 40, {RIGHT})

    assert against.x < plain.x


def test_a_conveyor_does_not_push_the_player_into_a_wall():
    world = World(level("..@.............G...", "<<<<<<<============="))
    settle(world)

    run(world, 80)

    assert world.x == pytest.approx(0.0)
    assert world.alive is True


# -- crumbling platforms -------------------------------------------------


def test_a_crumbling_tile_holds_you_the_first_time():
    world = World(level("..@.............G...", "===cc==============="))
    settle(world)

    run(world, 30, {RIGHT})

    assert world.alive is True


def test_a_crumbling_tile_is_gone_once_you_step_off_it():
    world = World(level("..@.............G...", "===ccc=============="))
    settle(world)

    run(world, 30, {RIGHT})

    assert world.crumbled, "nothing crumbled"
    assert all(not world.solid(*cell) for cell in world.crumbled)


def test_a_crumbled_tile_leaves_a_hole_to_fall_through():
    """A row of them is a route you get to take exactly once."""
    world = World(level("..@.............G...", "===ccc=============="))
    settle(world)
    run(world, 30, {RIGHT})
    assert world.crumbled and world.alive

    world.x = float(min(x for x, _ in world.crumbled))
    events = run(world, 40)

    assert Event.DIED in events


def test_resetting_puts_the_crumbled_tiles_back():
    world = World(level("..@.............G...", "===ccc=============="))
    settle(world)
    run(world, 30, {RIGHT})
    assert world.crumbled

    world.reset()

    assert world.crumbled == frozenset()


# -- portals -------------------------------------------------------------


def test_walking_into_a_portal_puts_you_out_of_the_other_one():
    world = World(level("..@..p........p.G...", "=" * WIDE))
    settle(world)

    run(world, 30, {RIGHT})

    assert world.x > 10.0, "the portal did not move them"


def test_a_portal_does_not_throw_the_player_back_and_forth():
    world = World(level("..@..p........p.G...", "=" * WIDE))
    settle(world)
    run(world, 30, {RIGHT})
    landed = world.x

    run(world, 4)

    assert abs(world.x - landed) < 1.0, "they were bounced straight back through"


def test_a_portal_keeps_the_speed_you_arrived_with():
    world = World(level("..@..p........p.G...", "=" * WIDE))
    settle(world)
    run(world, 30, {RIGHT})

    assert world.vx > 0.0


def test_a_level_without_portals_is_untouched_by_them():
    world = World(level("..@..o..........G...", "=" * WIDE))
    settle(world)

    run(world, 30, {RIGHT})

    assert world.alive is True


# -- enemies -------------------------------------------------------------


def _enemy_level() -> Level:
    return level("..@..E..........G...", "=" * WIDE)


def test_an_enemy_walks_its_ledge():
    level_ = _enemy_level()
    seen = {level_.enemies[0].at(tick) for tick in range(level_.period)}

    assert len(seen) > 1


def test_an_enemy_turns_back_at_the_edge_of_the_world():
    level_ = _enemy_level()
    columns = {x for x, _ in level_.enemies[0].path}

    assert min(columns) >= 0
    assert max(columns) < level_.width


def test_walking_into_an_enemy_kills():
    world = World(_enemy_level())
    settle(world)

    events = run(world, 80, {RIGHT})

    assert Event.DIED in events
    assert world.alive is False


# -- what the solver has to tell apart -----------------------------------


def test_the_level_clock_shows_in_the_dynamic_key():
    world = World(_enemy_level())
    first = world.dynamic_key()

    run(world, 6)

    assert world.dynamic_key() != first


def test_a_crumbled_tile_shows_in_the_dynamic_key():
    world = World(level("..@.............G...", "===ccc=============="))
    settle(world)
    before = world.dynamic_key()

    run(world, 30, {RIGHT})

    assert world.dynamic_key()[1] != before[1]


def test_a_still_level_has_only_one_clock_reading():
    world = World(level("..@..o..........G...", "=" * WIDE))
    settle(world)

    run(world, 40, {RIGHT})

    assert world.dynamic_key()[0] == 0
