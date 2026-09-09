"""A 16x16 drawing surface that knows how to blend.

The HTML leans on the browser canvas for translucency: sky gradients,
the sunrise glow, cloud particles drawn as soft radial blobs, storm
tints, the lightning flash, and a cursor that inverts what is under it.
The panel takes plain bytes, so this keeps float RGB per pixel, blends
in place, and hands out a framebuffer at the end.

Coordinates are canvas pixels (0..15); anything outside is ignored, as
a canvas would clip it.
"""

from __future__ import annotations

import math
from typing import Callable, Optional, Sequence

from ..display.protocol import HEIGHT, WIDTH

Colour = tuple[int, int, int]

SIZE = WIDTH * HEIGHT


class Canvas:
    """Float RGB pixels with alpha blending, sized for the panel."""

    __slots__ = ("px",)

    def __init__(self, colour: Colour = (0, 0, 0)) -> None:
        r, g, b = colour
        self.px = [float(r), float(g), float(b)] * SIZE

    # -- reading -----------------------------------------------------------

    def get(self, x: int, y: int) -> Colour:
        i = (y * WIDTH + x) * 3
        px = self.px
        return (_byte(px[i]), _byte(px[i + 1]), _byte(px[i + 2]))

    def to_bytes(self) -> bytes:
        return bytes(_byte(v) for v in self.px)

    # -- whole-canvas fills ----------------------------------------------

    def fill(self, colour: Colour, alpha: float = 1.0) -> None:
        if alpha >= 1.0:
            r, g, b = colour
            self.px[:] = [float(r), float(g), float(b)] * SIZE
            return
        self.rect(0, 0, WIDTH, HEIGHT, colour, alpha)

    def vertical_gradient(self, top: Colour, bottom: Colour) -> None:
        """Fill every row with the colour a linear gradient from the top
        edge to the bottom edge takes at that row's centre."""
        px = self.px
        for y in range(HEIGHT):
            t = (y + 0.5) / HEIGHT
            r = top[0] + (bottom[0] - top[0]) * t
            g = top[1] + (bottom[1] - top[1]) * t
            b = top[2] + (bottom[2] - top[2]) * t
            row = y * WIDTH * 3
            px[row : row + WIDTH * 3] = [r, g, b] * WIDTH

    # -- pixels and rectangles -------------------------------------------

    def set(self, x: int, y: int, colour: Colour, alpha: float = 1.0) -> None:
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT) or alpha <= 0.0:
            return
        i = (y * WIDTH + x) * 3
        px = self.px
        if alpha >= 1.0:
            px[i], px[i + 1], px[i + 2] = float(colour[0]), float(colour[1]), float(colour[2])
            return
        keep = 1.0 - alpha
        px[i] = px[i] * keep + colour[0] * alpha
        px[i + 1] = px[i + 1] * keep + colour[1] * alpha
        px[i + 2] = px[i + 2] * keep + colour[2] * alpha

    def rect(self, x: int, y: int, w: int, h: int, colour: Colour, alpha: float = 1.0) -> None:
        for yy in range(max(0, y), min(HEIGHT, y + h)):
            for xx in range(max(0, x), min(WIDTH, x + w)):
                self.set(xx, yy, colour, alpha)

    def invert(self, x: int, y: int) -> None:
        """What ``difference`` blending with white does: flip the pixel."""
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            return
        i = (y * WIDTH + x) * 3
        px = self.px
        px[i] = 255.0 - px[i]
        px[i + 1] = 255.0 - px[i + 1]
        px[i + 2] = 255.0 - px[i + 2]

    # -- sprites -----------------------------------------------------------

    def tile(
        self,
        sheet: Sequence[Sequence[Optional[Colour]]],
        sx: int,
        sy: int,
        dx: int,
        dy: int,
        mirrored: bool = False,
        alpha: float = 1.0,
    ) -> None:
        """Draw a 2x2 tile from a sheet; ``None`` pixels are transparent."""
        for oy in range(2):
            row = sheet[sy + oy]
            for ox in range(2):
                colour = row[sx + (1 - ox if mirrored else ox)]
                if colour is not None:
                    self.set(dx + ox, dy + oy, colour, alpha)

    # -- soft shapes -------------------------------------------------------

    def radial(
        self,
        cx: float,
        cy: float,
        radius: float,
        colour: Colour,
        alpha_at: Callable[[float], float],
        clip_to_disc: bool = True,
    ) -> None:
        """Blend a colour whose alpha is a function of distance / radius.

        Pixel centres inside the radius are blended with ``alpha_at(t)``
        for ``t`` in 0..1. With ``clip_to_disc`` false, pixels beyond the
        radius get ``alpha_at(1.0)``, which is what a canvas radial
        gradient does when it fills a whole rectangle.
        """
        if radius <= 0:
            return
        x0 = max(0, math.floor(cx - radius)) if clip_to_disc else 0
        x1 = min(WIDTH - 1, math.ceil(cx + radius)) if clip_to_disc else WIDTH - 1
        y0 = max(0, math.floor(cy - radius)) if clip_to_disc else 0
        y1 = min(HEIGHT - 1, math.ceil(cy + radius)) if clip_to_disc else HEIGHT - 1
        for y in range(y0, y1 + 1):
            dy = (y + 0.5) - cy
            for x in range(x0, x1 + 1):
                dx = (x + 0.5) - cx
                t = math.sqrt(dx * dx + dy * dy) / radius
                if t > 1.0:
                    if clip_to_disc:
                        continue
                    t = 1.0
                self.set(x, y, colour, alpha_at(t))

    def line(self, x0: float, y0: float, x1: float, y1: float, colour: Colour, alpha: float) -> None:
        """A one-pixel line, stepped along its longer axis."""
        steps = max(1, int(math.ceil(max(abs(x1 - x0), abs(y1 - y0)))))
        seen = set()
        for i in range(steps + 1):
            t = i / steps
            x = math.floor(x0 + (x1 - x0) * t)
            y = math.floor(y0 + (y1 - y0) * t)
            if (x, y) in seen:
                continue
            seen.add((x, y))
            self.set(x, y, colour, alpha)


def _byte(value: float) -> int:
    if value <= 0.0:
        return 0
    if value >= 255.0:
        return 255
    return int(value + 0.5)


def lerp_colour(a: Colour, b: Colour, t: float) -> Colour:
    """Round each channel, as the HTML does."""
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def hex_colour(text: str) -> Colour:
    text = text.lstrip("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
