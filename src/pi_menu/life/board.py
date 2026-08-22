"""Conway's Game of Life on a fixed grid. No I/O, no display, no Tk."""

from __future__ import annotations

import random
from typing import Iterator

DEFAULT_WIDTH = 16
DEFAULT_HEIGHT = 16


class Board:
    """A grid of live/dead cells that can advance one generation at a time.

    The grid wraps by default. On a board this small a non-wrapping edge
    kills gliders and most other travelling patterns within a few
    generations, so ``wrap=False`` is offered but not the default.
    """

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        wrap: bool = True,
    ) -> None:
        if width < 1 or height < 1:
            raise ValueError("board must be at least 1x1")
        self.width = width
        self.height = height
        self.wrap = wrap
        self._cells = bytearray(width * height)
        self.generation = 0

    # -- reading ---------------------------------------------------------

    def get(self, x: int, y: int) -> bool:
        """Is the cell at ``(x, y)`` alive? Off-grid cells are dead."""
        if not self.in_bounds(x, y):
            return False
        return bool(self._cells[y * self.width + x])

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def live_cells(self) -> Iterator[tuple[int, int]]:
        for y in range(self.height):
            row = y * self.width
            for x in range(self.width):
                if self._cells[row + x]:
                    yield x, y

    @property
    def population(self) -> int:
        return sum(self._cells)

    def neighbours(self, x: int, y: int) -> int:
        """Count the live cells among the eight around ``(x, y)``."""
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.wrap:
                    nx %= self.width
                    ny %= self.height
                elif not self.in_bounds(nx, ny):
                    continue
                count += self._cells[ny * self.width + nx]
        return count

    # -- writing ---------------------------------------------------------

    def set(self, x: int, y: int, alive: bool) -> None:
        if self.in_bounds(x, y):
            self._cells[y * self.width + x] = 1 if alive else 0

    def toggle(self, x: int, y: int) -> bool:
        """Flip one cell and return its new state."""
        if not self.in_bounds(x, y):
            return False
        idx = y * self.width + x
        self._cells[idx] ^= 1
        return bool(self._cells[idx])

    def clear(self) -> None:
        """Blank every cell and reset the generation counter."""
        self._cells[:] = bytes(len(self._cells))
        self.generation = 0

    def randomize(self, density: float = 0.3, rng: random.Random | None = None) -> None:
        """Fill the board randomly. ``density`` is the chance a cell is alive."""
        density = max(0.0, min(1.0, float(density)))
        source = rng or random
        self._cells[:] = bytes(
            1 if source.random() < density else 0 for _ in range(len(self._cells))
        )
        self.generation = 0

    # -- stepping --------------------------------------------------------

    def step(self) -> bool:
        """Advance one generation. Returns True if anything changed.

        A False return means the board has settled into a still life, and
        the caller can stop the timer instead of redrawing the same frame.
        """
        nxt = bytearray(len(self._cells))
        for y in range(self.height):
            row = y * self.width
            for x in range(self.width):
                n = self.neighbours(x, y)
                alive = self._cells[row + x]
                nxt[row + x] = 1 if (n == 3 or (alive and n == 2)) else 0

        changed = nxt != self._cells
        self._cells[:] = nxt
        self.generation += 1
        return changed

    # -- snapshots -------------------------------------------------------

    def snapshot(self) -> bytes:
        """Capture the current cells, for a later :meth:`restore`."""
        return bytes(self._cells)

    def restore(self, snapshot: bytes) -> None:
        """Put back a snapshot and rewind the generation counter to zero."""
        if len(snapshot) != len(self._cells):
            raise ValueError(
                f"snapshot is {len(snapshot)} cells, board is {len(self._cells)}"
            )
        self._cells[:] = snapshot
        self.generation = 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return NotImplemented
        return (
            self.width == other.width
            and self.height == other.height
            and self._cells == other._cells
        )

    def __repr__(self) -> str:
        return (
            f"Board({self.width}x{self.height}, wrap={self.wrap}, "
            f"gen={self.generation}, pop={self.population})"
        )
