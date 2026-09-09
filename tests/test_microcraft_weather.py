"""Clouds drift and recycle, rain falls where it should, waves follow depth."""

from __future__ import annotations

import math
import random

import pytest

from pi_menu.microcraft import palette, tiles, weather
from pi_menu.microcraft.canvas import Canvas
from pi_menu.microcraft.terrain import FRONT, SEA_LEVEL, World
from pi_menu.microcraft.weather import (
    CLOUD_MAX_Y,
    CLOUD_MIN_Y,
    WEATHER_RADIUS,
    Weather,
    make_cloud,
)


@pytest.fixture
def world():
    return World(11)


@pytest.fixture
def wx(world):
    return Weather(world, random.Random(5), player_x=0.0)


def storm(x: float, rng=None) -> weather.Cloud:
    return make_cloud(x, rng or random.Random(1), {"force_type": "cumulonimbus"})


def puff(x: float, rng=None) -> weather.Cloud:
    return make_cloud(x, rng or random.Random(2), {"force_type": "cumulus"})


# -- clouds ----------------------------------------------------------------


def test_each_type_has_the_shape_it_is_meant_to():
    rng = random.Random(3)
    cumulus = weather.sculpt_anchors("cumulus", rng)
    sheet = weather.sculpt_anchors("stratonimbus", rng)
    tower = weather.sculpt_anchors("cumulonimbus", rng)
    assert 8 <= len(cumulus) <= 11
    assert 20 <= len(sheet) <= 28
    assert len(tower) > len(sheet)
    # The storm tower is far taller than the flat sheet.
    height = lambda anchors: max(a[1] for a in anchors) - min(a[1] for a in anchors)
    assert height(tower) > 2 * height(sheet)
    assert weather.cloud_width_of(sheet) > weather.cloud_width_of(cumulus)


def test_a_cloud_is_a_swarm_bound_to_its_anchors():
    cloud = puff(0)
    assert len(cloud.particles) >= 5 * len(cloud.anchors)
    anchor_points = {(round(a[0], 6), round(a[1], 6)) for a in cloud.anchors}
    for p in cloud.particles:
        assert (round(p.ax, 6), round(p.ay, 6)) in anchor_points
        assert 0 < p.alpha <= 0.9
    assert CLOUD_MIN_Y <= cloud.y <= CLOUD_MAX_Y


def test_rain_clouds_are_slow_and_mini_clouds_are_harmless():
    assert storm(0).speed == pytest.approx(weather.WIND_SPEED * 0.2)
    assert puff(0).speed == pytest.approx(weather.WIND_SPEED)
    mini = make_cloud(0, random.Random(4), weather.mini_cloud_opts(random.Random(4)))
    assert mini.mini and mini.cover == 0 and mini.rain_rate == 0
    assert mini.width < puff(0).width


def test_the_type_roll_follows_the_weights():
    rng = random.Random(8)
    picks = [weather.pick_cloud_type(rng) for _ in range(3000)]
    assert 0.68 < picks.count("cumulus") / 3000 < 0.80
    assert 0.03 < picks.count("cumulonimbus") / 3000 < 0.11


def test_seeded_clouds_span_the_window_without_overlapping(wx):
    clouds = sorted(wx.clouds, key=lambda c: c.x)
    assert clouds[0].x - clouds[0].width / 2 <= -WEATHER_RADIUS + 1
    assert clouds[-1].x + clouds[-1].width / 2 >= WEATHER_RADIUS - weather.CLOUD_GAP_MAX * 5
    for a, b in zip(clouds, clouds[1:]):
        assert b.x - b.width / 2 >= a.x + a.width / 2 + weather.CLOUD_GAP_MIN - 1e-6
    assert len(wx.mini_clouds) > len(wx.clouds)


def test_the_wind_carries_every_cloud_east(wx):
    before = [c.x for c in wx.clouds]
    wx.update_motion(1000, camera_x=0)
    assert all(after > b for after, b in zip((c.x for c in wx.clouds), before))


def test_particles_only_wobble_near_the_camera(wx):
    near = min(wx.clouds, key=lambda c: abs(c.x))
    far = max(wx.clouds, key=lambda c: abs(c.x))
    near_before = [(p.ox, p.oy) for p in near.particles]
    far_before = [(p.ox, p.oy) for p in far.particles]
    for _ in range(10):
        wx.update_motion(50, camera_x=0)
    assert [(p.ox, p.oy) for p in near.particles] != near_before
    assert [(p.ox, p.oy) for p in far.particles] == far_before


def test_a_cloud_that_drifts_out_of_range_comes_back_behind_the_rest(wx):
    gone = wx.clouds[0]
    gone.x = WEATHER_RADIUS + gone.width + 5
    leftmost = min(c.x - c.width / 2 for c in wx.clouds[1:])
    wx.tick(player_x=0)
    fresh = wx.clouds[0]
    assert fresh is not gone
    assert fresh.x + fresh.width / 2 <= min(leftmost - weather.CLOUD_GAP_MIN, -WEATHER_RADIUS) + 1e-6


