"""The canvas blends the way a browser canvas does, and the sky keeps time."""

from __future__ import annotations

import datetime
import math
import random

import pytest

from pi_menu.display.protocol import FRAME_BYTES, pixel_offset
from pi_menu.microcraft import sky
from pi_menu.microcraft.canvas import Canvas, hex_colour, lerp_colour
from pi_menu.microcraft.noise import WORLD_RADIUS

# -- canvas ------------------------------------------------------------------


def test_a_fresh_canvas_is_black_and_the_right_size():
    frame = Canvas().to_bytes()
    assert len(frame) == FRAME_BYTES
    assert set(frame) == {0}


def test_an_opaque_pixel_replaces_and_a_translucent_one_blends():
    c = Canvas()
    c.set(3, 4, (255, 255, 255))
    assert c.get(3, 4) == (255, 255, 255)
    c.set(5, 5, (255, 255, 255), 0.5)
    assert c.get(5, 5) == (128, 128, 128)
    c.set(5, 5, (0, 0, 0), 0.5)
    assert c.get(5, 5) == (64, 64, 64)


def test_drawing_off_the_edge_is_ignored():
    c = Canvas()
    c.set(-1, 0, (255, 0, 0))
    c.set(16, 0, (255, 0, 0))
    c.rect(14, 14, 5, 5, (0, 255, 0))
    assert set(c.to_bytes()[: pixel_offset(14, 14)]) == {0}
    assert c.get(15, 15) == (0, 255, 0)


def test_to_bytes_lands_on_the_panel_layout():
    c = Canvas()
    c.set(2, 1, (10, 20, 30))
    frame = c.to_bytes()
    off = pixel_offset(2, 1)
    assert frame[off : off + 3] == bytes((10, 20, 30))


def test_invert_flips_a_pixel_and_flips_it_back():
    c = Canvas((10, 200, 55))
    c.invert(0, 0)
    assert c.get(0, 0) == (245, 55, 200)
    c.invert(0, 0)
    assert c.get(0, 0) == (10, 200, 55)


def test_a_vertical_gradient_runs_top_to_bottom():
    c = Canvas()
    c.vertical_gradient((0, 0, 0), (0, 0, 255))
    assert c.get(0, 0)[2] < c.get(0, 8)[2] < c.get(0, 15)[2]
    assert c.get(0, 15)[2] == 247  # row centre, not row edge: 15.5/16 * 255


def test_a_tile_honours_transparency_and_mirroring():
    sheet = (
        ((1, 1, 1), None),
        ((2, 2, 2), (3, 3, 3)),
    )
    c = Canvas((9, 9, 9))
    c.tile(sheet, 0, 0, 0, 0)
    assert c.get(0, 0) == (1, 1, 1) and c.get(1, 0) == (9, 9, 9)
    assert c.get(0, 1) == (2, 2, 2) and c.get(1, 1) == (3, 3, 3)
    c.tile(sheet, 0, 0, 4, 0, mirrored=True)
    assert c.get(5, 0) == (1, 1, 1) and c.get(4, 0) == (9, 9, 9)
    assert c.get(4, 1) == (3, 3, 3)


def test_a_radial_blob_is_strongest_at_its_centre_and_gone_at_the_rim():
    c = Canvas()
    c.radial(8.5, 8.5, 4, (255, 255, 255), lambda t: 1 - t)
    assert c.get(8, 8) == (255, 255, 255)
    assert c.get(8, 8) > c.get(8, 6) > c.get(8, 5)
    assert c.get(8, 12) == (0, 0, 0)  # 3.5 px away, alpha 0.125 -> 32... clipped rim
    assert c.get(0, 0) == (0, 0, 0)


def test_an_unclipped_radial_fills_the_whole_canvas_with_its_last_stop():
    c = Canvas()
    c.radial(2, 2, 3, (255, 0, 0), lambda t: 0.5 if t >= 1 else 0.0, clip_to_disc=False)
    assert c.get(15, 15) == (128, 0, 0)


def test_a_line_touches_every_column_it_crosses():
    c = Canvas()
    c.line(0, 0, 7, 3, (255, 255, 255), 1.0)
    lit_columns = {x for x in range(8) if any(c.get(x, y) != (0, 0, 0) for y in range(4))}
    assert lit_columns == set(range(8))


def test_colour_helpers_match_the_html():
    assert hex_colour("#5c94fc") == (92, 148, 252)
    assert lerp_colour((0, 0, 0), (255, 255, 255), 0.5) == (128, 128, 128)  # rounds


# -- time --------------------------------------------------------------------


def unix(year, month, day, hour=0, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc).timestamp()


def test_the_reference_new_moon_is_a_new_moon():
    assert sky.moon_phase_frac(unix(2000, 1, 6, 18, 14)) == pytest.approx(0.0, abs=1e-9)


def test_a_known_full_moon_is_full():
    # 2024-04-23 23:49 UTC was a full moon.
    assert sky.moon_phase_frac(unix(2024, 4, 23, 23, 49)) == pytest.approx(0.5, abs=0.01)


def test_illumination_is_dark_at_new_and_full_at_full():
    assert sky.moon_illumination(0.0) == pytest.approx(0.0)
    assert sky.moon_illumination(0.5) == pytest.approx(1.0)
    assert sky.moon_illumination(0.25) == pytest.approx(0.5)


def test_the_day_clock_runs_forty_minutes_and_wraps():
    clock = sky.DayClock(start_ms=0)
    assert clock.local_day_frac(-WORLD_RADIUS, 0) == pytest.approx(0.0)
    assert clock.local_day_frac(-WORLD_RADIUS, sky.DAY_LENGTH_MS / 2) == pytest.approx(0.5)
    assert clock.local_day_frac(-WORLD_RADIUS, sky.DAY_LENGTH_MS) == pytest.approx(0.0)


