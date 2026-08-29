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
from . import bosses, font
from .camera import window_x, window_y
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

ONE_WAY = (150, 220, 160)
LADDER = (190, 140, 60)
UPDRAFT = (120, 210, 235)
UPDRAFT_DIM = (40, 90, 110)
BLINK_ON = (200, 120, 255)

# -- the demons ----------------------------------------------------------

#: Bodies are drawn dim: the demon is scenery, not something you touch.
DEMON_BODY = {
    "ember": (70, 25, 10),
    "viridian": (15, 60, 35),
    "brass": (70, 55, 10),
    "crimson": (85, 10, 20),
}
DEMON_EYE = (255, 230, 60)
DEMON_EYE_DIM = (120, 80, 0)
DEMON_MOUTH = (255, 120, 0)
#: Fists and fireballs, on the other hand, are as loud as the panel gets.
FIST = (255, 90, 20)
FIREBALL = (255, 200, 40)

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

#: The menu is icons in a row now, not words in a column -- icons are
#: narrow enough to leave room for more buttons later. Each icon is its
#: lit pixels relative to its own origin.
ICON_PLAY = tuple(  # a play-button triangle, pointing right
    (0, y) for y in range(5)
) + ((1, 1), (1, 2), (1, 3), (2, 2))
ICON_LEVELS = tuple(  # a 4x4 box, hollow in the centre
    (x, y)
    for x in range(4)
    for y in range(4)
    if x in (0, 3) or y in (0, 3)
)
ICON_SETTINGS = (  # a 2x2 block with the four odd teeth Hugh specified
    (0, 0), (1, 0), (0, 1), (1, 1),
    (2, -1), (-1, 0), (3, 1), (1, 3),
)

#: Where each icon's origin sits on the panel, top row of the marker
#: underneath it, in menu-entry order: play, levels, settings.
MENU_ICONS = (
    (ICON_PLAY, (2, 5)),
    (ICON_LEVELS, (7, 6)),
    (ICON_SETTINGS, (12, 6)),
)
MENU_MARKER_ROW = 12

# -- the picker ----------------------------------------------------------

