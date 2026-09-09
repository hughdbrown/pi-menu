"""Painting the world and every screen onto the 16x16 canvas.

The view is eight blocks square at two pixels a block. The background
layer is drawn first and darkened by half, the front layer over it
with sky left open so the background shows through gaps, then waves,
clouds, the player, rain, lightning, the crack on whatever is being
broken, dropped items and the hotbar along the bottom row.

The inventory, bench and table screens are laid out to match the hit
tests in :mod:`pi_menu.microcraft.inventory`, which is the only reason
their pixel positions are what they are.
"""

from __future__ import annotations

import math
from typing import Optional

from ..display.protocol import HEIGHT, WIDTH
from . import palette, tiles
from .canvas import Canvas
from .inventory import (
    BACKPACK,
    CRAFT,
    HOTBAR,
    INV_COLS,
    INV_ROWS,
    OUTPUT,
    TABLE,
    TABLE_OUTPUT,
    Inventory,
)
from .player import BLOCK, COLS, PLAYER_COLOUR, ROWS, Breaker, Drops, Player
from .sky import draw_sky
from .terrain import BACK, FRONT, World
from .weather import CLOUD_MAX_Y, Weather

VIEW = WIDTH

FIRE_FRAME_MS = 150
BLINK_MS = 400
BOB_MS = 500

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BACKGROUND_SHADE = 0.5

# -- the opening screen -----------------------------------------------------------

#: g: gameplay shows through; p: grey panel; b: the button's slot.
MENU_ROWS = (
    "gggggggggggggggg",
    "gggggggggggggggg",
    "gggggggggggggggg",
    "gggggggggggggggg",
    "gggppppppppppggg",
    "gggpbbbbbbbbpggg",
    "gggpbbbbbbbbpggg",
    "gggpbbbbbbbbpggg",
    "gggppppppppppggg",
    "gggppppppppppggg",
    "gggppppppppppggg",
    "gggppppppppppggg",
    "gggggggggggggggg",
    "gggggggggggggggg",
    "gggggggggggggggg",
    "gggggggggggggggg",
)
PANEL_COLOUR = (112, 112, 112)
BTN_X, BTN_Y, BTN_W, BTN_H = 4, 5, 8, 3
#: The play button, 8x3; None lets the panel show through.
BTN_PIXELS = (
    ((121, 241, 230), (109, 241, 230), (9, 125, 23), None, None, None, (72, 72, 72), (78, 78, 78)),
    ((91, 241, 224), (106, 241, 229), (9, 130, 23), None, (83, 59, 28), (75, 55, 25), (78, 78, 78), (70, 70, 70)),
    ((94, 241, 225), None, (9, 125, 23), (9, 130, 23), (74, 54, 25), (83, 59, 28), None, (78, 78, 78)),
)


def point_in_button(cx: int, cy: int) -> bool:
    return BTN_X <= cx < BTN_X + BTN_W and BTN_Y <= cy < BTN_Y + BTN_H


def draw_menu(canvas: Canvas) -> None:
    for y, row in enumerate(MENU_ROWS):
        for x, cell in enumerate(row):
            if cell != "g":
                canvas.set(x, y, PANEL_COLOUR)
    for py, row in enumerate(BTN_PIXELS):
        for px, rgb in enumerate(row):
            if rgb is not None:
                canvas.set(BTN_X + px, BTN_Y + py, rgb)


# -- helpers ---------------------------------------------------------------------


def ui_tile(canvas: Canvas, src_x: int, dx: int, dy: int) -> None:
    canvas.tile(palette.UI_SHEET, src_x, 0, dx, dy)


def slot_tile(canvas: Canvas, dx: int, dy: int) -> None:
    """An empty slot, in the hue its position on the panel gives it."""
    canvas.tile(palette.slot_tile(dx, dy), 0, 0, dx, dy)


def item_tile(canvas: Canvas, kind: int, dx: int, dy: int) -> None:
    """A block or item at 2x2; items sit on their slot's tile."""
    sheet, sx, sy, mirrored = palette.tile_art(kind)
    if kind in tiles.ITEMS:
        slot_tile(canvas, dx, dy)
    canvas.tile(sheet, sx, sy, dx, dy, mirrored)


def blinking(now_ms: float) -> bool:
    return math.floor(now_ms / BLINK_MS) % 2 == 0


def _fire_overlay(canvas: Canvas, dx: int, dy: int, now_ms: float) -> None:
    frame = math.floor(now_ms / FIRE_FRAME_MS) % 4
    canvas.tile(palette.FIRE_SHEET, frame * 2, 0, dx, dy)


# -- the world ---------------------------------------------------------------------


