"""Clouds, rain, lightning and waves.

Clouds are swarms of free particles, each pulled only toward its own
slowly wandering anchor, so a cloud is a loose, living volume rather
than a drawn shape. A constant wind carries every cloud east; whatever
drifts out of the simulated window comes back in at the west edge as a
brand new cloud. Rain and cover are read off the clouds overhead, and
waves rise on open water in proportion to its depth and the weather.

Every random draw comes from the RNG the weather is given, so a seeded
run is repeatable.
"""

from __future__ import annotations

import math
import random
from typing import Optional

from ..display.protocol import HEIGHT, WIDTH
from .canvas import Canvas
from .noise import noise1d
from .terrain import SEA_LEVEL, SURFACE_BASE, WORLD_H, World
from . import palette, tiles

BLOCK = 2
COLS = WIDTH // BLOCK
ROWS = HEIGHT // BLOCK

WEATHER_RADIUS = 128

CLOUD_MIN_Y = SURFACE_BASE - 60
CLOUD_MAX_Y = SURFACE_BASE - 30

WIND_SPEED = 1.1  # blocks per second, always west to east

CLOUD_GAP_MIN, CLOUD_GAP_MAX = 16, 34
CLOUD_LONG_GAP_CHANCE = 0.22
CLOUD_LONG_GAP_MULT_MIN, CLOUD_LONG_GAP_MULT_MAX = 2.2, 4.5

CLOUD_TYPES = {
    "cumulus": {"weight": 0.74, "rain_rate": 0.0, "cover": 0.3},
    "stratonimbus": {"weight": 0.19, "rain_rate": 0.55, "cover": 0.65},
    "cumulonimbus": {"weight": 0.07, "rain_rate": 1.0, "cover": 0.95},
}
CLOUD_TYPE_NAMES = tuple(CLOUD_TYPES)

MINI_CLOUD_GAP_MIN, MINI_CLOUD_GAP_MAX = 5, 13
MINI_CLOUD_SCALE_MIN, MINI_CLOUD_SCALE_MAX = 0.2, 0.4
MINI_CLOUD_MIN_Y, MINI_CLOUD_MAX_Y = CLOUD_MIN_Y - 14, CLOUD_MAX_Y + 18
MINI_WIND_SPEED = WIND_SPEED * 1.3

CLOUD_COLOUR = (232, 236, 242)
GLOBAL_CLOUD_SCALE = 1.35

PARTICLE_ATTRACT_K = 1.6
PARTICLE_DAMPING = 0.90

#: Particles are only integrated for clouds this close to the camera;
#: the rest drift as a whole. A frozen swarm off screen looks the same.
PARTICLE_ACTIVE_RANGE = 40

LIGHTNING_CHANCE_PER_SEC = 0.05
LIGHTNING_FLASH_DECAY = 3.2
LIGHTNING_BOLT_TTL = 220  # ms
BOLT_COLOUR = (255, 255, 240)
FLASH_COLOUR = (235, 240, 255)

RAIN_SPAWN_MS = 160
RAIN_FALL_SPEED = 9  # blocks per second
RAIN_MAX_PER_COLUMN = 3
RAIN_SIM_RADIUS = 16
RAIN_COLOUR = (61, 120, 224)

OCEAN_BASELINE_WAVE_PX = 3
OCEAN_SHALLOW_DEPTH = 2
OCEAN_FULL_DEPTH = 8
LAKE_MAX_WAVE_PX = 1
WAVE_FOAM = (255, 255, 255)
WAVE_FOAM_ALPHA = 0.32

OVERCAST_TINT = (90, 92, 98)
STORM_TINT = (55, 58, 64)


