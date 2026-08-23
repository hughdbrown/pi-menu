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
    BUFFER_TICKS,
    COYOTE_TICKS,
    JUMP,
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