def draw_layers(canvas: Canvas, world: World, cam_x: int, cam_y: int, now_ms: float) -> None:
    """Background dimmed by half, then the front at full brightness."""
    burning = world.burning
    for layer, shade in ((BACK, True), (FRONT, False)):
        for ry in range(ROWS):
            wy = cam_y + ry
            for rx in range(COLS):
                wx = cam_x + rx
                kind = world.get(layer, wx, wy)
                if kind == tiles.SKY:
                    continue
                sheet, sx, sy, mirrored = palette.tile_art(kind)
                dx, dy = rx * BLOCK, ry * BLOCK
                canvas.tile(sheet, sx, sy, dx, dy, mirrored)
                if (layer, wx, wy) in burning:
                    _fire_overlay(canvas, dx, dy, now_ms)
                if shade:
                    canvas.rect(dx, dy, BLOCK, BLOCK, BLACK, BACKGROUND_SHADE)


def draw_player(canvas: Canvas, player: Player, cam_x: int, cam_y: int) -> None:
    psx = math.floor((player.x - cam_x) * BLOCK + 0.5)
    psy = math.floor((player.y - cam_y) * BLOCK + 0.5)
    canvas.rect(psx, psy, BLOCK, BLOCK, PLAYER_COLOUR)


def draw_break_overlay(
    canvas: Canvas, breaker: Breaker, world: World, inventory: Inventory,
    active_layer: int, cam_x: int, cam_y: int,
) -> None:
    if breaker.key is None or breaker.key[0] != active_layer:
        return
    _, wx, wy = breaker.key
    rx, ry = wx - cam_x, wy - cam_y
    if not (0 <= rx < COLS and 0 <= ry < ROWS):
        return
    frame = min(3, math.floor(breaker.fraction(world, inventory) * 4))
    canvas.tile(palette.BREAK_SHEET, frame * 2, 0, rx * BLOCK, ry * BLOCK)


def draw_drops(canvas: Canvas, drops: Drops, cam_x: int, cam_y: int, now_ms: float) -> None:
    bob_up = math.floor(now_ms / BOB_MS) % 2 == 0
    for d in drops.items:
        rx = d.x - cam_x
        ry = math.floor(d.y + 0.5) - cam_y
        if not (0 <= rx < COLS and 0 <= ry < ROWS):
            continue
        bob = 0 if (not d.landed or bob_up) else 1
        canvas.set(rx * BLOCK, math.floor((d.y - cam_y) * BLOCK + 0.5) + bob, palette.AVERAGE_COLOUR[d.kind])


def draw_hotbar(canvas: Canvas, inventory: Inventory, now_ms: float) -> None:
    """Eight full-resolution slots along the bottom block row."""
    blink = blinking(now_ms)
    dy = VIEW - BLOCK
    for i in range(8):
        dx = i * BLOCK
        stack = inventory.hotbar[i]
        if i == inventory.selected and blink:
            canvas.rect(dx, dy, BLOCK, BLOCK, WHITE)
        elif stack is not None:
            item_tile(canvas, stack.kind, dx, dy)
        else:
            slot_tile(canvas, dx, dy)


def draw_world(
    canvas: Canvas,
    world: World,
    weather: Weather,
    cam_x: int,
    cam_y: int,
    *,
    sky_frac: float,
    moon_phase: float,
    stars: list,
    now_ms: float,
    ref_y: float,
    player: Optional[Player] = None,
    breaker: Optional[Breaker] = None,
    inventory: Optional[Inventory] = None,
    drops: Optional[Drops] = None,
    active_layer: int = FRONT,
) -> None:
    """The whole scene. With no player this is the opening screen's demo."""
    draw_sky(canvas, sky_frac, moon_phase, stars, now_ms / 1000.0, weather.celestial_visibility)
    below_clouds = ref_y >= CLOUD_MAX_Y + 10
    weather.draw_overcast(canvas, below_clouds)
    draw_layers(canvas, world, cam_x, cam_y, now_ms)
    weather.draw_waves(canvas, cam_x, cam_y, now_ms / 1000.0)
    weather.draw_clouds(canvas, cam_x, cam_y)
    if player is not None:
        draw_player(canvas, player, cam_x, cam_y)
        weather.draw_rain(canvas, cam_x, cam_y)
        weather.draw_bolts(canvas, cam_x, cam_y)
        if breaker is not None and inventory is not None:
            draw_break_overlay(canvas, breaker, world, inventory, active_layer, cam_x, cam_y)
        if drops is not None:
            draw_drops(canvas, drops, cam_x, cam_y, now_ms)
        if inventory is not None:
            draw_hotbar(canvas, inventory, now_ms)
    weather.draw_flash(canvas)


# -- the screens -------------------------------------------------------------------


