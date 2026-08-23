"""Painting the game onto a 16x16 frame.

Every painter here returns a complete framebuffer, the same 768 bytes
the panel takes, and touches nothing else. That keeps the whole visual
side of the game testable by reading pixels back out, and it means the
session can hand a frame straight to a :class:`~pi_menu.display.pump.FramePump`
without an intermediate drawing surface.

Colour carries all the status the panel has room for, so every kind of
tile gets its own hue and no two that appear together are close. The one
thing colour cannot say is *which way* a conveyor pushes -- a single
pixel has no arrow -- so conveyors say it with a highlight that travels
along the belt in the direction it moves you.
"""

from __future__ import annotations

from typing import Iterable

from ..display.protocol import FRAME_BYTES, HEIGHT, WIDTH, pixel_offset
from . import font
from .camera import window_x
from .world import World

# -- the world -----------------------------------------------------------

PLATFORM = (24, 40, 96)
#: A platform that moves is the same idea, lit up.
MOVER = (70, 120, 255)
ICE = (205, 230, 255)
CRUMBLE = (150, 75, 30)
CONVEYOR = (0, 200, 170)
CONVEYOR_HIGHLIGHT = (140, 255, 230)
BOUNCE = (170, 255, 40)
PLAYER = (0, 220, 255)
COIN = (255, 170, 0)
SPIKE = (220, 30, 30)
ENEMY = (255, 50, 130)
PORTAL = (225, 0, 210)
PORTAL_DIM = (110, 0, 105)
#: Shut, the goal is barely there. It is not a destination yet.
GOAL_SHUT = (60, 60, 70)
GOAL_OPEN = (0, 255, 90)
GOAL_OPEN_DIM = (0, 110, 40)

DEATH_FLASH = (255, 40, 40)
WIN_FLASH = (0, 255, 120)

#: Every third belt pixel is lit, and the pattern travels one cell per
#: two ticks in the direction the belt pushes.
CONVEYOR_STRIDE = 3
CONVEYOR_TICKS = 2

# -- the menu ------------------------------------------------------------

MENU_SELECTED = (0, 255, 120)
MENU_IDLE = (28, 62, 44)
MENU_MARKER = (255, 255, 255)
MENU_WORDS = ("PLAY", "LVLS")
#: The words start clear of the marker column.
MENU_LEFT = 2
MENU_TOP = 2
#: Blank rows between the two words. Wide enough that they read as two
#: choices rather than one block of pixels.
MENU_GAP = 4

# -- the picker ----------------------------------------------------------

#: One pixel per level, every other column and row. Chunkier tiles were
#: readable at twelve levels and ran out of panel long before thirty.
PICKER_COLUMNS = 8
PICKER_ROWS = 5
PICKER_PITCH = 2
PICKER_CAPACITY = PICKER_COLUMNS * PICKER_ROWS
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


def put(frame: bytearray, x: int, y: int, colour: tuple) -> None:
    """Set one pixel, ignoring anything off the panel."""
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        offset = pixel_offset(x, y)
        frame[offset : offset + 3] = bytes(colour)


def pulse(on: tuple, off: tuple, phase: int) -> tuple:
    """Alternate between two colours as ``phase`` advances."""
    return on if (phase // PULSE_TICKS) % 2 == 0 else off


def flash(colour: tuple) -> bytes:
    """A frame of one colour, for a death or a win."""
    return bytes(colour) * (WIDTH * HEIGHT)


def tile_colour(level, cell: tuple, phase: int) -> tuple:
    """The colour of one static floor tile."""
    if cell in level.ice:
        return ICE
    if cell in level.bounce:
        return BOUNCE
    if cell in level.crumble:
        return CRUMBLE
    push = level.conveyors.get(cell)
    if push is not None:
        return _belt_colour(cell[0], push, phase)
    return PLATFORM


def _belt_colour(x: int, push: int, phase: int) -> tuple:
    """A belt pixel, lit or not, so the pattern travels as it pushes."""
    travelled = phase // CONVEYOR_TICKS
    if (x - push * travelled) % CONVEYOR_STRIDE == 0:
        return CONVEYOR_HIGHLIGHT
    return CONVEYOR


def draw_world(world: World, phase: int = 0) -> bytes:
    """The camera's view of a level in play.

    Drawn back to front -- ground, hazards, pickups, goal, player -- so
    the player is never hidden by the tile they are standing on.
    """
    frame = blank()
    level = world.level
    left = window_x(world.x, level.width)

    def visible(cells):
        return [(x, y) for x, y in cells if left <= x < left + WIDTH]

    for panel_x in range(WIDTH):
        x = left + panel_x
        if not 0 <= x < level.width:
            continue
        for y in range(HEIGHT):
            if (x, y) in world.crumbled:
                continue
            if level.static_solid(x, y):
                put(frame, panel_x, y, tile_colour(level, (x, y), phase))

    for x, y in visible(world.mover_cells()):
        put(frame, x - left, y, MOVER)

    for x, y in visible(level.spikes):
        put(frame, x - left, y, SPIKE)

    for x, y in visible(level.portals):
        put(frame, x - left, y, pulse(PORTAL, PORTAL_DIM, phase))

    for x, y in visible(world.coins):
        put(frame, x - left, y, COIN)

    goal_x, goal_y = level.goal
    goal_colour = (
        pulse(GOAL_OPEN, GOAL_OPEN_DIM, phase) if world.goal_open else GOAL_SHUT
    )
    put(frame, goal_x - left, goal_y, goal_colour)

    for x, y in visible(world.enemy_cells()):
        put(frame, x - left, y, ENEMY)

    player_x, player_y = world.pixel
    put(frame, player_x - left, player_y, PLAYER)

    return bytes(frame)


def draw_menu(selected: int, phase: int = 0) -> bytes:
    """The title screen: PLAY over LVLS, with the chosen one marked."""
    frame = blank()
    for index, word in enumerate(MENU_WORDS):
        chosen = index == selected
        colour = MENU_SELECTED if chosen else MENU_IDLE
        top = MENU_TOP + index * (font.GLYPH_HEIGHT + MENU_GAP)
        for x, y in font.pixels(word, MENU_LEFT, top):
            put(frame, x, y, colour)
        if chosen:
            # A marker in the spare column, so the choice is legible even
            # where the two greens are hard to tell apart.
            put(frame, 0, top + 1, MENU_MARKER)
            put(frame, 0, top + 2, MENU_MARKER)
    return bytes(frame)


def draw_picker(index: int, completed: Iterable, count: int, phase: int = 0) -> bytes:
    """A pixel per level, and the number of the one under the cursor."""
    if count > PICKER_CAPACITY:
        raise ValueError(
            f"the picker holds {PICKER_CAPACITY} levels, not {count} -- "
            "another row would cover the level number"
        )
    frame = blank()
    done = set(completed)

    for level_index in range(count):
        x = (level_index % PICKER_COLUMNS) * PICKER_PITCH
        y = (level_index // PICKER_COLUMNS) * PICKER_PITCH
        colour = TILE_DONE if level_index in done else TILE_TODO
        if level_index == index:
            colour = pulse(CURSOR, colour, phase)
        put(frame, x, y, colour)

    label = str(index + 1)
    left = (WIDTH - font.text_width(label)) // 2
    for x, y in font.pixels(label, left, NUMBER_TOP):
        put(frame, x, y, NUMBER)

    return bytes(frame)
