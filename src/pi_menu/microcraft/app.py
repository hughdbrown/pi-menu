"""Tk front-end for MicroCraft.

As with the platform game, the window is not the game: everything the
player looks at is on the LED panel. This holds the keyboard, runs a
20 Hz clock, and reports in words what the panel has no room for --
the block in hand, the layer being aimed at, the local time of day,
and whether the frames are reaching a real panel at all.
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from tkinter import ttk

from ..capture import save_frame
from ..display import add_display_args, open_display
from ..display.pump import FramePump
from ..palette import BG, FG, MUTED, WARN
from ..platformer.keys import HeldKeys
from .player import JUMP_KEY, LEFT, RIGHT
from .session import (
    BACK_KEY,
    BREAK,
    CURSOR_DOWN,
    CURSOR_LEFT,
    CURSOR_RIGHT,
    CURSOR_UP,
    DROP,
    HELD_KEYS,
    INVENTORY,
    LAYER,
    SELECT,
    TICK_MS,
    Session,
)

HELP = (
    "A / D walk  ·  W or Space jumps and swims up  ·  Arrows move the cursor\n"
    "Enter places, interacts, or presses what is under the cursor\n"
    "Hold Backspace to break the block under the cursor  ·  1–8 pick a hotbar slot\n"
    "E opens the inventory  ·  L aims at the front or the background layer\n"
    "Q three times drops one of what you hold  ·  Esc goes back  ·  C saves a PNG"
)

#: Tk keysym -> a key the session holds down until it is released.
HELD_KEYSYMS = {
    "a": LEFT, "A": LEFT,
    "d": RIGHT, "D": RIGHT,
    "w": JUMP_KEY, "W": JUMP_KEY, "space": JUMP_KEY,
    "BackSpace": BREAK,
}

#: Tk keysym -> a key the session acts on at once. Auto-repeat is welcome
#: here: a held arrow should keep moving the cursor.
TAP_KEYSYMS = {
    "Left": CURSOR_LEFT,
    "Right": CURSOR_RIGHT,
    "Up": CURSOR_UP,
    "Down": CURSOR_DOWN,
    "Return": SELECT,
    "KP_Enter": SELECT,
    "e": INVENTORY, "E": INVENTORY, "i": INVENTORY, "I": INVENTORY,
    "l": LAYER, "L": LAYER,
    "q": DROP, "Q": DROP,
    "Escape": BACK_KEY,
}

NOTE_TICKS = 60


class MicroCraftApp:
    """Holds the keyboard, runs the clock, and says what is happening."""

    def __init__(self, root: tk.Tk, pump: FramePump, seed: int | None = None) -> None:
        self.root = root
        self.pump = pump
        self.session = Session(pump.submit, seed=seed)
        self.keys = HeldKeys()
        self._after_id: str | None = None
        self._status = tk.StringVar()
        self._note: str | None = None
        self._note_ticks = 0
        self.brightness = tk.IntVar(value=int(pump.display.brightness * 100))
        self._build_ui()
        self._bind_keys()
        self._refresh()
        self._schedule()

    def _build_ui(self) -> None:
        self.root.title(f"MicroCraft — {self.pump.display.description}")
        self.root.configure(bg=BG)
        self.root.minsize(520, 260)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - theme availability varies
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Warn.TLabel", background=BG, foreground=WARN)
        style.configure("Title.TLabel", background=BG, foreground=FG, font=("", 15, "bold"))
        style.configure("TButton", padding=(10, 6))

        outer = ttk.Frame(self.root, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        ttk.Label(outer, text="MicroCraft", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=f"The world is on the panel. Keep this window focused to play.  Seed {self.session.seed}.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))
        ttk.Label(outer, textvariable=self._status, style="TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(outer, text=HELP, style="Muted.TLabel", justify="left").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )

        ttk.Label(outer, text="Brightness (%)", style="Muted.TLabel").grid(
            row=4, column=0, sticky="w", pady=(14, 0)
        )
        scale = ttk.Scale(
            outer, from_=5, to=100, orient="horizontal",
            command=self._on_brightness, takefocus=False,
        )
        scale.set(self.brightness.get())
        scale.grid(row=5, column=0, sticky="ew")

        panel = self.pump.display
        ttk.Label(
            outer,
            text=f"Output: {panel.description}",
            style="Muted.TLabel" if panel.is_panel else "Warn.TLabel",
        ).grid(row=8, column=0, sticky="w", pady=(12, 0))
        ttk.Button(outer, text="Quit", command=self.quit, takefocus=False).grid(
            row=9, column=0, sticky="e", pady=(12, 0)
        )

    def _bind_keys(self) -> None:
        self.root.bind("<KeyPress>", self._on_press)
        self.root.bind("<KeyRelease>", self._on_release)
        self.root.focus_set()

    # -- input -------------------------------------------------------------------

    def _on_press(self, event) -> None:
        sym = event.keysym
        if sym in ("c", "C"):
            self._capture()
            return
        if sym in HELD_KEYSYMS:
            key = HELD_KEYSYMS[sym]
            if self.keys.press(key):
                self.session.press(key)
                self._refresh()
            return
        if sym in TAP_KEYSYMS:
            self.session.press(TAP_KEYSYMS[sym])
            self._refresh()
            return
        if len(sym) == 1 and "1" <= sym <= "8":
            self.session.select_slot(int(sym) - 1)
            self._refresh()

    def _on_release(self, event) -> None:
        key = HELD_KEYSYMS.get(event.keysym)
        if key is not None:
            self.keys.release(key)

    def _capture(self) -> None:
        try:
            path = save_frame(self.session.framebuffer(), prefix="microcraft")
        except Exception as exc:  # noqa: BLE001 - a failed shot must not crash play
            self._show_note(f"capture failed: {exc}")
            return
        self._show_note(f"saved {path}")

    def _show_note(self, text: str) -> None:
        self._note = text
        self._note_ticks = NOTE_TICKS
        self._refresh()

    # -- the clock ---------------------------------------------------------------

    def _schedule(self) -> None:
        self._after_id = self.root.after(round(TICK_MS), self._tick)

    def _tick(self) -> None:
        self._after_id = None
        if self._note_ticks > 0:
            self._note_ticks -= 1
        for key in self.keys.settle():
            self.session.release(key)
        self.session.tick(TICK_MS)
        self._refresh()
        self._schedule()

    def _cancel_tick(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    # -- output ------------------------------------------------------------------

    def _refresh(self) -> None:
        error = self.pump.error
        if error is not None:
            self._status.set(f"panel stopped responding: {error}")
            return
        if self._note_ticks > 0:
            self._status.set(self._note)
            return
        self._status.set(self.session.status_text())

    def _on_brightness(self, value: str) -> None:
        self.brightness.set(int(float(value)))
        self.pump.set_brightness(self.brightness.get() / 100.0)

    def quit(self) -> None:
        self._cancel_tick()
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pi-microcraft",
        description="MicroCraft: a block-building world on the 16x16 Stellar Unicorn.",
    )
    add_display_args(parser)
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="world seed (default: a fresh random world each run)",
    )
    args = parser.parse_args(argv)

    display = open_display(args.backend, args.port, args.brightness)
    pump = FramePump(display)
    try:
        root = tk.Tk()
        MicroCraftApp(root, pump, seed=args.seed)
        root.mainloop()
    finally:
        pump.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