class Particle:
    __slots__ = ("ax", "ay", "ox", "oy", "vx", "vy", "r", "alpha",
                 "wobble_phase", "wobble_freq", "wobble_amp", "attract_k")

    def __init__(self, ax, ay, ox, oy, vx, vy, r, alpha, wobble_phase, wobble_freq, wobble_amp, attract_k):
        self.ax, self.ay, self.ox, self.oy = ax, ay, ox, oy
        self.vx, self.vy, self.r, self.alpha = vx, vy, r, alpha
        self.wobble_phase, self.wobble_freq, self.wobble_amp = wobble_phase, wobble_freq, wobble_amp
        self.attract_k = attract_k


class Cloud:
    __slots__ = ("type", "x", "y", "width", "anchors", "particles", "rain_rate",
                 "cover", "speed", "bob_phase", "bob_freq", "mini", "bottom")

    def __init__(self, type_, x, y, width, anchors, particles, rain_rate, cover, speed,
                 bob_phase, bob_freq, mini):
        self.type, self.x, self.y, self.width = type_, x, y, width
        self.anchors, self.particles = anchors, particles
        self.rain_rate, self.cover, self.speed = rain_rate, cover, speed
        self.bob_phase, self.bob_freq, self.mini = bob_phase, bob_freq, mini
        #: The underside, as an offset from the centre.
        self.bottom = max(oy + r for _, oy, r in anchors)


class Bolt:
    __slots__ = ("x", "points", "ttl")

    def __init__(self, x: int, points: list, ttl: float) -> None:
        self.x, self.points, self.ttl = x, points, ttl


class Drop:
    __slots__ = ("x", "y", "col", "fall_speed", "landed")

    def __init__(self, x: float, y: float, col: int, fall_speed: float) -> None:
        self.x, self.y, self.col, self.fall_speed = x, y, col, fall_speed
        self.landed = False


# -- building clouds -----------------------------------------------------------


def sculpt_anchors(type_: str, rng: random.Random) -> list:
    """Attraction targets laying out a cloud type; ``(ox, oy, r)`` each."""
    R = rng.random
    puffs = []
    if type_ == "cumulus":
        base_n = 5 + math.floor(R() * 3)
        base_spread = 3.2 + R() * 1.4
        for i in range(base_n):
            t = i / (base_n - 1)
            puffs.append([(t - 0.5) * base_spread * 2, 0.3 + (R() - 0.5) * 0.3, 2.0 + R() * 0.7])
        dome_n = 3 + math.floor(R() * 2)
        dome_spread = base_spread * 0.55
        for i in range(dome_n):
            t = 0.5 if dome_n == 1 else i / (dome_n - 1)
            puffs.append([(t - 0.5) * dome_spread * 2, -0.9 - R() * 0.6, 1.8 + R() * 0.8])
    elif type_ == "stratonimbus":
        n = 10 + math.floor(R() * 5)
        spread = 10 + R() * 4
        for i in range(n):
            t = 0.5 if n == 1 else i / (n - 1)
            ox = (t - 0.5) * spread * 2
            puffs.append([ox, 0.4 + (R() - 0.5) * 0.3, 2.2 + R() * 0.7])
            puffs.append([ox + (R() - 0.5) * 0.8, -0.5 + (R() - 0.5) * 0.4, 1.7 + R() * 0.7])
    else:  # cumulonimbus
        lean = (R() - 0.5) * 3.5
        base_n = 9 + math.floor(R() * 3)
        base_spread = 8 + R() * 2.2
        for i in range(base_n):
            t = i / (base_n - 1) + (R() - 0.5) * 0.12
            puffs.append([(t - 0.5) * base_spread * 2, 2.2 + (R() - 0.5) * 0.5, 2.4 + R() * 0.9])
        waist_rows = 4 + math.floor(R() * 2)
        waist_base_spread = base_spread * 0.55
        for row in range(waist_rows):
            row_n = 3 + math.floor(R() * 2)
            row_t = row / (waist_rows - 1)
            row_spread = waist_base_spread * (1 - row_t * 0.15)
            row_y = 1.0 - row * 1.5
            row_lean = lean * row_t
            for i in range(row_n):
                t = (0.5 if row_n == 1 else i / (row_n - 1)) + (R() - 0.5) * 0.25
                puffs.append([
                    (t - 0.5) * row_spread * 2 + row_lean,
                    row_y + (R() - 0.5) * 0.4,
                    2.1 + R() * 0.8,
                ])
        anvil_n = 6 + math.floor(R() * 3)
        anvil_spread = base_spread * 1.3 + R()
        anvil_y = 1.0 - waist_rows * 1.5 - 0.6
        anvil_skew = lean * 1.4 + (R() - 0.5) * 1.5
        for i in range(anvil_n):
            t = i / (anvil_n - 1) + (R() - 0.5) * 0.1
            edge = abs(t - 0.5) * 2
            puffs.append([
                (t - 0.5) * anvil_spread * 2 + anvil_skew,
                anvil_y + edge * 0.5 + (R() - 0.5) * 0.3,
                2.1 + R() * 0.8,
            ])
    return [
        (ox * GLOBAL_CLOUD_SCALE, oy * GLOBAL_CLOUD_SCALE, r * GLOBAL_CLOUD_SCALE)
        for ox, oy, r in puffs
    ]


