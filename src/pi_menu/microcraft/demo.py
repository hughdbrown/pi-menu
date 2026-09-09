"""The camera tour behind the opening screen.

Twelve shots in a fixed running order: steady pans over a few distinct
stretches of the loop at treetop or ground height, a couple of dips
underground, flights through the cloud deck near where the player will
spawn, and two shots that hold still while a whole day runs past in
nine seconds. Each shot pins the time of day, so the tour shows off
sunrise, noon, an eclipse, sunset and the moonlit night in turn.
"""

from __future__ import annotations

from .player import COLS, ROWS
from .terrain import WORLD_H, Generator
from .weather import CLOUD_MAX_Y, CLOUD_MIN_Y

#: Seven points spread evenly round the loop.
ANCHORS = (0, 285, 571, 857, -857, -571, -286)
SHOT_MS = 7000
PAN_BLOCKS = 70
CLOUD_SHOT_Y_MIN = CLOUD_MIN_Y - 6
CLOUD_SHOT_Y_MAX = CLOUD_MAX_Y - 6

GROUND = "ground"
CLOUD = "cloud"
TIMELAPSE = "timelapse"

SHOTS = (
    {"kind": GROUND, "anchor": 0, "depth": -6, "time": 0.28},
    {"kind": TIMELAPSE, "anchor": 1, "depth": -3, "time_start": 0.20, "ms": 9000},
    {"kind": CLOUD, "time": 0.45},
    {"kind": GROUND, "anchor": 5, "depth": -6, "time": 0.50, "moon": 0.0},
    {"kind": GROUND, "anchor": 2, "depth": 9, "time": 0.60},
    {"kind": GROUND, "anchor": 3, "depth": -6, "time": 0.72},
    {"kind": CLOUD, "time": 0.70},
    {"kind": TIMELAPSE, "anchor": 4, "depth": -3, "time_start": 0.62, "ms": 9000},
    {"kind": GROUND, "anchor": 4, "depth": 15, "time": 0.85},
    {"kind": GROUND, "anchor": 5, "depth": -3, "time": 0.92},
    {"kind": CLOUD, "time": 0.95},
    {"kind": GROUND, "anchor": 6, "depth": -6, "time": 0.22},
)


class Demo:
    """Which shot is playing, where its camera is, and what time it is."""

    def __init__(self, gen: Generator, spawn_x: float) -> None:
        self.gen = gen
        self.spawn_x = spawn_x
        self.index = -1
        self.elapsed = 0.0
        self.duration = SHOT_MS
        self.start_x = 0.0
        self.end_x = 0.0
        self.fixed_y = None
        self.time_frac = 0.5
        self.timelapse = False
        self.time_start = 0.5
        self.moon_phase = None
        self.cam_x = 0
        self.cam_y = 0

    @property
    def shot(self) -> dict:
        return SHOTS[self.index % len(SHOTS)]

    def pick(self, index: int) -> None:
        self.index = index
        shot = self.shot
        self.duration = shot.get("ms", SHOT_MS)
        self.timelapse = shot["kind"] == TIMELAPSE
        self.moon_phase = shot.get("moon")
        if self.timelapse:
            self.time_start = shot["time_start"]
        else:
            self.time_frac = shot["time"]
        direction = 1 if index % 2 == 0 else -1
        if shot["kind"] == CLOUD:
            jitter = (index * 613) % 41
            self.start_x = self.spawn_x - PAN_BLOCKS / 2 + jitter
            self.end_x = self.start_x + direction * PAN_BLOCKS
            self.fixed_y = CLOUD_SHOT_Y_MIN + (index * 977) % (CLOUD_SHOT_Y_MAX - CLOUD_SHOT_Y_MIN + 1)
        else:
            anchor = ANCHORS[shot["anchor"] % len(ANCHORS)]
            self.start_x = anchor + (index * 37) % 101
            self.end_x = self.start_x if self.timelapse else self.start_x + direction * PAN_BLOCKS
            self.fixed_y = None
        self.elapsed = 0.0

    def cam_y_at(self, x: float) -> int:
        shot = self.shot
        if shot["kind"] == CLOUD:
            return self.fixed_y
        column = int(x + 0.5) if x >= 0 else -int(-x + 0.5)
        if shot["depth"] > 0:
            surf = self.gen.front_height(column)
        else:
            surf = self.gen.surface_ref(column)
        return max(0, min(WORLD_H - ROWS, surf + shot["depth"]))

    def update(self, dt_ms: float) -> None:
        if self.index == -1:
            self.pick(0)
        self.elapsed += dt_ms
        if self.elapsed >= self.duration:
            self.pick(self.index + 1)
        t = min(1.0, self.elapsed / self.duration)
        x = self.start_x + (self.end_x - self.start_x) * t
        self.cam_x = int((x - COLS / 2) + 0.5) if x - COLS / 2 >= 0 else -int(-(x - COLS / 2) + 0.5)
        self.cam_y = self.cam_y_at(x)
        if self.timelapse:
            self.time_frac = (self.time_start + t) % 1
