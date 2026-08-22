"""Terminal backend: draws the panel in the terminal with ANSI colour.

Each text row shows two pixel rows using an upper-half block, so the
16x16 panel occupies 8 lines and stays roughly square on screen.
"""

from __future__ import annotations

import sys

from .base import Display
from .protocol import WIDTH, pixel_offset

_UPPER_HALF = "▀"
_RESET = "\033[0m"
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


class TerminalDisplay(Display):
    """Renders frames as coloured text. Useful with no hardware attached."""

    def __init__(self, brightness: float = 1.0, stream=None) -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._drawn = False
        super().__init__(brightness=brightness)
        self._stream.write(_HIDE_CURSOR)

    def _flush(self, framebuffer: bytes) -> None:
        rows = self.height // 2
        if self._drawn:
            # Step back over the previous frame so it redraws in place.
            self._stream.write(f"\033[{rows}A")
        self._stream.write(self._render(framebuffer))
        self._stream.flush()
        self._drawn = True

    def _render(self, framebuffer: bytes) -> str:
        scale = self._brightness
        out = []
        for y in range(0, self.height, 2):
            for x in range(WIDTH):
                top = _sample(framebuffer, x, y, scale)
                bottom = _sample(framebuffer, x, y + 1, scale)
                out.append(
                    f"\033[38;2;{top[0]};{top[1]};{top[2]}m"
                    f"\033[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m"
                    f"{_UPPER_HALF}"
                )
            out.append(_RESET + "\n")
        return "".join(out)

    def close(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.write(_RESET + _SHOW_CURSOR)
            self._stream.flush()
        except Exception:
            pass
        self._stream = None


def _sample(framebuffer: bytes, x: int, y: int, scale: float) -> tuple[int, int, int]:
    off = pixel_offset(x, y)
    return (
        int(framebuffer[off] * scale),
        int(framebuffer[off + 1] * scale),
        int(framebuffer[off + 2] * scale),
    )
