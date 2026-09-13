"""The placed-furnace smelting simulation.

The furnace has three single-item slots -- fuel, input, output -- and a
heat/smelting state that advances every frame whether the UI is open or
not. It mirrors the HTML furnace exactly: fuel burns faster as heat rises,
heat drifts down to an idle floor while fuel is present, and smelting
progress regresses if heat stays below a recipe's requirement for too long.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from . import tiles
from .inventory import Stack

FUEL_UNITS = {tiles.WOOD: 4, tiles.COAL: 8}


class Recipe(NamedTuple):
    input_kind: int
    heat: int
    time_ms: float
    output_kind: int


SMELT_RECIPES = {
    tiles.CLAY: Recipe(tiles.CLAY, 1, 1000, tiles.BRICK),
    tiles.COBBLESTONE: Recipe(tiles.COBBLESTONE, 1, 1000, tiles.STONE),
    tiles.COPPER_ORE: Recipe(tiles.COPPER_ORE, 3, 5000, tiles.COPPER),
    tiles.IRON_ORE: Recipe(tiles.IRON_ORE, 5, 10000, tiles.IRON),
    tiles.TUNGSTEN_ORE: Recipe(tiles.TUNGSTEN_ORE, 7, 10000, tiles.TUNGSTEN),
}

HEAT_MAX = 10
HEAT_IDLE_FLOOR = 1
HEAT_IDLE_DECAY_PER_SEC = 1 / 4
HEAT_NOFUEL_DECAY_PER_SEC = 1
OXYGEN_BOOST = 1
FUEL_UNITS_PER_SEC_PER_HEAT = 0.15
SMELT_GRACE_MS = 2000
SMELT_REGRESS_STAGE_MS = 2000


class Furnace:
    """One global furnace, matching the HTML's single state machine."""

    def __init__(self) -> None:
        self.fuel_slot: Optional[Stack] = None
        self.item_slot: Optional[Stack] = None
        self.output_slot: Optional[Stack] = None
        self.heat = 0.0
        self.fuel_type: Optional[int] = None
        self.fuel_units_left = 0.0
        self.progress_ms = 0.0
        self.below_ms = 0.0

    def update(self, dt_ms: float) -> None:
        """Advance fuel/heat/smelting by ``dt_ms`` milliseconds."""
        if self.fuel_units_left <= 0:
            stack = self.fuel_slot
            if stack is not None and stack.kind in FUEL_UNITS:
                self.fuel_type = stack.kind
                self.fuel_units_left = FUEL_UNITS[stack.kind]
                stack.count -= 1
                if stack.count <= 0:
                    self.fuel_slot = None
            else:
                self.fuel_type = None

        has_fuel = self.fuel_units_left > 0
        if has_fuel:
            if self.heat > HEAT_IDLE_FLOOR:
                self.heat = max(HEAT_IDLE_FLOOR, self.heat - HEAT_IDLE_DECAY_PER_SEC * dt_ms / 1000)
            self.fuel_units_left = max(0.0, self.fuel_units_left - FUEL_UNITS_PER_SEC_PER_HEAT * self.heat * dt_ms / 1000)
        else:
            self.heat = max(0.0, self.heat - HEAT_NOFUEL_DECAY_PER_SEC * dt_ms / 1000)

        input_stack = self.item_slot
        recipe = SMELT_RECIPES.get(input_stack.kind) if input_stack is not None else None
        output_stack = self.output_slot
        room_for_output = (
            recipe is not None
            and (
                output_stack is None
                or (output_stack.kind == recipe.output_kind and output_stack.count < tiles.stack_max_for(recipe.output_kind))
            )
        )

        if recipe is not None and room_for_output:
            if self.heat >= recipe.heat:
                self.below_ms = 0.0
                self.progress_ms = min(recipe.time_ms, self.progress_ms + dt_ms)
                if self.progress_ms >= recipe.time_ms:
                    input_stack.count -= 1
                    if input_stack.count <= 0:
                        self.item_slot = None
                    if output_stack is None:
                        self.output_slot = Stack(recipe.output_kind, 1)
                    else:
                        output_stack.count += 1
                    self.progress_ms = 0.0
            elif self.progress_ms > 0:
                self.below_ms += dt_ms
                if self.below_ms > SMELT_GRACE_MS:
                    self.progress_ms = max(0.0, self.progress_ms - (recipe.time_ms / 4) * dt_ms / SMELT_REGRESS_STAGE_MS)
        else:
            self.progress_ms = 0.0
            self.below_ms = 0.0

    def press_oxygen(self) -> None:
        """Pump the fire hotter, but only while fuel is actually burning."""
        if self.fuel_units_left <= 0:
            return
        self.heat = min(HEAT_MAX, self.heat + OXYGEN_BOOST)

    @property
    def input_recipe(self) -> Optional[Recipe]:
        stack = self.item_slot
        return SMELT_RECIPES.get(stack.kind) if stack is not None else None

    @property
    def progress_fraction(self) -> float:
        recipe = self.input_recipe
        if recipe is None:
            return 0.0
        return self.progress_ms / recipe.time_ms

    @property
    def heat_fraction(self) -> float:
        return self.heat / HEAT_MAX

    def empty_back_to(self, inventory) -> list:
        """Return fuel, input and output stacks to ``inventory``; leftovers to drop."""
        leftovers = []
        for slot in (self.fuel_slot, self.item_slot, self.output_slot):
            if slot is not None:
                left = inventory.take_back(slot)
                if left is not None:
                    leftovers.append(left)
        self.fuel_slot = None
        self.item_slot = None
        self.output_slot = None
        self.fuel_type = None
        self.fuel_units_left = 0.0
        self.progress_ms = 0.0
        self.below_ms = 0.0
        self.heat = 0.0
        return leftovers
