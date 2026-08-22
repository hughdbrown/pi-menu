"""Null backend: accepts frames and discards them. Used by the tests."""

from __future__ import annotations

from .base import Display


class NullDisplay(Display):
    """Records how many frames were pushed but draws nothing."""

    def __init__(self, brightness: float = 1.0) -> None:
        self.frames: list[bytes] = []
        super().__init__(brightness=brightness)

    def _flush(self, framebuffer: bytes) -> None:
        self.frames.append(framebuffer)

    @property
    def last_frame(self) -> bytes | None:
        return self.frames[-1] if self.frames else None
