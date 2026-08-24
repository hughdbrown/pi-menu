"""Every shipped route must actually win its level.

Auto-play replays these routes blind, so a stale one -- recorded before
a level was redrawn or a physics constant moved -- would walk the
auto-player into a wall in front of an audience. Replaying is cheap
(a few hundred ticks a level), so all sixty run on every test run.
"""

from __future__ import annotations

import pytest

from pi_menu.platformer.autopilot import TICKS_PER_MOVE, Autopilot, decode
from pi_menu.platformer.levels import LEVELS
from pi_menu.platformer.routes import ROUTES
from pi_menu.platformer.routes import TICKS_PER_MOVE as RECORDED_TEMPO
from pi_menu.platformer.world import World

IDS = [level.id for level in LEVELS]


def test_every_level_has_a_route():
    assert set(ROUTES) == {level.id for level in LEVELS}


def test_the_recorded_tempo_matches_the_replayer():
    assert RECORDED_TEMPO == TICKS_PER_MOVE


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_the_route_wins_the_level(level):
    world = World(level)
    pilot = Autopilot(ROUTES[level.id])

    for _ in range(len(ROUTES[level.id]) * TICKS_PER_MOVE + 10):
        world.step(pilot.held())
        pilot.advance()
        if world.won:
            break

    assert world.alive, f"the route for {level.id} walked into something"
    assert world.won, f"the route for {level.id} ran out before the goal"


def test_a_route_round_trips_through_its_encoding():
    from pi_menu.platformer.autopilot import KEY_BITS

    route = ROUTES[LEVELS[0].id]
    moves = decode(route)

    assert len(moves) == len(route)
    assert all(move <= frozenset(KEY_BITS) for move in moves)


def test_an_exhausted_pilot_holds_nothing():
    pilot = Autopilot("22")
    for _ in range(2 * TICKS_PER_MOVE + 3):
        pilot.advance()

    assert pilot.exhausted is True
    assert pilot.held() == frozenset()
