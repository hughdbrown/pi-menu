"""The Game of Life controls, with no window attached.

Every control -- start, stop, reset, random, clear, and editing a single
cell -- pushes a fresh frame to the panel. That is the whole point of
this class: the rule lives in one place and is tested against a real
frame server, rather than being spread across Tk callbacks where it can
only be verified by looking at the LEDs.

The Tk app owns the widgets and the timer; this owns the board, the
seed, and what the panel is currently showing.
"""

from __future__ import annotations

import random
from typing import Callable

from ..display.protocol import FRAME_BYTES, pixel_offset
from ..palette import DEFAULT_COLOUR, PALETTE
from .board import Board

#: Called with a complete framebuffer whenever the panel should change.
Sink = Callable[[bytes], None]

EMPTY_NOTE = "board is empty — draw some cells or press Random"
SETTLED_NOTE = "settled — no further change"


def default_mirroring(has_panel: bool) -> bool:
    """Whether the window should follow the simulation by default.

    With a panel attached the panel is the display, so the window need
    not race it. With no panel the window is all there is.
    """
    return not has_panel


def grid_should_rest(running: bool, mirroring: bool) -> bool:
    """True when the on-screen grid should stop following the board.

    Only while it is actually running: a stopped board still has to be
    visible, because that is when you draw on it.
    """
    return running and not mirroring


class LifeSession:
    """Board, seed and panel state for one run of the game."""

    def __init__(
        self,
        sink: Sink,
        wrap: bool = True,
        colour: str = DEFAULT_COLOUR,
        rng: random.Random | None = None,
    ) -> None:
        self.board = Board(wrap=wrap)
        self.colour = colour
        self.running = False
        self.note: str | None = None

        self._sink = sink
        self._rng = rng
        # The pattern Reset returns to. Hand edits and Random update it;
        # stepping does not, so Reset always rewinds to what you set up.
        self.seed = self.board.snapshot()

        self.push()

    # -- controls --------------------------------------------------------

    def start(self) -> bool:
        """Begin running. False if there is nothing alive to run."""
        if self.board.population == 0:
            self.running = False
            self.note = EMPTY_NOTE
            self.push()
            return False
        self.running = True
        self.note = None
        self.push()
        return True

    def stop(self) -> None:
        self.running = False
        self.push()

    def reset(self) -> None:
        """Rewind to generation 0 of the current seed and pause."""
        self.running = False
        self.note = None
        self.board.restore(self.seed)
        self.push()

    def randomize(self, density: float = 0.3) -> None:
        self.board.randomize(density, rng=self._rng)
        self.seed = self.board.snapshot()
        self.note = None
        self.push()

    def clear(self) -> None:
        self.running = False
        self.board.clear()
        self.seed = self.board.snapshot()
        self.note = None
        self.push()

    def set_cell(self, x: int, y: int, alive: bool) -> bool:
        """Set one cell by hand. False if it already had that value.

        Hand edits become the new seed, so Reset replays what you drew
        rather than whatever came before it.
        """
        if not self.board.in_bounds(x, y) or self.board.get(x, y) == alive:
            return False
        self.board.set(x, y, alive)
        self.seed = self.board.snapshot()
        self.note = None
        self.push()
        return True

    def step(self) -> bool:
        """Advance one generation. False once the board has settled."""
        changed = self.board.step()
        if not changed:
            self.running = False
            self.note = SETTLED_NOTE
        self.push()
        return changed

    def set_colour(self, colour: str) -> None:
        self.colour = colour
        self.push()

    # -- output ----------------------------------------------------------

    @property
    def rgb(self) -> tuple[int, int, int]:
        return PALETTE[self.colour]

    def framebuffer(self) -> bytes:
        """The frame the panel should currently be showing."""
        buf = bytearray(FRAME_BYTES)
        colour = bytes(self.rgb)
        for x, y in self.board.live_cells():
            offset = pixel_offset(x, y)
            buf[offset : offset + 3] = colour
        return bytes(buf)

    def push(self) -> None:
        """Send the current board to the panel."""
        self._sink(self.framebuffer())

    def status_text(self) -> str:
        state = "running" if self.running else "stopped"
        text = (
            f"generation {self.board.generation}  ·  "
            f"population {self.board.population}  ·  {state}"
        )
        if self.note:
            text += f"  ·  {self.note}"
        return text
