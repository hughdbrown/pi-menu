"""The boss fights: a demon behind the arena, throwing things at you.

There is no health bar. The demon runs a fixed number of waves and then
withdraws, and surviving that is what opens the goal. So what these
check is that the fight starts when it should, that everything it throws
can kill, that it ends, and that the goal stays shut until it does.
"""

from __future__ import annotations

import pytest

from pi_menu.platformer import bosses
from pi_menu.platformer.bosses import BALROG, BOSSES, IMP, MOLOCH, WYRM
from pi_menu.platformer.level import Level, LevelError
from pi_menu.platformer.world import RIGHT, Event, World

WIDE = 48


def arena(boss=IMP, boss_at=(30, 4), spawn_x=2) -> Level:
    """A long flat level with the demon at the far end."""
    rows = ["." * WIDE for _ in range(16)]
    row13 = ["."] * WIDE
    row13[spawn_x] = "@"
    row13[WIDE - 2] = "G"
    rows[13] = "".join(row13)
    rows[14] = "=" * WIDE
    rows[15] = "=" * WIDE
    if boss_at is not None:
        row = list(rows[boss_at[1]])
        row[boss_at[0]] = "B"
        rows[boss_at[1]] = "".join(row)
    return Level("arena", rows, boss=boss)


def run(world, ticks, held=frozenset()):
    return [world.step(held) for _ in range(ticks)]


def settle(world):
    for _ in range(200):
        if world.on_ground:
            return
        world.step(frozenset())
    raise AssertionError("the player never landed")


# -- the shape of a fight ------------------------------------------------


@pytest.mark.parametrize("boss", BOSSES, ids=[b.name for b in BOSSES])
def test_every_demon_has_waves_that_end(boss):
    assert boss.waves
    assert boss.duration == sum(wave.ticks for wave in boss.waves)


@pytest.mark.parametrize("boss", BOSSES, ids=[b.name for b in BOSSES])
def test_every_tick_of_a_fight_belongs_to_a_wave(boss):
    for tick in range(boss.duration):
        wave, within = boss.wave_at(tick)
        assert 0 <= within < wave.ticks


@pytest.mark.parametrize("boss", BOSSES, ids=[b.name for b in BOSSES])
def test_every_demon_throws_something(boss):
    assert any(wave.fireballs for wave in boss.waves)


@pytest.mark.parametrize("boss", BOSSES, ids=[b.name for b in BOSSES])
def test_a_fireball_is_always_thrown_early_enough_to_arrive(boss):
    for wave in boss.waves:
        for ball in wave.fireballs:
            assert ball.offset < wave.ticks, f"{boss.name}: thrown after the wave"


def test_the_demons_differ_in_what_they_throw():
    """Variety is the point: the fists are the same everywhere."""
    signatures = {
        boss.name: tuple(
            sorted((ball.row, ball.speed) for wave in boss.waves for ball in wave.fireballs)
        )
        for boss in BOSSES
    }

    assert len(set(signatures.values())) == len(BOSSES)


def test_the_demons_get_harder_in_play_order():
    order = [IMP, WYRM, MOLOCH, BALROG]
    counts = [sum(len(wave.fireballs) for wave in boss.waves) for boss in order]

    assert counts == sorted(counts)
    assert [boss.duration for boss in order] == sorted(boss.duration for boss in order)


# -- starting and ending -------------------------------------------------


def test_the_fight_does_not_start_until_you_reach_the_arena():
    world = World(arena())
    settle(world)

    assert world.boss_fighting is False
    assert world.boss_done is False


def test_walking_into_the_arena_starts_the_fight():
    world = World(arena())
    settle(world)
    world.x = float(world.level.boss_origin[0] - bosses.ARENA_LEAD)

    world.step(frozenset())

    assert world.boss_fighting is True


def test_the_demon_withdraws_when_its_last_wave_is_over():
    world = World(arena())
    settle(world)
    world.x = float(world.level.boss_origin[0] - bosses.ARENA_LEAD)
    world.step(frozenset())

    for _ in range(IMP.duration + 2):
        world.step(frozenset())
        world.alive = True  # ignore the beating; this is about the clock

    assert world.boss_done is True
    assert world.boss_fighting is False


def test_the_goal_stays_shut_while_the_demon_is_up():
    world = World(arena())
    settle(world)

    assert world.goal_open is False, "no coins here, so only the demon holds it shut"

    world.boss_done = True

    assert world.goal_open is True


def test_a_level_without_a_boss_never_waits_for_one():
    rows = ["." * 20 for _ in range(16)]
    rows[13] = "..@.............G..."
    rows[14] = "=" * 20
    rows[15] = "=" * 20
    world = World(Level("plain", rows))

    assert world.boss_done is True
    assert world.goal_open is True


