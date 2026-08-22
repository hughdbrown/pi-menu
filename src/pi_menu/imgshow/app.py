"""Tk front-end for picking an image file and showing it on the panel.

Pick a file, and the 16x16 result appears in an enlarged preview and on
the Stellar Unicorn at the same time. Changing the scale mode or
brightness re-renders both, so the preview is always what the panel is
actually showing.
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from ..display import add_display_args, open_display
from ..display.protocol import FRAME_BYTES, HEIGHT, WIDTH
from ..display.pump import FramePump
from ..palette import BG, FG, GRID_LINE, MUTED, PANEL_BG, to_hex
from .loader import (
    SUPPORTED_EXTENSIONS,
    Frame,
    ScaleMode,
    apply_brightness,
    load_frames,
    pixels,
    prepare,
    to_framebuffer,
)

PREVIEW_CELL = 22

FILE_TYPES = [
    ("Images", " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)),
    ("PNG", "*.png"),
    ("JPEG", "*.jpg *.jpeg"),
    ("GIF", "*.gif"),
    ("All files", "*"),
]


class ImageShowApp:
    """Chooses an image file and mirrors it to the panel."""

    def __init__(self, root: tk.Tk, pump: FramePump, start_path: str | None = None):
        self.root = root
        self.pump = pump

        self.frames: list[Frame] = []
        self.path: Path | None = None
        self._frame_index = 0
        self._after_id: str | None = None

        self.scale_mode = tk.StringVar(value=ScaleMode.FIT.value)
        self.brightness = tk.IntVar(value=int(pump.display.brightness * 100))
        self.animate = tk.BooleanVar(value=True)
        self._status = tk.StringVar(value="No image loaded.")
        self._filename = tk.StringVar(value="—")

        self._build_ui()
        if start_path:
            self.load(Path(start_path))

    # -- construction ----------------------------------------------------

    def _build_ui(self) -> None:
        self.root.title("Image Shower — Stellar Unicorn")
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
        style.configure("TRadiobutton", background=BG, foreground=FG)
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.configure("TButton", padding=(10, 6))

        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        size = WIDTH * PREVIEW_CELL
        self.canvas = tk.Canvas(
            outer,
            width=size,
            height=size,
            bg=PANEL_BG,
            highlightthickness=1,
            highlightbackground=GRID_LINE,
        )
        self.canvas.grid(row=0, column=0, rowspan=2, sticky="nw")

        self._rects = []
        for y in range(HEIGHT):
            for x in range(WIDTH):
                x0, y0 = x * PREVIEW_CELL, y * PREVIEW_CELL
                self._rects.append(
                    self.canvas.create_rectangle(
                        x0,
                        y0,
                        x0 + PREVIEW_CELL,
                        y0 + PREVIEW_CELL,
                        fill=PANEL_BG,
                        width=0,
                    )
                )

        controls = ttk.Frame(outer, padding=(14, 0, 0, 0))
        controls.grid(row=0, column=1, sticky="new")
        controls.columnconfigure(0, weight=1)

        ttk.Button(controls, text="Choose image…", command=self.choose).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Label(controls, textvariable=self._filename, style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )

        ttk.Label(controls, text="Scale", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", pady=(12, 0)
        )
        for offset, mode in enumerate(ScaleMode):
            ttk.Radiobutton(
                controls,
                text=mode.label,
                value=mode.value,
                variable=self.scale_mode,
                command=self.render,
            ).grid(row=3 + offset, column=0, sticky="w")

        ttk.Label(controls, text="Brightness (%)", style="Muted.TLabel").grid(
            row=7, column=0, sticky="w", pady=(12, 0)
        )
        scale = ttk.Scale(
            controls,
            from_=5,
            to=100,
            orient="horizontal",
            command=self._on_brightness,
        )
        scale.set(self.brightness.get())
        scale.grid(row=8, column=0, sticky="ew")

        self._animate_box = ttk.Checkbutton(
            controls,
            text="Animate (GIF)",
            variable=self.animate,
            command=self._on_animate_toggle,
        )
        self._animate_box.grid(row=9, column=0, sticky="w", pady=(12, 0))
        self._animate_box.state(["disabled"])

        ttk.Button(controls, text="Blank panel", command=self.blank).grid(
            row=10, column=0, sticky="ew", pady=(12, 0)
        )
        ttk.Button(controls, text="Quit", command=self.quit).grid(
            row=11, column=0, sticky="ew", pady=(4, 0)
        )

        ttk.Label(outer, textvariable=self._status, style="Muted.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

    # -- loading ---------------------------------------------------------

    def choose(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self.root, title="Choose an image", filetypes=FILE_TYPES
        )
        if chosen:
            self.load(Path(chosen))

    def load(self, path: Path) -> None:
        self._stop_animation()
        try:
            self.frames = load_frames(path, animate=True)
        except FileNotFoundError:
            self._status.set(f"No such file: {path}")
            return
        except Exception as exc:  # noqa: BLE001 - any decode failure is user-facing
            self._status.set(f"Could not read {path.name}: {exc}")
            return

        self.path = path
        self._frame_index = 0
        self._filename.set(_ellipsize(path.name))
        self._animate_box.state(["!disabled"] if len(self.frames) > 1 else ["disabled"])
        self.render()

    # -- rendering -------------------------------------------------------

    def render(self) -> None:
        """Draw the current frame to the preview and the panel."""
        self._stop_animation()
        if not self.frames:
            self._status.set("No image loaded.")
            return

        if self.animate.get() and len(self.frames) > 1:
            self._show_frame(self._frame_index)
            self._schedule_next()
        else:
            self._frame_index = 0
            self._show_frame(0)
        self._update_status()

    def _show_frame(self, index: int) -> None:
        frame = self.frames[index]
        small = apply_brightness(
            prepare(frame.image, ScaleMode(self.scale_mode.get())),
            self.brightness.get() / 100.0,
        )
        for rect, rgb in zip(self._rects, pixels(small)):
            self.canvas.itemconfig(rect, fill=to_hex(rgb))
        self.pump.submit(to_framebuffer(small))
        self._check_pump()

    def _schedule_next(self) -> None:
        duration = self.frames[self._frame_index].duration_ms
        self._after_id = self.root.after(duration, self._advance)

    def _advance(self) -> None:
        self._after_id = None
        if not self.frames or not self.animate.get():
            return
        self._frame_index = (self._frame_index + 1) % len(self.frames)
        self._show_frame(self._frame_index)
        self._update_status()
        self._schedule_next()

    def _stop_animation(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    # -- controls --------------------------------------------------------

    def _on_animate_toggle(self) -> None:
        self._frame_index = 0
        self.render()

    def _on_brightness(self, value: str) -> None:
        self.brightness.set(int(float(value)))
        # Brightness is baked into the pixels rather than sent as a panel
        # command, so the preview and the LEDs dim by the same amount.
        if self.frames:
            self._show_frame(self._frame_index)

    def blank(self) -> None:
        self._stop_animation()
        for rect in self._rects:
            self.canvas.itemconfig(rect, fill=PANEL_BG)
        self.pump.submit(bytes(FRAME_BYTES))
        self._status.set("Panel blanked.")

    def quit(self) -> None:
        self._stop_animation()
        self.root.destroy()

    # -- status ----------------------------------------------------------

    def _update_status(self) -> None:
        if not self.path:
            return
        source = self.frames[self._frame_index].image
        text = (
            f"{self.path.name}  ·  {source.width}x{source.height} → {WIDTH}x{HEIGHT}"
        )
        if len(self.frames) > 1:
            text += f"  ·  frame {self._frame_index + 1}/{len(self.frames)}"
        self._status.set(text)

    def _check_pump(self) -> None:
        error = self.pump.error
        if error is not None:
            self._status.set(f"display stopped: {error}")


def _ellipsize(name: str, limit: int = 28) -> str:
    return name if len(name) <= limit else name[: limit - 1] + "…"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pi-imgshow",
        description="Show an image file on a 16x16 Stellar Unicorn.",
    )
    parser.add_argument(
        "image",
        nargs="?",
        help="image to open at startup (otherwise use the file chooser)",
    )
    add_display_args(parser)
    args = parser.parse_args(argv)

    display = open_display(args.backend, args.port, args.brightness)
    pump = FramePump(display)
    try:
        root = tk.Tk()
        ImageShowApp(root, pump, start_path=args.image)
        root.mainloop()
    finally:
        pump.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
