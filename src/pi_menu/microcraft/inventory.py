"""What the player carries, and how it is moved about and crafted.

Eight hotbar slots and a backpack of thirty-two, each empty or a stack.
The inventory screens are driven by one cursor and one button, so a
slot is *selected* with a first press and *moved* with a second: onto
an empty slot, swapping with a different kind, merging with the same
kind. Two quick presses on the selected stack arm a split, and the next
press halves it into the destination.

Crafting works the same way. Ingredients sit in the bench's 2x2 or the
table's 3x3 grid; the output slot shows what they would make and, when
picked from, makes it and consumes them right then. Anything left in a
grid when its screen closes goes back to the inventory, and what will
not fit is handed back to the caller to drop on the ground.

Screen layouts live here beside the click handling, since a hit test
and the painter that draws the thing it tests must agree.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from . import tiles
from .tiles import (
    BRICK, CLAY, COAL, COBBLESTONE, COPPER, COPPER_AXE, COPPER_PICKAXE, COPPER_SWORD,
    CRAFTING_TABLE, DIRT, FURNACE, GRASS, IRON, IRON_AXE, IRON_PICKAXE, IRON_SWORD,
    LEAF, SAND, STICK, STONE, STONE_AXE, STONE_PICKAXE, STONE_SWORD, WOOD, WOOD_PLANKS,
    BUCKET_EMPTY,
)

HOTBAR_SIZE = 8
INV_COLS = 8
INV_ROWS = 4
INV_SIZE = INV_COLS * INV_ROWS
CRAFT_SIZE = 4
TABLE_CRAFT_SIZE = 9

#: Slot groups, named as the HTML names them.
HOTBAR = "hotbar"
BACKPACK = "inv"
CRAFT = "craft"
OUTPUT = "output"
TABLE = "tableCraft"
TABLE_OUTPUT = "tableOutput"

#: Two presses this close together on the selected stack arm a split.
DOUBLE_TAP_MS = 350


class Stack:
    """A kind and a count. Mutable, because counts change in place."""

    __slots__ = ("kind", "count")

    def __init__(self, kind: int, count: int) -> None:
        self.kind = kind
        self.count = count

    def __repr__(self) -> str:
        return f"Stack({tiles.NAMES.get(self.kind, self.kind)} x{self.count})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Stack) and (self.kind, self.count) == (other.kind, other.count)


class Recipe(NamedTuple):
    kind: int
    count: int
    #: Parallel to the input grid: how many to take from each slot.
    consume: tuple


STARTER_HOTBAR = (
    (GRASS, 5), (DIRT, 16), (STONE, 16), (WOOD, 8),
    (LEAF, 8), (COBBLESTONE, 16), (BRICK, 16),
)
STARTER_BACKPACK = (
    (STICK, 6), (COAL, 8), (COPPER, 4), (IRON, 4),
    (IRON_SWORD, 1), (COPPER_SWORD, 1), (IRON_PICKAXE, 1), (COPPER_PICKAXE, 1),
    (IRON_AXE, 1), (COPPER_AXE, 1), (STONE_SWORD, 1), (STONE_PICKAXE, 1),
    (STONE_AXE, 1), (BUCKET_EMPTY, 1), (FURNACE, 4), (CLAY, 8), (SAND, 16),
)

# Stone tools, read row-major over the 3x3 table: C cobblestone, S stick,
# . must be empty. The axe is accepted either-handed.
STONE_TOOL_PATTERNS = (
    ("CCC.S..S.", STONE_PICKAXE),
    (".C..C..S.", STONE_SWORD),
    ("CC.CS..S.", STONE_AXE),
    (".CC.SC.S.", STONE_AXE),
)


class Inventory:
    """Every slot, the hotbar selection, and the cursor's held stack."""

    def __init__(self, starter_kit: bool = True) -> None:
        self.hotbar: list = [None] * HOTBAR_SIZE
        self.backpack: list = [None] * INV_SIZE
        self.craft: list = [None] * CRAFT_SIZE
        self.craft_output: list = [None]
        self.table: list = [None] * TABLE_CRAFT_SIZE
        self.table_output: list = [None]
        self.selected = 1
        #: ``(group, index)`` of the stack picked up on screen, or None.
        self.selection: Optional[tuple] = None
        self.split_armed = False
        self._last_tap = (0.0, None, -1)
        if starter_kit:
            for i, (kind, count) in enumerate(STARTER_HOTBAR):
                self.hotbar[i] = Stack(kind, count)
            for i, (kind, count) in enumerate(STARTER_BACKPACK):
                self.backpack[i] = Stack(kind, count)

    # -- the hotbar ------------------------------------------------------

    @property
    def held(self) -> Optional[Stack]:
        return self.hotbar[self.selected]

    def select_slot(self, index: int) -> None:
        """Empty slots cannot be selected."""
        if 0 <= index < HOTBAR_SIZE and self.hotbar[index] is not None:
            self.selected = index

    def drop_one_held(self) -> Optional[int]:
        """Take one of the held stack; the kind taken, or None."""
        held = self.held
        if held is None:
            return None
        held.count -= 1
        if held.count <= 0:
            self.hotbar[self.selected] = None
        return held.kind

    # -- slots by group ------------------------------------------------

    def _slots(self, group: str) -> list:
        return {
            HOTBAR: self.hotbar, BACKPACK: self.backpack, CRAFT: self.craft,
            OUTPUT: self.craft_output, TABLE: self.table, TABLE_OUTPUT: self.table_output,
        }[group]

    def get(self, group: str, index: int) -> Optional[Stack]:
        return self._slots(group)[index]

    def set(self, group: str, index: int, value: Optional[Stack]) -> None:
        self._slots(group)[index] = value

    # -- putting things in -----------------------------------------------

    def find_stack_with_room(self, kind: int) -> Optional[tuple]:
        limit = tiles.stack_max_for(kind)
        for group in (HOTBAR, BACKPACK):
            for i, s in enumerate(self._slots(group)):
                if s is not None and s.kind == kind and s.count < limit:
                    return group, i
        return None

    def find_empty_slot(self) -> Optional[tuple]:
        for group in (HOTBAR, BACKPACK):
            for i, s in enumerate(self._slots(group)):
                if s is None:
                    return group, i
        return None

    def pickup(self, kind: int) -> bool:
        """Add one; False, and nothing added, if there is no room."""
        where = self.find_stack_with_room(kind) or self.find_empty_slot()
        if where is None:
            return False
        group, i = where
        slots = self._slots(group)
        if slots[i] is None:
            slots[i] = Stack(kind, 0)
        slots[i].count += 1
        return True

    def add_items(self, kind: int, count: int) -> int:
        """Add up to ``count`` one at a time; how many actually went in."""
        added = 0
        while added < count and self.pickup(kind):
            added += 1
        return added

    def take_back(self, stack: Optional[Stack]) -> Optional[Stack]:
        """Return a stack to the inventory; whatever will not fit, or None."""
        if stack is None:
            return None
        added = self.add_items(stack.kind, stack.count)
        remaining = stack.count - added
        return Stack(stack.kind, remaining) if remaining > 0 else None

    def _empty_grid(self, slots: list) -> list:
        leftovers = []
        for i, stack in enumerate(slots):
            if stack is not None:
                left = self.take_back(stack)
                if left is not None:
                    leftovers.append(left)
                slots[i] = None
        return leftovers

    def close_bench(self) -> list:
        """Empty the 2x2 grid and output back home; leftovers to drop."""
        leftovers = self._empty_grid(self.craft)
        leftovers += self._empty_grid(self.craft_output)
        self.selection = None
        self.split_armed = False
        return leftovers

    def close_table(self) -> list:
        leftovers = self._empty_grid(self.table)
        leftovers += self._empty_grid(self.table_output)
        self.selection = None
        self.split_armed = False
        return leftovers

    def deselect(self) -> None:
        self.selection = None
        self.split_armed = False

    # -- moving things about -----------------------------------------------

    def slot_click(self, group: str, index: int, now_ms: float) -> None:
        """One press on a slot: select, put back, swap, merge, or split."""
        last_time, last_group, last_index = self._last_tap
        repeat = last_group == group and last_index == index and now_ms - last_time < DOUBLE_TAP_MS
        self._last_tap = (now_ms, group, index)

        slot = self.get(group, index)
        if self.selection is None:
            if slot is not None:
                self.selection = (group, index)
            self.split_armed = False
            return

        if self.selection == (group, index):
            if repeat:
                self.split_armed = True
            else:
                self.selection = None
                self.split_armed = False
            return

        if self.split_armed:
            self.split_stack(self.selection, (group, index))
            self.split_armed = False
            return

        from_group, from_index = self.selection
        held = self.get(from_group, from_index)
        dest = self.get(group, index)
        if held is not None and dest is not None and held.kind == dest.kind:
            total = held.count + dest.count
            merged = min(total, tiles.stack_max_for(held.kind))
            leftover = total - merged
            self.set(group, index, Stack(held.kind, merged))
            self.set(from_group, from_index, Stack(held.kind, leftover) if leftover > 0 else None)
        else:
            self.set(group, index, held)
            self.set(from_group, from_index, dest)
        self.selection = None
        self.split_armed = False

    def split_stack(self, source: tuple, dest: tuple) -> None:
        """Move half of the source onto the destination, up to its stack size."""
        held = self.get(*source)
        if held is None or held.count < 2:
            self.selection = None
            return
        there = self.get(*dest)
        if there is not None and there.kind != held.kind:
            self.selection = None
            return
        limit = tiles.stack_max_for(held.kind)
        half = held.count // 2
        remain = held.count - half
        dest_count = (there.count if there is not None else 0) + half
        overflow = 0
        if dest_count > limit:
            overflow = dest_count - limit
            dest_count = limit
        source_count = remain + overflow
        self.set(*dest, Stack(held.kind, dest_count) if dest_count > 0 else None)
        self.set(*source, Stack(held.kind, source_count) if source_count > 0 else None)
        self.selection = None

    # -- recipes -------------------------------------------------------------

    @staticmethod
    def match_shaped(slots4: list) -> Optional[Recipe]:
        """The 2x2 recipes: four planks make a table, two stacked make sticks."""
        if all(s is not None and s.kind == WOOD_PLANKS and s.count >= 1 for s in slots4):
            return Recipe(CRAFTING_TABLE, 1, (1, 1, 1, 1))
        tl, tr, bl, br = slots4
        if (
            tl is not None and tl.kind == WOOD_PLANKS
            and bl is not None and bl.kind == WOOD_PLANKS
            and tr is None and br is None
        ):
            return Recipe(STICK, 4, (1, 0, 1, 0))
        return None

    def bench_recipe(self) -> Optional[Recipe]:
        shaped = self.match_shaped(self.craft)
        if shaped is not None:
            return shaped
        for i, s in enumerate(self.craft):
            if s is not None and s.kind == WOOD:
                consume = [0] * CRAFT_SIZE
                consume[i] = 1
                return Recipe(WOOD_PLANKS, 4, tuple(consume))
        return None

    @staticmethod
    def _matches9(slots9: list, pattern: str) -> bool:
        for cell, s in zip(pattern, slots9):
            if cell == ".":
                if s is not None:
                    return False
            elif cell == "C":
                if s is None or s.kind != COBBLESTONE or s.count < 1:
                    return False
            elif cell == "S":
                if s is None or s.kind != STICK or s.count < 1:
                    return False
        return True

    def table_recipe(self) -> Optional[Recipe]:
        """Stone tools, then a log anywhere, then any 2x2 recipe shifted
        anywhere in the grid with the rest of it empty."""
        for pattern, kind in STONE_TOOL_PATTERNS:
            if self._matches9(self.table, pattern):
                return Recipe(kind, 1, tuple(0 if c == "." else 1 for c in pattern))
        for i, s in enumerate(self.table):
            if s is not None and s.kind == WOOD:
                consume = [0] * TABLE_CRAFT_SIZE
                consume[i] = 1
                return Recipe(WOOD_PLANKS, 4, tuple(consume))
        for r0 in (0, 1):
            for c0 in (0, 1):
                window = (r0 * 3 + c0, r0 * 3 + c0 + 1, (r0 + 1) * 3 + c0, (r0 + 1) * 3 + c0 + 1)
                if any(s is not None and i not in window for i, s in enumerate(self.table)):
                    continue
                match = self.match_shaped([self.table[i] for i in window])
                if match is not None:
                    consume = [0] * TABLE_CRAFT_SIZE
                    for k, i in enumerate(window):
                        consume[i] = match.consume[k]
                    return Recipe(match.kind, match.count, tuple(consume))
        return None

    def _output_click(self, grid: list, output: list, recipe_fn, group: str, now_ms: float) -> None:
        """Craft into the output slot on first pick-up, consuming then;
        after that the slot is an ordinary stack until it is put down."""
        if self.selection is not None:
            return
        if output[0] is None:
            recipe = recipe_fn()
            if recipe is None:
                return
            for i, amount in enumerate(recipe.consume):
                if amount > 0:
                    s = grid[i]
                    s.count -= amount
                    grid[i] = s if s.count > 0 else None
            output[0] = Stack(recipe.kind, recipe.count)
        self.slot_click(group, 0, now_ms)

    def bench_output_click(self, now_ms: float) -> None:
        self._output_click(self.craft, self.craft_output, self.bench_recipe, OUTPUT, now_ms)

    def table_output_click(self, now_ms: float) -> None:
        self._output_click(self.table, self.table_output, self.table_recipe, TABLE_OUTPUT, now_ms)

    # -- what is under the cursor on each screen -----------------------------

    @staticmethod
    def hit_inventory(px: int, py: int) -> tuple:
        """The main inventory screen: armour row, buttons, quantity dots,
        the backpack grid, a separator, and the hotbar."""
        if py <= 1:
            if px <= 7:
                return "armor", px // 2
            if px <= 11:
                return "bg", -1
            if px <= 13:
                return "openCraft", -1
            return "exit", -1
        if py <= 3:
            return ("qty" if px <= 7 else "bg"), -1
        if py <= 11:
            return BACKPACK, ((py - 4) // 2) * INV_COLS + px // 2
        if py <= 13:
            return "bg", -1
        return HOTBAR, px // 2

    @staticmethod
    def hit_bench(px: int, py: int) -> tuple:
        if 14 <= px <= 15 and 0 <= py <= 1:
            return "exit", -1
        if 12 <= px <= 15 and 2 <= py <= 5:
            return "qty", -1
        if 1 <= px <= 4 and 1 <= py <= 4:
            return CRAFT, ((py - 1) // 2) * 2 + (px - 1) // 2
        if 8 <= px <= 9 and 2 <= py <= 3:
            return OUTPUT, 0
        if 6 <= py <= 13:
            return BACKPACK, ((py - 6) // 2) * INV_COLS + px // 2
        if 14 <= py <= 15:
            return HOTBAR, px // 2
        return "bg", -1

    @staticmethod
    def hit_table(px: int, py: int) -> tuple:
        if 14 <= px <= 15 and 0 <= py <= 1:
            return "exit", -1
        if 1 <= px <= 6 and 0 <= py <= 5:
            return TABLE, (py // 2) * 3 + (px - 1) // 2
        if 9 <= px <= 10 and 2 <= py <= 3:
            return TABLE_OUTPUT, 0
        if 12 <= px <= 15 and 2 <= py <= 5:
            return "qty", -1
        if 6 <= py <= 13:
            return BACKPACK, ((py - 6) // 2) * INV_COLS + px // 2
        if 14 <= py <= 15:
            return HOTBAR, px // 2
        return "bg", -1

    # -- words ---------------------------------------------------------------

    def held_text(self) -> str:
        s = self.held
        return f"{tiles.NAMES[s.kind]} x{s.count}" if s is not None else "empty"
