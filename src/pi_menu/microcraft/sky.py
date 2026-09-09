"""Day, night, and what hangs in the sky.

A full day takes forty minutes of real time for a player who stays put.
Because the world loops, where you stand shifts your local time the way
time zones do, so the far side of the loop is having the opposite time
of day. The moon follows the real synodic month against a known new
moon, so its phase is the phase outside the window right now.
"""

from __future__ import annotations

import math
import random
from typing import Optional

from ..display.protocol import HEIGHT, WIDTH
from .canvas import Canvas, Colour, hex_colour, lerp_colour
from .noise import WORLD_PERIOD, WORLD_RADIUS, wrap_x

VIEW = WIDTH

DAY_LENGTH_MS = 40 * 60 * 1000

SYNODIC_MONTH_DAYS = 29.530588853
#: 2000-01-06 18:14 UTC, a real new moon, as a Unix time in seconds.
KNOWN_NEW_MOON_S = 947182440

#: ``(fraction of the day, top colour, bottom colour)``, looped.
SKY_KEYFRAMES = tuple(
    (frac, hex_colour(top), hex_colour(bottom))
    for frac, top, bottom in (
        (0.00, "#03040a", "#050814"),
        (0.20, "#0a0c1c", "#141633"),
        (0.24, "#241a3d", "#3d2a52"),
        (0.27, "#4a2c52", "#c65a3a"),
        (0.32, "#5f77a8", "#e8935a"),
        (0.40, "#5c94fc", "#8bb7ff"),
        (0.50, "#4f8bfa", "#7fadfb"),
        (0.60, "#5c94fc", "#8bb7ff"),
        (0.68, "#5f77a8", "#e8935a"),
        (0.73, "#4a2c52", "#c65a3a"),
        (0.76, "#241a3d", "#3d2a52"),
        (0.80, "#0a0c1c", "#141633"),
        (1.00, "#03040a", "#050814"),
    )
)

STAR_COUNT = 18

MOON_LIT = (255, 255, 255)
ECLIPSE_CORONA = hex_colour("#fffbec")
MOON_DARK = hex_colour("#404040")
SUN = hex_colour("#fffde0")
GLOW = (255, 90, 50)

#: The five pixels of a plus, and the order they light as the moon waxes
#: or wanes. The centre comes second so a partial phase reads as one
#: crescent rather than two dots.
PLUS_OFFSETS = {"top": (0, -1), "left": (-1, 0), "right": (1, 0), "bottom": (0, 1), "center": (0, 0)}
MOON_WAX_ORDER = ("right", "center", "top", "bottom", "left")
MOON_WANE_ORDER = ("left", "center", "top", "bottom", "right")

ECLIPSE_SKY_DARKEN = 0.82
ECLIPSE_SKY = hex_colour("#0c0e1a")


# -- time --------------------------------------------------------------------


def moon_phase_frac(now_s: float) -> float:
    """0 at new moon, 0.5 at full, from a Unix time in seconds."""
    days = (now_s - KNOWN_NEW_MOON_S) / 86400.0
    return ((days % SYNODIC_MONTH_DAYS) / SYNODIC_MONTH_DAYS + 1) % 1


def moon_illumination(phase: float) -> float:
    """The lit fraction of the disc, 0..1."""
    return (1 - math.cos(phase * math.pi * 2)) / 2


class DayClock:
    """Turns a monotonic clock into a local time of day for any column."""

    def __init__(self, start_ms: float = 0.0) -> None:
        self.cycle_start_ms = start_ms

    def local_day_frac(self, world_x: float, now_ms: float) -> float:
        """0 midnight, 0.25 sunrise, 0.5 noon, 0.75 sunset."""
        base = ((now_ms - self.cycle_start_ms) / DAY_LENGTH_MS) % 1
        zone = (wrap_x(world_x) + WORLD_RADIUS) / WORLD_PERIOD
        return ((base + zone) % 1 + 1) % 1

    def anchor_noon(self, world_x: float, now_ms: float) -> None:
        """Re-anchor so that right now, at this column, it is noon."""
        zone = (wrap_x(world_x) + WORLD_RADIUS) / WORLD_PERIOD
        target_base = ((0.5 - zone) % 1 + 1) % 1
        self.cycle_start_ms = now_ms - target_base * DAY_LENGTH_MS


# -- colours and positions -----------------------------------------------------


def sky_colours_at(frac: float) -> tuple[Colour, Colour]:
    for i in range(len(SKY_KEYFRAMES) - 1):
        t0, top0, bot0 = SKY_KEYFRAMES[i]
        t1, top1, bot1 = SKY_KEYFRAMES[i + 1]
        if t0 <= frac <= t1:
            t = (frac - t0) / ((t1 - t0) or 1)
            return lerp_colour(top0, top1, t), lerp_colour(bot0, bot1, t)
    last = SKY_KEYFRAMES[-1]
    return last[1], last[2]