def cloud_width_of(anchors: list) -> float:
    return max(ox + r for ox, _, r in anchors) - min(ox - r for ox, _, r in anchors)


def build_particles(anchors: list, rng: random.Random) -> list:
    """Seed free particles near each anchor, then a looser haze across
    the whole footprint, each haze particle bound to its nearest anchor."""
    R = rng.random
    particles = []
    for ox_a, oy_a, r_a in anchors:
        n = 5 + math.floor(R() * 4)
        for _ in range(n):
            ang = R() * math.pi * 2
            dist = R() * r_a * 0.7
            particles.append(Particle(
                ox_a, oy_a,
                ox_a + math.cos(ang) * dist, oy_a + math.sin(ang) * dist,
                (R() - 0.5) * 0.2, (R() - 0.5) * 0.2,
                r_a * (0.45 + R() * 0.35),
                0.55 + R() * 0.35,
                R() * math.pi * 2, 0.12 + R() * 0.18, 0.5 + R() * 0.6,
                PARTICLE_ATTRACT_K,
            ))
    min_x = min(ox - r for ox, _, r in anchors)
    max_x = max(ox + r for ox, _, r in anchors)
    min_y = min(oy - r for _, oy, r in anchors)
    max_y = max(oy + r for _, oy, r in anchors)
    haze = round(len(anchors) * 3)
    for _ in range(haze):
        ox = min_x + R() * (max_x - min_x)
        oy = min_y + R() * (max_y - min_y)
        best = min(anchors, key=lambda a: (a[0] - ox) ** 2 + (a[1] - oy) ** 2)
        particles.append(Particle(
            best[0], best[1], ox, oy,
            (R() - 0.5) * 0.15, (R() - 0.5) * 0.15,
            best[2] * (0.18 + R() * 0.22),
            0.22 + R() * 0.28,
            R() * math.pi * 2, 0.08 + R() * 0.15, 0.9 + R() * 1.1,
            PARTICLE_ATTRACT_K * 0.35,
        ))
    return particles


