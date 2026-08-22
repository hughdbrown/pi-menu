"""Tk front-end for Conway's Game of Life, mirrored to the Stellar Unicorn.

The window is the control surface: Start, Stop, Reset, Random and Clear,
plus a 16x16 grid you can paint by clicking and dragging. Every change is
pushed to the panel through a :class:`FramePump` so serial latency never
blocks the buttons.
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from tkinter import ttk

from ..display import add_display_args, open_display
from ..display.protocol import FRAME_BYTES, pixel_offset
from ..display.pump import FramePump
from ..palette import (
    BG,
    CELL_DEAD,
    DEFAULT_COLOUR,
    FG,
    GRID_LINE,
    MUTED,
    PALETTE,
    PANEL_BG,
    to_hex,
)
from .board import Board

CELL_PIXELS = 30
MIN_SPEED = 1
MAX_SPEED = 30
DEFAULT_SPEED = 8


class LifeApp:
    """Wires a :class:`Board` to a Tk window and an LED panel."""

    def __init__(self, root: tk.Tk, pump: FramePump, wrap: bool = True) -> None:
        self.root = root
        self.pump = pump
        self.board = Board(wrap=wrap)

        # The pattern Reset returns to. Hand edits and Random update it;
        # stepping does not, so Reset always rewinds to what you set up.
        self.seed = self.board.snapshot()

        self.running = False
        self._after_id: str | None = None
        self._paint_state: bool | None = None
        self._status = tk.StringVar()

        self.speed = tk.IntVar(value=DEFAULT_SPEED)
        self.density = tk.IntVar(value=30)
        self.colour = tk.StringVar(value=DEFAULT_COLOUR)
        self.brightness = tk.IntVar(value=int(pump.display.brightness * 100))

        self._build_ui()
        self._bind_keys()
        self.refresh()

    # -- construction ----------------------------------------------------

    def _build_ui(self) -> None:
        self.root.title("Conway's Game of Life — Stellar Unicorn")
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - theme availability varies
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("TButton", padding=(10, 6))
        style.configure("TScale", background=BG)

        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        size = self.board.width * CELL_PIXELS
        self.canvas = tk.Canvas(
            outer,
            width=size,
            height=size,
            bg=PANEL_BG,
            highlightthickness=1,
            highlightbackground=GRID_LINE,
        )
        self.canvas.grid(row=0, column=0, rowspan=2, sticky="nw")
        self.canvas.bind("<Button-1>", self._on_paint_start)
        self.canvas.bind("<B1-Motion>", self._on_paint_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_paint_end)

        self._rects = []
        for y in range(self.board.height):
            for x in range(self.board.width):
                x0, y0 = x * CELL_PIXELS, y * CELL_PIXELS
                self._rects.append(
                    self.canvas.create_rectangle(
                        x0 + 1,
                        y0 + 1,
                        x0 + CELL_PIXELS - 1,
                        y0 + CELL_PIXELS - 1,
                        fill=CELL_DEAD,
                        outline=GRID_LINE,
                    )
                )

        controls = ttk.Frame(outer, padding=(14, 0, 0, 0))
        controls.grid(row=0, column=1, sticky="new")

        self.start_button = ttk.Button(controls, text="Start", command=self.start)
        self.stop_button = ttk.Button(controls, text="Stop", command=self.stop)
        reset_button = ttk.Button(controls, text="Reset", command=self.reset)
        random_button = ttk.Button(controls, text="Random", command=self.randomize)
        clear_button = ttk.Button(controls, text="Clear", command=self.clear)

        for row, widget in enumerate(
            (
                self.start_button,
                self.stop_button,
                reset_button,
                random_button,
                clear_button,
            )
        ):
            widget.grid(row=row, column=0, sticky="ew", pady=3)
        controls.columnconfigure(0, weight=1)

        self._slider(controls, 5, "Speed (gen/s)", self.speed, MIN_SPEED, MAX_SPEED)
        self._slider(controls, 7, "Random density (%)", self.density, 5, 70)
        self._slider(
            controls, 9, "Brightness (%)", self.brightness, 5, 100, self._on_brightness
        )

        ttk.Label(controls, text="Colour", style="Muted.TLabel").grid(
            row=11, column=0, sticky="w", pady=(10, 0)
        )
        picker = ttk.Combobox(
            controls,
            textvariable=self.colour,
            values=list(PALETTE),
            state="readonly",
            width=12,
        )
        picker.grid(row=12, column=0, sticky="ew")
        picker.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        ttk.Button(controls, text="Quit", command=self.quit).grid(
            row=13, column=0, sticky="ew", pady=(16, 0)
        )

        status = ttk.Label(outer, textvariable=self._status, style="Muted.TLabel")
        status.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        hint = ttk.Label(
            outer,
            text="Click or drag the grid to draw cells — it works while running too.",
            style="Muted.TLabel",
        )
        hint.grid(row=3, column=0, columnspan=2, sticky="w")

    def _slider(self, parent, row, label, variable, low, high, command=None) -> None:
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(
            row=row, column=0, sticky="w", pady=(10, 0)
        )

        def on_move(value: str) -> None:
            variable.set(int(float(value)))
            if command:
                command()

        scale = ttk.Scale(
            parent, from_=low, to=high, orient="horizontal", command=on_move
        )
        scale.set(variable.get())
        scale.grid(row=row + 1, column=0, sticky="ew")

    def _bind_keys(self) -> None:
        self.root.bind("<space>", lambda _e: self.toggle_running())
        self.root.bind("<n>", lambda _e: self.randomize())
        self.root.bind("<c>", lambda _e: self.clear())
        self.root.bind("<r>", lambda _e: self.reset())
        self.root.bind("<q>", lambda _e: self.quit())

    # -- controls --------------------------------------------------------

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._schedule()
        self.refresh()

    def stop(self) -> None:
        self.running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.refresh()

    def toggle_running(self) -> None:
        self.stop() if self.running else self.start()

    def reset(self) -> None:
        """Rewind to generation 0 of the current seed and pause."""
        self.stop()
        self.board.restore(self.seed)
        self.refresh()

    def randomize(self) -> None:
        self.board.randomize(self.density.get() / 100.0)
        self.seed = self.board.snapshot()
        self.refresh()

    def clear(self) -> None:
        self.stop()
        self.board.clear()
        self.seed = self.board.snapshot()
        self.refresh()

    def quit(self) -> None:
        self.stop()
        self.root.destroy()

    # -- painting --------------------------------------------------------

    def _cell_at(self, event) -> tuple[int, int] | None:
        x = int(self.canvas.canvasx(event.x)) // CELL_PIXELS
        y = int(self.canvas.canvasy(event.y)) // CELL_PIXELS
        return (x, y) if self.board.in_bounds(x, y) else None

    def _on_paint_start(self, event) -> None:
        cell = self._cell_at(event)
        if cell is None:
            return
        # Whatever the first cell becomes is what the whole drag paints,
        # so dragging never flickers cells on and off under the cursor.
        self._paint_state = not self.board.get(*cell)
        self._paint(cell)

    def _on_paint_drag(self, event) -> None:
        cell = self._cell_at(event)
        if cell is not None and self._paint_state is not None:
            self._paint(cell)

    def _on_paint_end(self, _event) -> None:
        self._paint_state = None

    def _paint(self, cell: tuple[int, int]) -> None:
        x, y = cell
        if self.board.get(x, y) == self._paint_state:
            return
        self.board.set(x, y, bool(self._paint_state))
        self.seed = self.board.snapshot()
        self.refresh()

    # -- the loop --------------------------------------------------------

    def _schedule(self) -> None:
        interval = max(1, round(1000 / max(MIN_SPEED, self.speed.get())))
        self._after_id = self.root.after(interval, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        if not self.running:
            return
        changed = self.board.step()
        self.refresh()
        if not changed:
            # A still life will never change again; stop burning frames.
            self.running = False
            self._set_status("settled — no further change")
            self.refresh()
            return
        self._schedule()

    # -- output ----------------------------------------------------------

    def refresh(self) -> None:
        """Redraw the Tk grid, push a frame, and update the status line."""
        rgb = PALETTE[self.colour.get()]
        alive_hex = to_hex(rgb)
        for y in range(self.board.height):
            for x in range(self.board.width):
                fill = alive_hex if self.board.get(x, y) else CELL_DEAD
                self.canvas.itemconfig(self._rects[y * self.board.width + x], fill=fill)

        self.pump.submit(self._framebuffer(rgb))
        self._set_status()
        self._sync_buttons()
        self._check_pump()

    def _framebuffer(self, rgb: tuple[int, int, int]) -> bytes:
        buf = bytearray(FRAME_BYTES)
        for x, y in self.board.live_cells():
            off = pixel_offset(x, y)
            buf[off : off + 3] = bytes(rgb)
        return bytes(buf)

    def _sync_buttons(self) -> None:
        self.start_button.state(["disabled"] if self.running else ["!disabled"])
        self.stop_button.state(["!disabled"] if self.running else ["disabled"])

    def _set_status(self, note: str | None = None) -> None:
        state = "running" if self.running else "stopped"
        text = (
            f"generation {self.board.generation}  ·  "
            f"population {self.board.population}  ·  {state}"
        )
        if note:
            text += f"  ·  {note}"
        self._status.set(text)

    def _on_brightness(self) -> None:
        self.pump.set_brightness(self.brightness.get() / 100.0)

    def _check_pump(self) -> None:
        error = self.pump.error
        if error is not None:
            self._set_status(f"display stopped: {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pi-life",
        description="Conway's Game of Life on a 16x16 Stellar Unicorn.",
    )
    parser.add_argument(
        "--no-wrap",
        action="store_true",
        help="treat the edges as dead instead of wrapping the grid",
    )
    add_display_args(parser)
    args = parser.parse_args(argv)

    display = open_display(args.backend, args.port, args.brightness)
    pump = FramePump(display)
    try:
        root = tk.Tk()
        LifeApp(root, pump, wrap=not args.no_wrap)
        root.mainloop()
    finally:
        pump.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