def position_on_arc(p: float) -> tuple[float, float, float]:
    """``(x, y, elevation)`` along a sine arc across the view; p 0..1
    runs horizon to horizon and the zenith is at 0.5."""
    x = p * (VIEW - 1)
    elevation = math.sin(max(0.0, min(1.0, p)) * math.pi)
    y = 1 + (1 - elevation) * (VIEW * 0.5 - 2)
    return x, y, elevation


def make_stars(rng: random.Random) -> list:
    """A fixed screen-space starfield, each star twinkling on its own."""
    return [
        {
            "x": math.floor(rng.random() * VIEW),
            "y": math.floor(rng.random() * (VIEW * 0.65)),
            "phase": rng.random() * math.pi * 2,
            "speed": 0.5 + rng.random() * 1.5,
        }
        for _ in range(STAR_COUNT)
    ]


# -- drawing -------------------------------------------------------------------


def _js_round(v: float) -> int:
    return math.floor(v + 0.5)


def draw_moon_disc(canvas: Canvas, cx: float, cy: float, phase: float, alpha: float = 1.0) -> None:
    lit_count = _js_round(moon_illumination(phase) * 5)
    order = MOON_WAX_ORDER if phase < 0.5 else MOON_WANE_ORDER
    x, y = _js_round(cx), _js_round(cy)
    for key in order[:lit_count]:
        ox, oy = PLUS_OFFSETS[key]
        canvas.set(x + ox, y + oy, MOON_LIT, alpha)


def draw_eclipse(canvas: Canvas, cx: float, cy: float, alpha: float = 1.0) -> None:
    """The moon's dark disc dead centre on the sun, corona around it."""
    x, y = _js_round(cx), _js_round(cy)
    for key in ("top", "left", "right", "bottom"):
        ox, oy = PLUS_OFFSETS[key]
        canvas.set(x + ox, y + oy, ECLIPSE_CORONA, alpha)
    canvas.set(x, y, MOON_DARK, alpha)


def is_eclipse(frac: float, moon_phase: float) -> bool:
    is_day = 0.25 < frac < 0.75
    sun_visible = is_day and 0.32 < frac < 0.68
    near_new = moon_phase < 0.03 or moon_phase > 0.97
    return sun_visible and near_new


def draw_sky(
    canvas: Canvas,
    frac: float,
    moon_phase: float,
    stars: list,
    twinkle_s: float,
    visibility: float = 1.0,
) -> None:
    """The gradient, then the sun or the moon and stars, for a time of day.

    ``visibility`` fades every celestial body -- cloud cover hides them
    before it tints the sky.
    """
    is_day = 0.25 < frac < 0.75
    sun_visible = is_day and 0.32 < frac < 0.68
    near_new = moon_phase < 0.03 or moon_phase > 0.97
    in_eclipse = is_day and sun_visible and near_new

    top, bottom = sky_colours_at(frac)
    if in_eclipse:
        top = lerp_colour(top, ECLIPSE_SKY, ECLIPSE_SKY_DARKEN)
        bottom = lerp_colour(bottom, ECLIPSE_SKY, ECLIPSE_SKY_DARKEN)
    canvas.vertical_gradient(top, bottom)

    if visibility <= 0.01:
        return  # socked in: sun, moon and stars stay behind the deck

    # The moon's arc is offset from the sun's by its phase: full is up
    # all night, new tracks the sun, quarters sit half way between.
    moon_frac = (frac + moon_phase) % 1
    moon_up = 0.25 < moon_frac < 0.75

    if is_day:
        p = (frac - 0.25) / 0.5
        x, y, elevation = position_on_arc(p)
        warmth = 1 - elevation
        if warmth > 0.15:
            glow_alpha = min(0.55, (warmth - 0.15) * 0.9) * visibility
            canvas.radial(
                x, y, 9, GLOW, lambda t: glow_alpha * (1 - t), clip_to_disc=False
            )
        if sun_visible:
            if near_new:
                draw_eclipse(canvas, x, y, visibility)
            else:
                canvas.set(_js_round(x), _js_round(y), SUN, visibility)
        if moon_up and not near_new:
            mx, my, _ = position_on_arc((moon_frac - 0.25) / 0.5)
            too_close = sun_visible and abs(mx - x) < 2 and abs(my - y) < 2
            if not too_close:
                draw_moon_disc(canvas, mx, my, moon_phase, visibility * 0.32)
    else:
        for star in stars:
            tw = 0.12 + 0.16 * (0.5 + 0.5 * math.sin(twinkle_s * star["speed"] + star["phase"]))
            canvas.set(star["x"], star["y"], MOON_LIT, tw * visibility)
        if moon_up:
            mx, my, _ = position_on_arc((moon_frac - 0.25) / 0.5)
            draw_moon_disc(canvas, mx, my, moon_phase, visibility)


__all__ = [
    "DAY_LENGTH_MS",
    "DayClock",
    "draw_eclipse",
    "draw_moon_disc",
    "draw_sky",
    "is_eclipse",
    "make_stars",
    "moon_illumination",
    "moon_phase_frac",
    "position_on_arc",
    "sky_colours_at",
]