def pick_cloud_type(rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    for name in CLOUD_TYPE_NAMES:
        acc += CLOUD_TYPES[name]["weight"]
        if r < acc:
            return name
    return CLOUD_TYPE_NAMES[-1]


def roll_cloud_gap(gap_min: float, gap_max: float, rng: random.Random) -> float:
    gap = gap_min + rng.random() * (gap_max - gap_min)
    if rng.random() < CLOUD_LONG_GAP_CHANCE:
        gap *= CLOUD_LONG_GAP_MULT_MIN + rng.random() * (
            CLOUD_LONG_GAP_MULT_MAX - CLOUD_LONG_GAP_MULT_MIN
        )
    return gap


def make_cloud(x: float, rng: random.Random, opts: Optional[dict] = None) -> Cloud:
    opts = opts or {}
    scale = opts.get("scale", 1)
    type_ = opts.get("force_type") or pick_cloud_type(rng)
    anchors = sorted(sculpt_anchors(type_, rng), key=lambda a: -a[1])
    if scale != 1:
        anchors = [(ox * scale, oy * scale, r * scale) for ox, oy, r in anchors]
    definition = CLOUD_TYPES[type_]
    min_y = opts.get("min_y", CLOUD_MIN_Y)
    max_y = opts.get("max_y", CLOUD_MAX_Y)
    mini = bool(opts.get("mini"))
    rain_rate = 0.0 if mini else definition["rain_rate"]
    base_speed = opts.get("wind_speed", WIND_SPEED)
    speed = base_speed * (0.2 if rain_rate > 0 else 1)  # rain is heavy and slow
    y = min_y + rng.random() * (max_y - min_y)
    return Cloud(
        type_, x, y, cloud_width_of(anchors), anchors, build_particles(anchors, rng),
        rain_rate, 0.0 if mini else definition["cover"], speed,
        rng.random() * math.pi * 2, 0.15 + rng.random() * 0.1, mini,
    )


def mini_cloud_opts(rng: random.Random) -> dict:
    return {
        "scale": MINI_CLOUD_SCALE_MIN + rng.random() * (MINI_CLOUD_SCALE_MAX - MINI_CLOUD_SCALE_MIN),
        "force_type": "cumulus",
        "min_y": MINI_CLOUD_MIN_Y,
        "max_y": MINI_CLOUD_MAX_Y,
        "mini": True,
        "wind_speed": MINI_WIND_SPEED,
    }


# -- the weather -----------------------------------------------------------------


class Weather:
    """Every cloud, drop and bolt within reach of the player."""

    def __init__(self, world: World, rng: random.Random, player_x: float) -> None:
        self.world = world
        self.rng = rng
        self.sim_time = 0.0
        self.clouds = self._seed(player_x, CLOUD_GAP_MIN, CLOUD_GAP_MAX, None, 3)
        self.mini_clouds = self._seed(
            player_x, MINI_CLOUD_GAP_MIN, MINI_CLOUD_GAP_MAX, mini_cloud_opts, 3
        )
        self.sky_overcast = 0.0
        self.storm_overcast = 0.0
        self.screen_flash = 0.0
        self.bolts: list = []
        self.drops: list = []
        self._rain_credit: dict = {}

    # -- seeding and recycling -----------------------------------------

    def _seed(self, player_x, gap_min, gap_max, opts, guard_mult) -> list:
        clouds = []
        left = player_x - WEATHER_RADIUS
        far = player_x + WEATHER_RADIUS
        guard = 0
        guard_max = max(8, round((WEATHER_RADIUS * 2) / ((gap_min + gap_max) / 2 + 6))) * guard_mult
        while left < far and guard < guard_max:
            guard += 1
            o = opts(self.rng) if callable(opts) else opts
            cloud = make_cloud(left, self.rng, o)
            cloud.x = left + cloud.width / 2
            clouds.append(cloud)
            left = cloud.x + cloud.width / 2 + roll_cloud_gap(gap_min, gap_max, self.rng)
        return clouds

    def _recycle(self, clouds, player_x, gap_min, gap_max, opts) -> None:
        leftmost = min(c.x - c.width / 2 for c in clouds) if clouds else math.inf
        for i, cloud in enumerate(clouds):
            if cloud.x - player_x > WEATHER_RADIUS + cloud.width:
                gap = roll_cloud_gap(gap_min, gap_max, self.rng)
                right_edge = min(leftmost - gap, player_x - WEATHER_RADIUS)
                o = opts(self.rng) if callable(opts) else opts
                fresh = make_cloud(0, self.rng, o)
                fresh.x = right_edge - fresh.width / 2
                clouds[i] = fresh
                leftmost = fresh.x - fresh.width / 2

    def tick(self, player_x: float) -> None:
        """The slow tick: bring drifted-away clouds back in on the west."""
        self._recycle(self.clouds, player_x, CLOUD_GAP_MIN, CLOUD_GAP_MAX, None)
        self._recycle(self.mini_clouds, player_x, MINI_CLOUD_GAP_MIN, MINI_CLOUD_GAP_MAX, mini_cloud_opts)

    # -- motion ----------------------------------------------------------

    def update_motion(self, dt_ms: float, camera_x: float) -> None:
        """Every frame: drift on the wind; wobble the swarms near the camera."""
        dt = dt_ms / 1000.0
        self.sim_time += dt
        damp = PARTICLE_DAMPING ** (dt * 60)
        sim_time = self.sim_time
        for cloud in self.clouds + self.mini_clouds:
            cloud.x += cloud.speed * dt
            if abs(cloud.x - camera_x) > PARTICLE_ACTIVE_RANGE + cloud.width:
                continue
            for p in cloud.particles:
                wob_x = math.sin(sim_time * p.wobble_freq + p.wobble_phase) * p.wobble_amp
                wob_y = math.cos(sim_time * p.wobble_freq * 1.3 + p.wobble_phase) * p.wobble_amp * 0.6
                p.vx = (p.vx + (p.ax + wob_x - p.ox) * p.attract_k * dt) * damp
                p.vy = (p.vy + (p.ay + wob_y - p.oy) * p.attract_k * dt) * damp
                p.ox += p.vx * dt
                p.oy += p.vy * dt

    # -- what is overhead ------------------------------------------------

    def cloud_cover_at(self, x: float) -> float:
        cover = 0.0
        for c in self.clouds:
            half = c.width / 2
            d = abs(x - c.x)
            if d < half:
                cover = max(cover, c.cover * (1 - (d / half) * 0.5))
        return max(0.0, min(1.0, cover))

    def storm_cover_at(self, x: float) -> float:
        cover = 0.0
        for c in self.clouds:
            if not c.rain_rate:
                continue
            half = c.width / 2
            d = abs(x - c.x)
            if d < half:
                cover = max(cover, c.cover * (1 - (d / half) * 0.5))
        return max(0.0, min(1.0, cover))

    def rain_intensity_at(self, x: float) -> float:
        intensity = 0.0
        for c in self.clouds:
            if c.rain_rate and abs(x - c.x) < c.width / 2 * 0.85:
                intensity = max(intensity, c.rain_rate)
        return intensity

    def cloud_bottom_at(self, x: float) -> float:
        bottom = None
        for c in self.clouds:
            if c.rain_rate and abs(x - c.x) < c.width / 2 * 0.85:
                b = c.y + c.bottom
                if bottom is None or b > bottom:
                    bottom = b
        return CLOUD_MAX_Y if bottom is None else bottom

    def settle_overcast(self, ref_x: float) -> None:
        """Ease the tint toward the cover overhead so it never flickers."""
        self.sky_overcast += (self.cloud_cover_at(round(ref_x)) - self.sky_overcast) * 0.05
        self.storm_overcast += (self.storm_cover_at(round(ref_x)) - self.storm_overcast) * 0.05

    @property
    def celestial_visibility(self) -> float:
        cloudiness = max(self.sky_overcast, self.storm_overcast * 1.2)
        return max(0.0, 1 - cloudiness * 1.6)

    # -- lightning ---------------------------------------------------------

    def _bolt_points(self, top_y: float, bottom_y: float) -> list:
        steps = 5 + math.floor(self.rng.random() * 3)
        points = []
        for i in range(steps + 1):
            t = i / steps
            dx = 0.0 if i in (0, steps) else (self.rng.random() - 0.5) * 1.6
            points.append((dx, top_y + (bottom_y - top_y) * t))
        return points

    def strike(self, cloud: Cloud, player_x: float, player_y: float) -> None:
        half = cloud.width / 2
        in_domain = abs(player_x - cloud.x) < half * 0.85
        below_clouds = player_y >= CLOUD_MAX_Y + 10
        if in_domain and below_clouds:
            self.screen_flash = 0.8 + self.rng.random() * 0.2
        strike_x = math.floor(cloud.x + (self.rng.random() - 0.5) * half * 1.4 + 0.5)
        top_y = cloud.y + cloud.bottom
        bottom_y = self.world.gen.front_height(strike_x)
        self.bolts.append(Bolt(strike_x, self._bolt_points(top_y, bottom_y), LIGHTNING_BOLT_TTL))

    def update_lightning(self, dt_ms: float, player_x: float, player_y: float) -> None:
        dt = dt_ms / 1000.0
        if self.screen_flash > 0:
            self.screen_flash = max(0.0, self.screen_flash - LIGHTNING_FLASH_DECAY * dt)
        for bolt in list(self.bolts):
            bolt.ttl -= dt_ms
            if bolt.ttl <= 0:
                self.bolts.remove(bolt)
        for cloud in self.clouds:
            if cloud.type != "cumulonimbus":
                continue
            if self.rng.random() < LIGHTNING_CHANCE_PER_SEC * cloud.rain_rate * dt:
                self.strike(cloud, player_x, player_y)

    # -- rain ------------------------------------------------------------

    def spawn_rain(self, player_x: float, player_y: float) -> None:
        px, py = math.floor(player_x + 0.5), math.floor(player_y + 0.5)
        lo_x, hi_x = px - RAIN_SIM_RADIUS, px + RAIN_SIM_RADIUS
        lo_y, hi_y = py - RAIN_SIM_RADIUS, py + RAIN_SIM_RADIUS
        credit = self._rain_credit
        for x in list(credit):
            if x < lo_x or x >= hi_x:
                del credit[x]
        in_box: dict = {}
        for d in self.drops:
            if lo_y <= d.y <= hi_y:
                in_box[d.col] = in_box.get(d.col, 0) + 1
        for x in range(lo_x, hi_x):
            intensity = self.rain_intensity_at(x)
            if intensity <= 0:
                credit.pop(x, None)
                continue
            cap = 1 + math.floor(intensity * (RAIN_MAX_PER_COLUMN - 1) + 0.5)
            if in_box.get(x, 0) >= cap:
                credit[x] = min(credit.get(x, 0.0), 1.0)
                continue
            owed = credit.get(x, 0.0) + intensity * 0.85
            if owed >= 1:
                bottom = max(self.cloud_bottom_at(x), lo_y - 1)
                fall_speed = RAIN_FALL_SPEED * (0.8 + self.rng.random() * 0.4)
                self.drops.append(Drop(x + 0.5, bottom + 1, x, fall_speed))
                credit[x] = owed - 1
            else:
                credit[x] = owed

    def update_rain(self, dt_ms: float, player_x: float, player_y: float, t_sec: float) -> None:
        dt = dt_ms / 1000.0
        py = math.floor(player_y + 0.5)
        px = math.floor(player_x + 0.5)
        world = self.world
        keep = []
        for d in self.drops:
            if d.landed:
                continue  # it had its frame resting on the surface
            d.y += d.fall_speed * dt
            cx = math.floor(d.x)
            out = d.y - py > RAIN_SIM_RADIUS + 4 or abs(cx - px) > RAIN_SIM_RADIUS + 4
            if d.y >= WORLD_H or out:
                continue
            row = math.floor(d.y)
            if world.solid_at(cx, row + 1):
                d.y = row
                d.landed = True
            elif world.fluid_at(cx, row) and tiles.is_water(world.block(cx, row)):
                surface = float(row)
                if world.gen.ocean_factor(cx) > 0.02:
                    surface -= self.current_wave_height_at(cx, t_sec) / BLOCK
                d.y = surface
                d.landed = True
            keep.append(d)
        self.drops = keep

    # -- waves -----------------------------------------------------------

    def ocean_depth_at(self, x: int) -> int:
        return max(0, self.world.gen.front_height(x) - SEA_LEVEL)

    def weather_wave_factor_at(self, x: int) -> float:
        col = math.floor(x + 0.5)
        return 1 + self.cloud_cover_at(col) * 0.4 + self.rain_intensity_at(col) * 0.4

    def ocean_max_wave_height_at(self, x: int) -> int:
        depth = self.ocean_depth_at(x)
        if depth <= OCEAN_SHALLOW_DEPTH:
            return 0
        depth_factor = max(0.0, min(1.0, (depth - OCEAN_SHALLOW_DEPTH) / (OCEAN_FULL_DEPTH - OCEAN_SHALLOW_DEPTH)))
        h = depth_factor * OCEAN_BASELINE_WAVE_PX * self.weather_wave_factor_at(x)
        return max(0, min(5, math.floor(h + 0.5)))

    def max_wave_height_at(self, x: int) -> int:
        h = self.ocean_max_wave_height_at(x)
        return h if self.world.gen.ocean_factor(x) > 0 else min(LAKE_MAX_WAVE_PX, h)

    def extra_swim_blocks_at(self, x: int) -> int:
        h = self.max_wave_height_at(x)
        if h < 3:
            return 0
        return 1 if h < 5 else 2

    def wave_envelope_at(self, raw_px: float, t_sec: float, max_h: int) -> float:
        wavelength = 5 + max_h * 6
        phase = raw_px / wavelength + t_sec * 0.3
        hump = (math.sin(phase * math.pi * 2) + 1) / 2
        jitter = (noise1d(raw_px * 0.8 + t_sec * 5, 42, 0.4, self.world.seed) - 0.5) * 0.3
        return max(0.0, min(1.0, hump + jitter))

    def current_wave_height_at(self, x: int, t_sec: float) -> int:
        max_h = self.max_wave_height_at(x)
        if max_h <= 0:
            return 0
        best = 0
        for i in range(BLOCK):
            h = min(max_h, math.floor(self.wave_envelope_at(x * BLOCK + i, t_sec, max_h) * max_h + 0.5))
            best = max(best, h)
        return best

    def fluid_or_wave_at(self, x: int, y: int, t_sec: float) -> bool:
        """Water, or the air a wave has visibly risen into right now."""
        world = self.world
        if world.fluid_at(x, y):
            return True
        if world.block(x, y) != tiles.SKY:
            return False
        cap = self.extra_swim_blocks_at(x)
        if cap <= 0:
            return False
        h = self.current_wave_height_at(x, t_sec)
        for d in range(1, cap + 1):
            if not world.is_open_water_surface(x, y + d):
                continue
            if h >= (d - 1) * BLOCK + 1:
                return True
        return False

    # -- drawing -----------------------------------------------------------

    def draw_clouds(self, canvas: Canvas, cam_x: float, cam_y: float) -> None:
        """Mini wisps first, so they read as further back."""
        self._draw_cloud_list(self.mini_clouds, canvas, cam_x, cam_y)
        self._draw_cloud_list(self.clouds, canvas, cam_x, cam_y)

    def _draw_cloud_list(self, clouds, canvas: Canvas, cam_x: float, cam_y: float) -> None:
        px_buf = canvas.px
        cr, cg, cb = CLOUD_COLOUR
        for c in clouds:
            rel_x = c.x - cam_x
            half = c.width / 2 + 1
            if rel_x < -half or rel_x > COLS + half:
                continue
            bob = math.sin(self.sim_time * c.bob_freq + c.bob_phase) * 0.3
            rel_y = (c.y + bob) - cam_y
            for p in c.particles:
                pr = p.r * BLOCK
                if pr <= 0:
                    continue
                px = (rel_x + p.ox) * BLOCK
                py = (rel_y + p.oy) * BLOCK
                x0 = math.floor(px - pr)
                x1 = math.ceil(px + pr)
                y0 = math.floor(py - pr)
                y1 = math.ceil(py + pr)
                if x1 < 0 or y1 < 0 or x0 >= WIDTH or y0 >= HEIGHT:
                    continue
                a0 = p.alpha
                for y in range(max(0, y0), min(HEIGHT - 1, y1) + 1):
                    dy = (y + 0.5) - py
                    dy2 = dy * dy
                    row = y * WIDTH
                    for x in range(max(0, x0), min(WIDTH - 1, x1) + 1):
                        dx = (x + 0.5) - px
                        t = math.sqrt(dx * dx + dy2) / pr
                        if t >= 1.0:
                            continue
                        # stops: 0 -> a, 0.7 -> a/2, 1 -> 0
                        if t < 0.7:
                            a = a0 * (1 - (t / 0.7) * 0.5)
                        else:
                            a = a0 * 0.5 * (1 - (t - 0.7) / 0.3)
                        i = (row + x) * 3
                        keep = 1.0 - a
                        px_buf[i] = px_buf[i] * keep + cr * a
                        px_buf[i + 1] = px_buf[i + 1] * keep + cg * a
                        px_buf[i + 2] = px_buf[i + 2] * keep + cb * a

    def draw_rain(self, canvas: Canvas, cam_x: float, cam_y: float) -> None:
        for d in self.drops:
            rel_x, rel_y = d.x - cam_x, d.y - cam_y
            if rel_x < 0 or rel_x >= COLS or rel_y < 0 or rel_y >= ROWS:
                continue
            canvas.set(math.floor(rel_x * BLOCK), math.floor(rel_y * BLOCK), RAIN_COLOUR)

    def draw_bolts(self, canvas: Canvas, cam_x: float, cam_y: float) -> None:
        for b in self.bolts:
            rel_x = b.x - cam_x
            if rel_x < -2 or rel_x > COLS + 2:
                continue
            alpha = max(0.0, b.ttl / LIGHTNING_BOLT_TTL)
            last = None
            for dx, y in b.points:
                point = ((rel_x + dx) * BLOCK, (y - cam_y) * BLOCK)
                if last is not None:
                    canvas.line(last[0], last[1], point[0], point[1], BOLT_COLOUR, alpha)
                last = point

    def draw_flash(self, canvas: Canvas) -> None:
        if self.screen_flash > 0.001:
            canvas.fill(FLASH_COLOUR, self.screen_flash * 0.85)

    def draw_overcast(self, canvas: Canvas, below_clouds: bool) -> None:
        if below_clouds and self.sky_overcast > 0.01:
            canvas.fill(OVERCAST_TINT, self.sky_overcast * 0.65)
        if below_clouds and self.storm_overcast > 0.01:
            canvas.fill(STORM_TINT, self.storm_overcast * 0.8)

    def draw_waves(self, canvas: Canvas, cam_x: int, cam_y: int, t_sec: float) -> None:
        """Ripples cut from the water tile's own top pixels, rising above
        every open water surface on screen."""
        world = self.world
        sheet = palette.tile_art(tiles.WATER)[0]
        sx, sy = tiles.SHEET_POS[tiles.WATER]
        for ry in range(ROWS):
            for rx in range(COLS):
                wx, wy = cam_x + rx, cam_y + ry
                if not world.is_open_water_surface(wx, wy):
                    continue
                max_h = self.max_wave_height_at(wx)
                if max_h <= 0:
                    continue
                dx, dy = rx * BLOCK, ry * BLOCK
                for i in range(BLOCK):
                    h = min(max_h, math.floor(self.wave_envelope_at(wx * BLOCK + i, t_sec, max_h) * max_h + 0.5))
                    if h <= 0:
                        continue
                    colour = sheet[sy][sx + i]
                    for k in range(1, h + 1):
                        canvas.set(dx + i, dy - k, colour)
                        if k == h and h >= 3:
                            canvas.set(dx + i, dy - k, WAVE_FOAM, WAVE_FOAM_ALPHA)