def _slot(canvas: Canvas, inventory: Inventory, group: str, index: int, dx: int, dy: int, blink: bool) -> None:
    stack = inventory.get(group, index)
    if inventory.selection == (group, index) and blink:
        canvas.rect(dx, dy, 2, 2, WHITE)
    elif stack is not None:
        item_tile(canvas, stack.kind, dx, dy)
    else:
        slot_tile(canvas, dx, dy)


def _backpack_and_hotbar(canvas: Canvas, inventory: Inventory, top: int, blink: bool) -> None:
    for row in range(INV_ROWS):
        for col in range(INV_COLS):
            _slot(canvas, inventory, BACKPACK, row * INV_COLS + col, col * 2, top + row * 2, blink)
    for col in range(8):
        _slot(canvas, inventory, HOTBAR, col, col * 2, 14, blink)


def _quantity_dots(canvas: Canvas, x0: int, y0: int, cols: int, count: Optional[int]) -> None:
    """Sixteen dots, one lit per item held; a plain patch when nothing is."""
    rows = 16 // cols
    if count is None:
        canvas.rect(x0, y0, cols, rows, palette.UI_BG_COLOUR)
        return
    for i in range(16):
        canvas.set(x0 + i % cols, y0 + i // cols, WHITE if i < count else palette.UI_BG_COLOUR)


def _held_count(inventory: Inventory) -> Optional[int]:
    if inventory.selection is None:
        return None
    held = inventory.get(*inventory.selection)
    return min(held.count, tiles.STACK_MAX) if held is not None else 0


def draw_inventory(canvas: Canvas, inventory: Inventory, now_ms: float) -> None:
    """Armour row, bench and exit buttons, quantity dots, backpack, hotbar."""
    blink = blinking(now_ms)
    canvas.fill(BLACK)
    for i in range(4):
        slot_tile(canvas, i * 2, 0)
    for i in range(2):
        ui_tile(canvas, tiles.UI_BG_X, 8 + i * 2, 0)
    canvas.tile(palette.CRAFT_BUTTON, 0, 0, 12, 0)
    ui_tile(canvas, tiles.UI_EXIT_X, 14, 0)
    _quantity_dots(canvas, 0, 2, 8, _held_count(inventory))
    for i in range(4):
        ui_tile(canvas, tiles.UI_BG_X, 8 + i * 2, 2)
    for row in range(INV_ROWS):
        for col in range(INV_COLS):
            _slot(canvas, inventory, BACKPACK, row * INV_COLS + col, col * 2, 4 + row * 2, blink)
    for i in range(8):
        ui_tile(canvas, tiles.UI_BG_X, i * 2, 12)
    for col in range(8):
        _slot(canvas, inventory, HOTBAR, col, col * 2, 14, blink)


def _crafting_screen(
    canvas: Canvas, inventory: Inventory, now_ms: float,
    grid_group: str, grid_cols: int, grid_x: int, grid_y: int,
    output_group: str, output_x: int, recipe,
) -> None:
    blink = blinking(now_ms)
    canvas.fill(BLACK)
    for row in range(8):
        for col in range(8):
            ui_tile(canvas, tiles.UI_BG_X, col * 2, row * 2)
    slots = inventory._slots(grid_group)
    for index in range(len(slots)):
        row, col = divmod(index, grid_cols)
        _slot(canvas, inventory, grid_group, index, grid_x + col * 2, grid_y + row * 2, blink)

    output = inventory.get(output_group, 0)
    preview = recipe() if output is None else None
    if inventory.selection == (output_group, 0) and blink:
        canvas.rect(output_x, 2, 2, 2, WHITE)
    elif output is not None:
        item_tile(canvas, output.kind, output_x, 2)
    elif preview is not None:
        item_tile(canvas, preview.kind, output_x, 2)
    else:
        slot_tile(canvas, output_x, 2)

    ui_tile(canvas, tiles.UI_EXIT_X, 14, 0)
    count = _held_count(inventory)
    if count is None and preview is not None:
        count = preview.count
    _quantity_dots(canvas, 12, 2, 4, count)
    _backpack_and_hotbar(canvas, inventory, 6, blink)


def draw_bench(canvas: Canvas, inventory: Inventory, now_ms: float) -> None:
    _crafting_screen(canvas, inventory, now_ms, CRAFT, 2, 1, 1, OUTPUT, 8, inventory.bench_recipe)


def draw_table(canvas: Canvas, inventory: Inventory, now_ms: float) -> None:
    _crafting_screen(canvas, inventory, now_ms, TABLE, 3, 1, 0, TABLE_OUTPUT, 9, inventory.table_recipe)


def draw_cursor(canvas: Canvas, x: int, y: int) -> None:
    """Always last: invert the pixel so it shows on anything."""
    canvas.invert(x, y)
