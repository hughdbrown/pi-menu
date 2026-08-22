"""The display interface every backend shares.

Backends differ only in where a finished frame goes, so the pixel
bookkeeping lives here once and each backend implements ``_flush``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .protocol import FRAME_BYTES, HEIGHT, WIDTH, pixel_offset


class Display(ABC):
    """A 16x16 RGB matrix.

    Drawing calls mutate an in-memory framebuffer; nothing reaches the
    hardware until :meth:`show`.
    """

    width = WIDTH
    height = HEIGHT

    def __init__(self, brightness: float = 1.0) -> None:
        self._buf = bytearray(FRAME_BYTES)
        self._brightness = 1.0
        self.set_brightness(brightness)

    # -- drawing ---------------------------------------------------------

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        """Set one pixel. Coordinates outside the panel are ignored."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        off = pixel_offset(x, y)
        self._buf[off] = _clamp_byte(r)
        self._buf[off + 1] = _clamp_byte(g)
        self._buf[off + 2] = _clamp_byte(b)

    def clear(self) -> None:
        """Blank the framebuffer. Call :meth:`show` to push it."""
        self._buf[:] = bytes(FRAME_BYTES)

    def set_frame(self, framebuffer: bytes) -> None:
        """Replace the whole framebuffer at once."""
        if len(framebuffer) != FRAME_BYTES:
            raise ValueError(
                f"framebuffer must be {FRAME_BYTES} bytes, got {len(framebuffer)}"
            )
        self._buf[:] = framebuffer

    @property
    def framebuffer(self) -> bytes:
        return bytes(self._buf)

    # -- output ----------------------------------------------------------

    def show(self) -> None:
        """Push the current framebuffer to the backend."""
        self._flush(bytes(self._buf))

    def set_brightness(self, brightness: float) -> None:
        """Set brightness as a 0.0-1.0 fraction."""
        self._brightness = max(0.0, min(1.0, float(brightness)))
        self._apply_brightness(self._brightness)

    @property
    def brightness(self) -> float:
        return self._brightness

    @property
    def description(self) -> str:
        """Where frames are going, in words fit for a title bar."""
        return type(self).__name__

    @property
    def is_panel(self) -> bool:
        """True only when this really is the Stellar Unicorn."""
        return False

    def close(self) -> None:
        """Release any resources. Safe to call more than once."""

    def __enter__(self) -> "Display":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- backend hooks ---------------------------------------------------

    @abstractmethod
    def _flush(self, framebuffer: bytes) -> None:
        """Send a complete frame to wherever this backend puts frames."""

    def _apply_brightness(self, brightness: float) -> None:
        """Backends that control brightness in hardware override this."""


def _clamp_byte(value: int) -> int:
    return max(0, min(255, int(value)))