# -- cover and rain --------------------------------------------------------


def test_cover_and_rain_are_read_off_the_clouds_overhead(wx):
    wx.clouds = [storm(0), puff(200)]
    assert wx.cloud_cover_at(0) == pytest.approx(0.95)
    assert wx.cloud_cover_at(200) == pytest.approx(0.3)
    assert wx.storm_cover_at(200) == 0
    assert wx.rain_intensity_at(0) == 1.0
    assert wx.rain_intensity_at(200) == 0
    assert wx.rain_intensity_at(500) == 0
    assert wx.cloud_bottom_at(0) == pytest.approx(wx.clouds[0].y + wx.clouds[0].bottom)
    assert wx.cloud_bottom_at(500) == CLOUD_MAX_Y


def test_cover_fades_toward_a_cloud_s_edge(wx):
    wx.clouds = [puff(0)]
    half = wx.clouds[0].width / 2
    assert wx.cloud_cover_at(0) > wx.cloud_cover_at(half * 0.8) > 0
    assert wx.cloud_cover_at(half + 1) == 0


def test_the_overcast_tint_eases_and_hides_the_sun(wx):
    wx.clouds = [storm(0)]
    assert wx.celestial_visibility == 1.0
    for _ in range(200):
        wx.settle_overcast(0)
    assert wx.sky_overcast == pytest.approx(0.95, abs=0.01)
    assert wx.celestial_visibility == 0.0


def test_rain_spawns_only_under_raining_clouds_and_respects_the_cap(world):
    wx = Weather(world, random.Random(1), 0.0)
    wx.clouds = [storm(0)]
    for _ in range(6):
        wx.spawn_rain(0, CLOUD_MAX_Y + 40)
    assert wx.drops
    assert all(-weather.RAIN_SIM_RADIUS <= d.col < weather.RAIN_SIM_RADIUS for d in wx.drops)
    per_column = {}
    for d in wx.drops:
        per_column[d.col] = per_column.get(d.col, 0) + 1
    assert max(per_column.values()) <= weather.RAIN_MAX_PER_COLUMN
    assert all(d.y >= wx.clouds[0].y + wx.clouds[0].bottom for d in wx.drops)

    wx.clouds = [puff(0)]
    wx.drops = []
    for _ in range(6):
        wx.spawn_rain(0, CLOUD_MAX_Y + 40)
    assert not wx.drops


def test_a_drop_falls_and_rests_on_the_first_solid_row(world):
    wx = Weather(world, random.Random(1), 0.0)
    x = world.gen.find_spawn_x()
    while world.gen.is_water_column(x):
        x += 1
    surf = world.gen.front_height(x)
    drop = weather.Drop(x + 0.5, surf - 3.0, x, weather.RAIN_FALL_SPEED)
    wx.drops = [drop]
    for _ in range(40):
        wx.update_rain(50, x, surf - 1, 0.0)
        if drop.landed:
            break
    assert drop.landed and drop.y == surf - 1
    wx.update_rain(50, x, surf - 1, 0.0)
    assert not wx.drops  # gone after its one frame on the ground


def test_a_drop_far_from_the_player_is_forgotten(world):
    wx = Weather(world, random.Random(1), 0.0)
    wx.drops = [weather.Drop(100.5, 100.0, 100, weather.RAIN_FALL_SPEED)]
    wx.update_rain(50, 0, 100, 0.0)
    assert not wx.drops


# -- lightning -------------------------------------------------------------


def test_only_thunderheads_strike_and_the_flash_needs_the_player_under_them(world):
    wx = Weather(world, random.Random(1), 0.0)
    wx.clouds = [make_cloud(0, random.Random(1), {"force_type": "stratonimbus"})]
    for _ in range(400):
        wx.update_lightning(50, 0, CLOUD_MAX_Y + 40)
    assert not wx.bolts and wx.screen_flash == 0

    wx.clouds = [storm(0)]
    wx.strike(wx.clouds[0], 0, CLOUD_MAX_Y + 40)
    assert wx.bolts and wx.screen_flash >= 0.8
    bolt = wx.bolts[0]
    assert bolt.points[0][0] == 0 and bolt.points[-1][0] == 0
    assert bolt.points[-1][1] == world.gen.front_height(bolt.x)

    wx.screen_flash = 0
    wx.strike(wx.clouds[0], 0, CLOUD_MIN_Y - 20)  # up a mountain, above the deck
    assert wx.screen_flash == 0

    wx.update_lightning(weather.LIGHTNING_BOLT_TTL + 1, 0, CLOUD_MAX_Y + 40)
    assert not wx.bolts


def test_the_flash_decays(world):
    wx = Weather(world, random.Random(1), 0.0)
    wx.clouds = []
    wx.screen_flash = 1.0
    wx.update_lightning(100, 0, 300)
    assert wx.screen_flash == pytest.approx(1 - 0.32)
    wx.update_lightning(1000, 0, 300)
    assert wx.screen_flash == 0


# -- waves -----------------------------------------------------------------