# -- what it throws ------------------------------------------------------


def _fight(boss=IMP):
    world = World(arena(boss=boss))
    settle(world)
    world.x = float(world.level.boss_origin[0] - bosses.ARENA_LEAD)
    world.step(frozenset())
    return world


def test_a_fist_comes_down_and_goes_back_up():
    world = _fight()
    heights = []
    for _ in range(bosses.FIST_TOTAL):
        world.step(frozenset())
        world.alive = True
        cells = world.fist_cells()
        if cells:
            heights.append(min(y for _, y in cells))

    assert heights, "no fist ever appeared"
    assert max(heights) > min(heights), "the fist never moved"


def test_a_fist_is_three_cells_wide():
    world = _fight()
    for _ in range(bosses.FIST_TOTAL):
        world.step(frozenset())
        world.alive = True
        cells = world.fist_cells()
        if cells:
            assert len({x for x, _ in cells}) == bosses.FIST_WIDTH
            return
    pytest.fail("no fist ever appeared")


def test_a_fist_aims_at_where_the_player_is():
    """It aims once, when the fist launches -- not continuously."""
    world = _fight()

    for _ in range(IMP.waves[0].fist_period + 1):
        world.x = 26.0
        world.step(frozenset())
        world.alive = True

    assert abs(world.fist_aim - 26) <= bosses.AIM_STEP


def test_a_fist_already_falling_does_not_follow_you():
    world = _fight()
    for _ in range(IMP.waves[0].fist_period + 1):
        world.x = 26.0
        world.step(frozenset())
        world.alive = True
    aimed = world.fist_aim

    world.x = 20.0  # dodge while it is on its way down
    world.step(frozenset())

    assert world.fist_aim == aimed


def test_a_fist_aims_at_even_columns_only():
    """Halving where one can land halves what the solver must track."""
    world = _fight()
    for x in range(20, 34):
        world.x = float(x)
        for _ in range(bosses.FIST_TOTAL):
            world.step(frozenset())
            world.alive = True
        assert world.fist_aim % bosses.AIM_STEP == 0


def test_a_fist_kills():
    world = _fight()
    world.x = 26.0

    events = []
    for _ in range(bosses.FIST_TOTAL * 2):
        events.append(world.step(frozenset()))
        if not world.alive:
            break

    assert Event.DIED in events


def test_fireballs_cross_the_arena():
    world = _fight()
    seen = []
    for _ in range(IMP.waves[0].ticks):
        world.step(frozenset())
        world.alive = True
        seen.extend(world.fireball_cells())

    assert seen, "nothing was ever thrown"
    columns = [x for x, _ in seen]
    assert min(columns) < max(columns), "the fireball never travelled"


def test_a_fireball_travels_away_from_the_demon():
    world = _fight()
    positions = []
    for _ in range(IMP.waves[0].ticks):
        world.step(frozenset())
        world.alive = True
        for x, _y in world.fireball_cells():
            positions.append(x)

    assert positions[0] > positions[-1], "it flew into the demon"


def test_a_fireball_kills():
    world = _fight()
    world.x = 20.0
    world.y = 13.0

    events = []
    for _ in range(IMP.waves[0].ticks):
        world.y = 13.0  # stand still in its path
        events.append(world.step(frozenset()))
        if not world.alive:
            break

    assert Event.DIED in events


# -- what the solver has to tell apart -----------------------------------


def test_the_fight_shows_in_the_dynamic_key():
    world = _fight()
    before = world.dynamic_key()

    world.step(frozenset())

    assert world.dynamic_key() != before


def test_the_key_says_when_the_fight_is_over():
    world = _fight()
    during = world.dynamic_key()
    world.boss_done = True
    world.boss_tick = None

    assert world.dynamic_key() != during


# -- the map -------------------------------------------------------------


def test_a_boss_needs_room_on_the_map():
    with pytest.raises(LevelError, match="runs off the map"):
        arena(boss_at=(WIDE - 2, 4))


def test_the_demon_is_drawn_eight_by_eight():
    assert len(bosses.DEMON) == 8
    assert all(len(row) == 8 for row in bosses.DEMON)


def test_the_demon_has_eyes_and_a_mouth_inside_its_body():
    body = {
        (x, y)
        for y, row in enumerate(bosses.DEMON)
        for x, cell in enumerate(row)
        if cell == "#"
    }

    assert set(bosses.DEMON_EYES) <= body
    assert set(bosses.DEMON_MOUTH) <= body