def test_the_far_side_of_the_world_has_the_opposite_time_of_day():
    clock = sky.DayClock(start_ms=0)
    here = clock.local_day_frac(100, 1234)
    there = clock.local_day_frac(100 + WORLD_RADIUS, 1234)
    assert (there - here) % 1 == pytest.approx(0.5)


def test_anchoring_noon_makes_it_noon_here_and_now():
    clock = sky.DayClock()
    clock.anchor_noon(-321, 98765)
    assert clock.local_day_frac(-321, 98765) == pytest.approx(0.5)
    assert clock.local_day_frac(-321, 98765 + sky.DAY_LENGTH_MS / 4) == pytest.approx(0.75)


# -- colours -----------------------------------------------------------------


def test_noon_is_blue_and_midnight_is_nearly_black():
    top, bottom = sky.sky_colours_at(0.5)
    assert top == (79, 139, 250) and bottom == (127, 173, 251)
    top, bottom = sky.sky_colours_at(0.0)
    assert max(top) < 20 and max(bottom) < 25


def test_dusk_is_warm_at_the_horizon():
    top, bottom = sky.sky_colours_at(0.73)
    assert bottom[0] > bottom[2]  # more red than blue low down
    assert top[2] > top[0] or top[0] < 100  # and darker, cooler above


def test_the_arc_rises_from_the_left_horizon_to_the_zenith():
    x0, y0, e0 = sky.position_on_arc(0)
    xm, ym, em = sky.position_on_arc(0.5)
    x1, y1, e1 = sky.position_on_arc(1)
    assert x0 == 0 and x1 == 15
    assert em == pytest.approx(1) and ym == 1
    assert y0 == pytest.approx(7) and y1 == pytest.approx(7)


# -- drawing -----------------------------------------------------------------


def lit_pixels(canvas: Canvas, colour) -> set:
    return {(x, y) for y in range(16) for x in range(16) if canvas.get(x, y) == colour}


@pytest.mark.parametrize(
    "phase, expected",
    # cos(pi/2) is a hair above zero in doubles, so the first quarter rounds
    # down to two pixels and the last quarter up to three, in JS as here.
    [(0.0, 0), (0.5, 5), (0.25, 2), (0.75, 3), (0.125, 1)],
)
def test_the_moon_lights_as_many_of_its_five_pixels_as_its_phase(phase, expected):
    c = Canvas()
    sky.draw_moon_disc(c, 8, 8, phase)
    assert len(lit_pixels(c, sky.MOON_LIT)) == expected


def test_a_waxing_moon_lights_its_right_side_first():
    c = Canvas()
    sky.draw_moon_disc(c, 8, 8, 0.125)
    assert lit_pixels(c, sky.MOON_LIT) == {(9, 8)}
    c = Canvas()
    sky.draw_moon_disc(c, 8, 8, 0.875)
    assert lit_pixels(c, sky.MOON_LIT) == {(7, 8)}


def test_an_eclipse_is_a_dark_centre_in_a_corona():
    c = Canvas()
    sky.draw_eclipse(c, 8, 8)
    assert c.get(8, 8) == sky.MOON_DARK
    assert lit_pixels(c, sky.ECLIPSE_CORONA) == {(8, 7), (7, 8), (9, 8), (8, 9)}


def test_noon_draws_a_sun_and_no_stars():
    c = Canvas()
    sky.draw_sky(c, 0.5, 0.5, sky.make_stars(random.Random(1)), 0.0)
    assert c.get(7, 1) == sky.SUN or c.get(8, 1) == sky.SUN
    assert c.get(0, 15)[2] > 200  # blue at the bottom


def test_midnight_draws_a_full_moon_high_and_the_stars_dim():
    c = Canvas()
    stars = sky.make_stars(random.Random(1))
    sky.draw_sky(c, 0.0, 0.5, stars, 0.0)
    assert len(lit_pixels(c, sky.MOON_LIT)) == 5
    star = stars[0]
    r, g, b = c.get(star["x"], star["y"])
    assert 0 < r < 100 or (star["x"], star["y"]) in lit_pixels(c, sky.MOON_LIT)


def test_a_new_moon_at_noon_is_a_total_eclipse():
    c = Canvas()
    sky.draw_sky(c, 0.5, 0.0, [], 0.0)
    assert sky.is_eclipse(0.5, 0.0)
    assert c.get(8, 1) == sky.MOON_DARK or c.get(7, 1) == sky.MOON_DARK
    plain = Canvas()
    sky.draw_sky(plain, 0.5, 0.5, [], 0.0)
    assert sum(c.get(0, 15)) < sum(plain.get(0, 15))  # darkened sky


def test_sunrise_has_a_warm_glow_but_no_sun_yet():
    c = Canvas()
    sky.draw_sky(c, 0.27, 0.5, [], 0.0)
    assert not lit_pixels(c, sky.SUN)
    r, g, b = c.get(1, 6)
    assert r > b  # the glow reddens the horizon near the rising sun


def test_full_cover_hides_everything_but_the_gradient():
    covered, clear = Canvas(), Canvas()
    stars = sky.make_stars(random.Random(2))
    sky.draw_sky(covered, 0.0, 0.5, stars, 0.0, visibility=0.0)
    sky.draw_sky(clear, 0.0, 0.5, stars, 0.0, visibility=1.0)
    assert not lit_pixels(covered, sky.MOON_LIT)
    assert lit_pixels(clear, sky.MOON_LIT)


def test_the_starfield_stays_in_the_upper_sky():
    stars = sky.make_stars(random.Random(3))
    assert len(stars) == sky.STAR_COUNT
    assert all(0 <= s["x"] < 16 and 0 <= s["y"] <= 10 for s in stars)
