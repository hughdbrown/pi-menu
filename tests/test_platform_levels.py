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
    assert level.solid(*level.spawn) is False


@pytest.mark.parametrize("level", LEVELS, ids=IDS)
def test_no_level_buries_its_goal_in_a_wall(level):
    assert level.solid(*level.goal) is False


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