def test_waves_are_flat_in_the_shallows_and_swell_out_at_sea(wx, world):
    gen = world.gen
    deep = next(x for x in range(-1000, 1000) if gen.ocean_factor(x) >= 1 and wx.ocean_depth_at(x) >= 8)
    assert wx.max_wave_height_at(deep) >= 3
    shore = next(x for x in range(-1000, 1000) if 0 < wx.ocean_depth_at(x) <= 2)
    assert wx.max_wave_height_at(shore) == 0
    assert wx.extra_swim_blocks_at(deep) >= 1


def test_lakes_are_capped_to_a_ripple(wx, world):
    gen = world.gen
    lakes = [x for x in range(-1000, 1000) if gen.ocean_factor(x) == 0 and gen.is_water_column(x)]
    if not lakes:
        pytest.skip("no inland lake in this seed")
    assert all(wx.max_wave_height_at(x) <= weather.LAKE_MAX_WAVE_PX for x in lakes)


def test_a_storm_whips_the_sea_up(wx, world):
    gen = world.gen
    deep = next(x for x in range(-1000, 1000) if gen.ocean_factor(x) >= 1 and wx.ocean_depth_at(x) >= 8)
    wx.clouds = []
    calm = wx.weather_wave_factor_at(deep)
    wx.clouds = [storm(deep)]
    assert wx.weather_wave_factor_at(deep) > calm


def test_a_tall_crest_is_swimmable_and_a_trough_is_not(wx, world):
    gen = world.gen
    deep = next(x for x in range(-1000, 1000) if gen.ocean_factor(x) >= 1 and wx.ocean_depth_at(x) >= 8)
    assert world.is_open_water_surface(deep, SEA_LEVEL)
    assert wx.fluid_or_wave_at(deep, SEA_LEVEL, 0.0)  # water itself
    over = [wx.fluid_or_wave_at(deep, SEA_LEVEL - 1, t / 10) for t in range(100)]
    assert any(over) and not all(over)
    assert not wx.fluid_or_wave_at(deep, SEA_LEVEL - 4, 0.0)


# -- drawing ---------------------------------------------------------------


def test_clouds_paint_pale_pixels_where_they_are_and_nowhere_else(wx):
    cloud = puff(0)
    wx.clouds, wx.mini_clouds = [cloud], []
    canvas = Canvas()
    wx.draw_clouds(canvas, cam_x=-4, cam_y=cloud.y - 4)
    painted = [(x, y) for y in range(16) for x in range(16) if canvas.get(x, y) != (0, 0, 0)]
    assert painted
    r, g, b = max((canvas.get(x, y) for x, y in painted), key=sum)
    assert b >= g >= r  # the cloud colour, dimmed by alpha, stays cool white
    empty = Canvas()
    wx.draw_clouds(empty, cam_x=500, cam_y=cloud.y)
    assert empty.to_bytes() == Canvas().to_bytes()


def test_rain_is_a_blue_pixel_and_a_bolt_reaches_the_ground(wx):
    wx.drops = [weather.Drop(3.5, 4.0, 3, 9.0)]
    canvas = Canvas()
    wx.draw_rain(canvas, 0, 0)
    assert canvas.get(7, 8) == weather.RAIN_COLOUR

    wx.bolts = [weather.Bolt(4, [(0.0, 0.0), (0.5, 4.0), (0.0, 7.5)], weather.LIGHTNING_BOLT_TTL)]
    canvas = Canvas()
    wx.draw_bolts(canvas, 0, 0)
    assert canvas.get(8, 0) == weather.BOLT_COLOUR
    assert any(canvas.get(x, 15) != (0, 0, 0) for x in range(6, 11))


def test_the_flash_and_the_overcast_tint_wash_the_whole_frame(wx):
    canvas = Canvas()
    wx.screen_flash = 1.0
    wx.draw_flash(canvas)
    assert canvas.get(0, 0) == canvas.get(15, 15) != (0, 0, 0)

    canvas = Canvas((255, 255, 255))
    wx.sky_overcast = 1.0
    wx.draw_overcast(canvas, below_clouds=False)
    assert canvas.get(0, 0) == (255, 255, 255)
    wx.draw_overcast(canvas, below_clouds=True)
    assert canvas.get(0, 0) < (255, 255, 255)


def test_waves_are_drawn_from_the_water_tile_s_own_pixels(wx, world):
    gen = world.gen
    deep = next(x for x in range(-1000, 1000) if gen.ocean_factor(x) >= 1 and wx.ocean_depth_at(x) >= 8)
    canvas = Canvas()
    cam_x, cam_y = deep - 4, SEA_LEVEL - 4
    crests = set()
    for t in range(40):
        canvas = Canvas()
        wx.draw_waves(canvas, cam_x, cam_y, t / 4)
        for x in range(16):
            for y in range(8):
                if canvas.get(x, y) != (0, 0, 0):
                    crests.add(canvas.get(x, y))
    water_top = {palette.tile_art(tiles.WATER)[0][2][2], palette.tile_art(tiles.WATER)[0][2][3]}
    assert crests and all(c in water_top or c[0] > 0 for c in crests)
