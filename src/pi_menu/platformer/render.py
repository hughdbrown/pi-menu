"""Painting the game onto a 16x16 frame.

Every painter here returns a complete framebuffer, the same 768 bytes
the panel takes, and touches nothing else. That keeps the whole visual
side of the game testable by reading pixels back out, and it means the
session can hand a frame straight to a :class:`~pi_menu.display.pump.FramePump`
without an intermediate drawing surface.

Colour carries all the status the panel has room for: which menu entry
is selected, whether a level is finished, whether the goal has opened.
There is no space for a word longer than four characters, so none of it
can be spelled out.
"""

from __future__ import annotations

from typing import Iterable

from ..display.protocol import FRAME_BYTES, HEIGHT, WIDTH, pixel_offset
from . import font
from .camera import window_x
from .world import World

# -- the world -----------------------------------------------------------

PLATFORM = (24, 40, 96)
PLAYER = (0, 220, 255)
COIN = (255, 170, 0)
SPIKE = (220, 30, 30)
#: Shut, the goal is barely there. It is not a destination yet.
GOAL_SHUT = (60, 60, 70)
GOAL_OPEN = (0, 255, 90)
GOAL_OPEN_DIM = (0, 110, 40)

DEATH_FLASH = (255, 40, 40)
WIN_FLASH = (0, 255, 120)

# -- the menu ------------------------------------------------------------

MENU_SELECTED = (0, 255, 120)
MENU_IDLE = (28, 62, 44)
MENU_WORDS = ("PLAY", "LVLS")
#: Two words of five rows with one blank row between them, centred.
MENU_TOP = (HEIGHT - (2 * font.GLYPH_HEIGHT + 1)) // 2

# -- the picker ----------------------------------------------------------

TILE_SIZE = 3
TILE_PITCH = TILE_SIZE + 1
PICKER_COLUMNS = 4
TILE_DONE = (0, 190, 70)
TILE_TODO = (30, 45, 90)
CURSOR = (255, 255, 255)
NUMBER = (170, 180, 210)
#: The first row of the level number, below the grid.
NUMBER_TOP = 11

#: How many ticks a pulsing colour spends on each of its two shades.
PULSE_TICKS = 5


def blank() -> bytearray:
    return bytearray(FRAME_BYTES)


def put(frame: bytearray, x: int, y: int, colour: tuple[int, int, int]) -> None:
    """Set one pixel, ignoring anything off the panel."""
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        offset = pixel_offset(x, y)
        frame[offset : offset + 3] = bytes(colour)


def pulse(
    on: tuple[int, int, int], off: tuple[int, int, int], phase: int
) -> tuple[int, int, int]:
    """Alternate between two colours as ``phase`` advances."""
    return on if (phase // PULSE_TICKS) % 2 == 0 else off


def flash(colour: tuple[int, int, int]) -> bytes:
    """A frame of one colour, for a death or a win."""
    return bytes(colour) * (WIDTH * HEIGHT)


def draw_world(world: World, phase: int = 0) -> bytes:
    """The camera's view of a level in play.

    Drawn back to front -- ground, hazards, pickups, goal, player -- so
    the player is never hidden by the tile they are standing on.
    """
    frame = blank()
    level = world.level
    left = window_x(world.x, level.width)

    for panel_x in range(WIDTH):
        x = left + panel_x
        if not 0 <= x < level.width:
            continue
        for y in range(HEIGHT):
            if level.solid(x, y):
                put(frame, panel_x, y, PLATFORM)

    for x, y in level.spikes:
        put(frame, x - left, y, SPIKE)

    for x, y in world.coins:
        put(frame, x - left, y, COIN)

    goal_x, goal_y = level.goal
    goal_colour = (
        pulse(GOAL_OPEN, GOAL_OPEN_DIM, phase) if world.goal_open else GOAL_SHUT
    )
    put(frame, goal_x - left, goal_y, goal_colour)

    player_x, player_y = world.pixel
    put(frame, player_x - left, player_y, PLAYER)

    return bytes(frame)


def draw_menu(selected: int, phase: int = 0) -> bytes:
    """The title screen: PLAY over LVLS, the chosen one lit."""
    frame = blank()
    for index, word in enumerate(MENU_WORDS):
        colour = MENU_SELECTED if index == selected else MENU_IDLE
        left = (WIDTH - font.text_width(word)) // 2
        top = MENU_TOP + index * (font.GLYPH_HEIGHT + 1)
        for x, y in font.pixels(word, left, top):
            put(frame, x, y, colour)
    return bytes(frame)


def draw_picker(
    index: int, completed: Iterable[int], count: int, phase: int = 0
) -> bytes:
    """A tile per level, and the number of the one under the cursor."""
    frame = blank()
    done = set(completed)

    for level_index in range(count):
        column = level_index % PICKER_COLUMNS
        row = level_index // PICKER_COLUMNS
        origin_x = column * TILE_PITCH
        origin_y = row * TILE_PITCH
        colour = TILE_DONE if level_index in done else TILE_TODO
        for dy in range(TILE_SIZE):
            for dx in range(TILE_SIZE):
                on_edge = dx in (0, TILE_SIZE - 1) or dy in (0, TILE_SIZE - 1)
                if level_index == index and on_edge:
                    put(
                        frame,
                        origin_x + dx,
                        origin_y + dy,
                        pulse(CURSOR, colour, phase),
                    )
                else:
                    put(frame, origin_x + dx, origin_y + dy, colour)

    label = str(index + 1)
    left = (WIDTH - font.text_width(label)) // 2
    for x, y in font.pixels(label, left, NUMBER_TOP):
        put(frame, x, y, NUMBER)

    return bytes(frame)
