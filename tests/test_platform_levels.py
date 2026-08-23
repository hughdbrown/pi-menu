"""The level set, and proof that every one of them can be finished.

The last test here is the important one. A hand-drawn map can be well
formed, readable and pretty, and still be impossible: a coin one cell
above the jump arc, a ledge you can land on but not leave. Nothing in
the ASCII shows that. So each level is played by a search that uses the
real physics, and passes only when it finds a sequence of key presses
that actually wins.
"""

from __future__ import annotations

import pytest

from pi_menu.platformer.level import Level
from pi_menu.platformer.levels import LEVELS, title
from platform_solver import Unwinnable, solve

IDS = [level.id for level in LEVELS]


def test_there_are_at_least_ten_levels():
    assert len(LEVELS) >= 10


def test_every_entry_is_a_parsed_level():
    assert all(isinstance(level, Level) for level in LEVELS)


def test_every_level_id_is_unique():
    assert len(set(IDS)) == len(IDS)


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_every_level_is_wider_than_the_panel(level):
    assert level.width > 16, "a level no wider than the panel never scrolls"


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_every_level_has_coins_to_collect(level):
    assert level.coins, "with no coins the goal opens immediately"


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_no_level_starts_the_player_inside_a_wall(level):
    assert level.static_solid(*level.spawn) is False


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_no_level_buries_its_goal_in_a_wall(level):
    assert level.static_solid(*level.goal) is False


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_nothing_important_sits_on_a_spike(level):
    """A coin you cannot take without dying is not a coin."""
    assert not (level.coins & level.spikes)
    assert level.goal not in level.spikes
    assert level.spawn not in level.spikes


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_the_level_can_actually_be_finished(level):
    try:
        moves = solve(level)
    except Unwinnable as exc:  # pragma: no cover - only when a level is broken
        pytest.fail(str(exc))
    assert moves, "the level was won without pressing anything"


def test_levels_are_titled_by_their_position():
    assert title(0).startswith("1. ")
    assert title(len(LEVELS) - 1).startswith(f"{len(LEVELS)}. ")


# -- the moving parts ----------------------------------------------------

MOVING = [level for level in LEVELS if level.moves]


def test_some_levels_move_and_some_do_not():
    assert MOVING and len(MOVING) < len(LEVELS)


@pytest.mark.parametrize("level", MOVING, ids=[level.id for level in MOVING])
def test_a_moving_level_comes_back_to_where_it_started(level):
    assert level.period > 1
    for mover in level.movers:
        assert mover.occupied(level.period) == mover.occupied(0)
    for enemy in level.enemies:
        assert enemy.at(level.period) == enemy.at(0)


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_no_level_has_a_mover_too_short_to_be_worth_riding(level):
    """A coin drawn on a track splits it into two stubs that barely move."""
    for mover in level.movers:
        assert mover.span >= 2, f"{level.id}: a track was cut short at {mover.cells[0]}"


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_no_level_takes_so_long_to_repeat_that_it_cannot_be_searched(level):
    """The period multiplies the solver's state space.

    Two enemies in pens of different lengths took one level to a period
    of 2184 and put it out of the solver's reach entirely. Matching the
    pens brought it to 24.
    """
    assert level.period <= 240, f"{level.id}: period {level.period}"


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_nothing_that_moves_starts_inside_a_wall(level):
    for enemy in level.enemies:
        assert not level.static_solid(*enemy.at(0))
    for mover in level.movers:
        for cell in mover.occupied(0):
            assert not level.static_solid(*cell)


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_no_level_leans_on_more_crumbling_tiles_than_the_solver_allows(level):
    assert len(level.crumble) <= 4


def test_every_mechanic_appears_in_at_least_one_level():
    """A mechanic no level uses is a mechanic nobody has ever seen work."""
    used = {
        "movers": any(level.movers for level in LEVELS),
        "enemies": any(level.enemies for level in LEVELS),
        "bounce": any(level.bounce for level in LEVELS),
        "ice": any(level.ice for level in LEVELS),
        "conveyors": any(level.conveyors for level in LEVELS),
        "crumble": any(level.crumble for level in LEVELS),
        "portals": any(level.portals for level in LEVELS),
    }

    assert all(used.values()), f"never used: {[k for k, v in used.items() if not v]}"
