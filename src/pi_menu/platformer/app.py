"""Tk front-end for the platform game.

The window is not the game. Everything the player looks at is on the LED
panel -- the menu, the level picker and the level itself -- so this holds
the keyboard focus, runs the clock, and reports in words the things the
panel has no room to say: which level is running, how many coins are
left, and whether the frames are reaching a real panel at all.

Frames go out through a :class:`~pi_menu.display.pump.FramePump`, so a
slow serial write never stalls the twenty-a-second tick.
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from tkinter import ttk

from ..display import add_display_args, open_display
from ..display.pump import FramePump
from ..palette import BG, FG, MUTED, WARN
from .keys import KEYSYMS, HeldKeys
from .session import PlatformSession
from .world import TICK_HZ

TICK_MS = round(1000 / TICK_HZ)

HELP = (
    "Arrow keys move and jump  ·  Enter chooses  ·  Esc goes back\n"
    "Collect every coin to open the goal, then reach it."
)


class PlatformApp:
    """Holds the keyboard, runs the clock, and says what is happening."""

    def __init__(self, root: tk.Tk, pump: FramePump) -> None:
        self.root = root
        self.pump = pump
        self.session = PlatformSession(pump.submit)
        self.keys = HeldKeys()

        self._after_id: str | None = None
        self._status = tk.StringVar()
        self.brightness = tk.IntVar(value=int(pump.display.brightness * 100))

        self._build_ui()
        self._bind_keys()
        self._refresh()
        self._schedule()

    # -- construction ----------------------------------------------------

    def _build_ui(self) -> None:
        self.root.title(f"Platform Game — {self.pump.display.description}")
        self.root.configure(bg=BG)
        self.root.minsize(460, 220)
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

        ttk.Label(outer, text="Platform Game", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text="The game is on the panel. Keep this window focused to play.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        ttk.Label(outer, textvariable=self._status, style="TLabel").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(outer, text=HELP, style="Muted.TLabel", justify="left").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )

        ttk.Label(outer, text="Brightness (%)", style="Muted.TLabel").grid(
            row=4, column=0, sticky="w", pady=(14, 0)
        )
        scale = ttk.Scale(
            outer, from_=5, to=100, orient="horizontal", command=self._on_brightness
        )
        scale.set(self.brightness.get())
        scale.grid(row=5, column=0, sticky="ew")

        # Which device is actually lighting up. A terminal preview looks
        # like a working program, so without this line there is nothing
        # on screen to say the panel is missing.
        panel = self.pump.display
        ttk.Label(
            outer,
            text=f"Output: {panel.description}",
            style="Muted.TLabel" if panel.is_panel else "Warn.TLabel",
        ).grid(row=6, column=0, sticky="w", pady=(12, 0))

        ttk.Button(outer, text="Quit", command=self.quit).grid(
            row=7, column=0, sticky="e", pady=(12, 0)
        )

    def _bind_keys(self) -> None:
        self.root.bind("<KeyPress>", self._on_press)
        self.root.bind("<KeyRelease>", self._on_release)
        self.root.focus_set()

    # -- input -----------------------------------------------------------

    def _on_press(self, event) -> None:
        key = KEYSYMS.get(event.keysym)
        if key is not None and self.keys.press(key):
            self.session.press(key)
            self._refresh()

    def _on_release(self, event) -> None:
        key = KEYSYMS.get(event.keysym)
        if key is not None:
            self.keys.release(key)

    # -- the clock -------------------------------------------------------

    def _schedule(self) -> None:
        self._after_id = self.root.after(TICK_MS, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        for key in self.keys.settle():
            self.session.release(key)
        self.session.tick()
        self._refresh()
        self._schedule()

    def _cancel_tick(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    # -- output ----------------------------------------------------------

    def _refresh(self) -> None:
        error = self.pump.error
        if error is not None:
            self._status.set(f"panel stopped responding: {error}")
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
        prog="pi-platformer",
        description="A platform game for the 16x16 Stellar Unicorn.",
    )
    add_display_args(parser)
    args = parser.parse_args(argv)

    display = open_display(args.backend, args.port, args.brightness)
    pump = FramePump(display)
    try:
        root = tk.Tk()
        PlatformApp(root, pump)
        root.mainloop()
    finally:
        pump.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
