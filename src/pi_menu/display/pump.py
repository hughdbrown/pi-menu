"""Pushes frames to a display from a background thread.

A serial write plus its acknowledgement takes tens of milliseconds. Doing
that on Tk's main loop makes buttons feel stuck, so the UI hands frames
to this pump instead and returns immediately.

The pump keeps only the newest frame. If the UI outruns the panel the
intermediate frames are dropped rather than queued, which is what you
want for a live simulation -- a stale frame has no value once a newer
one exists.
"""

from __future__ import annotations

import threading

from .base import Display


class FramePump:
    """Owns a display and writes to it from one worker thread."""

    def __init__(self, display: Display) -> None:
        self._display = display
        self._lock = threading.Lock()
        self._pending_frame: bytes | None = None
        self._pending_brightness: float | None = None
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._run, name="frame-pump", daemon=True
        )
        self._thread.start()

    @property
    def display(self) -> Display:
        return self._display

    @property
    def error(self) -> BaseException | None:
        """The exception that stopped the worker, if one did."""
        with self._lock:
            return self._error

    def submit(self, framebuffer: bytes) -> None:
        """Queue a frame, replacing any frame not yet written."""
        with self._lock:
            self._pending_frame = framebuffer
        self._wake.set()

    def set_brightness(self, brightness: float) -> None:
        with self._lock:
            self._pending_brightness = brightness
        self._wake.set()

    def _run(self) -> None:
        while not self._stopping.is_set():
            self._wake.wait(0.1)
            self._wake.clear()

            with self._lock:
                frame, self._pending_frame = self._pending_frame, None
                brightness, self._pending_brightness = self._pending_brightness, None

            try:
                if brightness is not None:
                    self._display.set_brightness(brightness)
                if frame is not None:
                    self._display.set_frame(frame)
                    self._display.show()
            except BaseException as exc:  # noqa: BLE001 - reported to the UI
                with self._lock:
                    self._error = exc
                return

    def close(self) -> None:
        """Stop the worker and close the display."""
        self._stopping.set()
        self._wake.set()
        self._thread.join(timeout=2.0)
        self._display.close()