#: One pixel per level, sixteen to a row with a blank row between rows.
#: Eight-wide with gaps held forty; sixty needs the columns packed.
#: Adjacent pixels stay countable because the row breaks do the grouping.
PICKER_COLUMNS = 16
PICKER_ROWS = 5
PICKER_ROW_PITCH = 2
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

    Drawn back to front -- demon, ground, hazards, pickups, goal, player
    -- so the player is never hidden by the tile they are standing on,
    and the demon is never in front of the level it is throwing things
    at. That order is what makes an eight-by-eight boss possible on a
    sixteen-pixel panel: it is scenery, and the fight is in front of it.
    """
    frame = blank()
    level = world.level
    left = window_x(world.x, level.width)
    top = window_y(world.y, level.height)

    def place(cells, colour):
        for x, y in cells:
            put(frame, x - left, y - top, colour)

    if level.boss is not None:
        _draw_demon(frame, world, left, top, phase)

    for panel_x in range(WIDTH):
        x = left + panel_x
        if not 0 <= x < level.width:
            continue
        for panel_y in range(HEIGHT):
            y = top + panel_y
            if not 0 <= y < level.height or (x, y) in world.crumbled:
                continue
            if level.static_solid(x, y):
                put(frame, panel_x, panel_y, tile_colour(level, (x, y), phase))

    # One-way platforms are not solid, so the floor pass above skips
    # them. They are drawn here, with the other tiles you pass through.
    place(level.one_way, ONE_WAY)
    place(level.ladders, LADDER)
    place(level.updrafts, pulse(UPDRAFT, UPDRAFT_DIM, phase))
    if world.blinks_on():
        place(level.blinks, BLINK_ON)
    place(world.mover_cells(), MOVER)
    place(level.spikes, SPIKE)
    place(level.portals, pulse(PORTAL, PORTAL_DIM, phase))
    place(world.coins, COIN)

    goal_colour = (
        pulse(GOAL_OPEN, GOAL_OPEN_DIM, phase) if world.goal_open else GOAL_SHUT
    )
    place([level.goal], goal_colour)

    place(world.enemy_cells(), ENEMY)
    place(world.fireball_cells(), FIREBALL)
    place(world.fist_cells(), FIST)
    place([world.pixel], PLAYER)

    return bytes(frame)


def _draw_demon(frame: bytearray, world: World, left: int, top: int, phase: int):
    """The eight-by-eight demon, dim, behind everything else.

    It goes on before the level does, so any tile drawn over it wins. A
    boss that occupies a quarter of the panel can only work as a
    backdrop; drawn in front it would be the level.
    """
    if world.boss_done:
        return
    origin_x, origin_y = world.level.boss_origin
    body = DEMON_BODY[world.level.boss.hue]
    eyes = pulse(DEMON_EYE, DEMON_EYE_DIM, phase) if world.boss_fighting else DEMON_EYE_DIM
    throwing = bool(world.fireball_cells())

    for y, row in enumerate(bosses.DEMON):
        for x, cell in enumerate(row):
            if cell != "#":
                continue
            colour = body
            if (x, y) in bosses.DEMON_EYES:
                colour = eyes
            elif (x, y) in bosses.DEMON_MOUTH and throwing:
                colour = DEMON_MOUTH
            put(frame, origin_x + x - left, origin_y + y - top, colour)


def draw_menu(selected: int, phase: int = 0) -> bytes:
    """The title screen: three icons — play, levels, settings."""
    frame = blank()
    for index, (icon, (left, top)) in enumerate(MENU_ICONS):
        chosen = index == selected
        colour = MENU_SELECTED if chosen else MENU_IDLE
        span = [left + dx for dx, _ in icon]
        for dx, dy in icon:
            put(frame, left + dx, top + dy, colour)
        if chosen:
            # A marker under the icon, so the choice is legible even
            # where the two greens are hard to tell apart.
            centre = (min(span) + max(span)) // 2
            put(frame, centre, MENU_MARKER_ROW, MENU_MARKER)
            put(frame, centre + 1, MENU_MARKER_ROW, MENU_MARKER)
    return bytes(frame)


# -- the settings screen ---------------------------------------------------

#: Loudness bars: one slot per level, filled up to the setting.
SETTINGS_BAR_LEFT = 5
SETTINGS_BAR_SLOTS = 8  # == sound_settings.MAX_LEVEL
SETTINGS_MUSIC_ROW = 2
SETTINGS_FX_ROW = 6
SETTINGS_TUNE_ROW = 10
MUSIC_BAR = (255, 190, 0)
FX_BAR = (0, 200, 255)
EMPTY_SLOT = (36, 36, 36)
SETTINGS_ROWS = 3  # music, effects, tune


def _bar(frame: bytearray, top: int, level: int, colour: tuple) -> None:
    for slot in range(SETTINGS_BAR_SLOTS):
        lit = slot < level
        for dy in (0, 1):
            put(
                frame,
                SETTINGS_BAR_LEFT + slot,
                top + dy,
                colour if lit else EMPTY_SLOT,
            )


def draw_settings(music: int, effects: int, tune: int, row: int, phase: int = 0) -> bytes:
    """Two loudness bars and the tune number, with the chosen row marked."""
    frame = blank()
    _bar(frame, SETTINGS_MUSIC_ROW, music, MUSIC_BAR)
    _bar(frame, SETTINGS_FX_ROW, effects, FX_BAR)
    for x, y in font.pixels(str(tune), SETTINGS_BAR_LEFT, SETTINGS_TUNE_ROW):
        put(frame, x, y, MENU_SELECTED)

    marker_top = (SETTINGS_MUSIC_ROW, SETTINGS_FX_ROW, SETTINGS_TUNE_ROW)[row]
    put(frame, 1, marker_top, MENU_MARKER)
    put(frame, 1, marker_top + 1, MENU_MARKER)
    return bytes(frame)


def draw_picker(index: int, completed: Iterable, count: int, phase: int = 0) -> bytes:
    """A pixel per level, and the number of the one under the cursor."""
    if count > PICKER_CAPACITY:
        raise ValueError(
            f"the picker holds {PICKER_CAPACITY} levels, not {count} -- "
            "another row would reach the level number"
        )
    frame = blank()
    done = set(completed)

    for level_index in range(count):
        x = level_index % PICKER_COLUMNS
        y = (level_index // PICKER_COLUMNS) * PICKER_ROW_PITCH
        colour = TILE_DONE if level_index in done else TILE_TODO
        if level_index == index:
            colour = pulse(CURSOR, colour, phase)
        put(frame, x, y, colour)

    label = str(index + 1)
    left = (WIDTH - font.text_width(label)) // 2
    for x, y in font.pixels(label, left, NUMBER_TOP):
        put(frame, x, y, NUMBER)

    return bytes(frame)
