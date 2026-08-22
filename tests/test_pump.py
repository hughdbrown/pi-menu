import threading
import time

from pi_menu.display.base import Display
from pi_menu.display.null_ import NullDisplay
from pi_menu.display.protocol import FRAME_BYTES
from pi_menu.display.pump import FramePump


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def test_a_submitted_frame_reaches_the_display():
    pump = FramePump(NullDisplay())
    try:
        frame = bytes([7]) * FRAME_BYTES
        pump.submit(frame)
        assert wait_until(lambda: pump.display.last_frame == frame)
    finally:
        pump.close()


def test_only_the_newest_frame_survives_a_slow_display():
    """A backlog of stale frames is worse than dropping them."""

    class SlowDisplay(NullDisplay):
        def __init__(self):
            super().__init__()
            self.first_write = threading.Event()
            self.release = threading.Event()

        def _flush(self, framebuffer):
            super()._flush(framebuffer)
            if not self.first_write.is_set():
                self.first_write.set()
                self.release.wait(2.0)

    display = SlowDisplay()
    pump = FramePump(display)
    try:
        pump.submit(bytes([1]) * FRAME_BYTES)
        assert display.first_write.wait(2.0)

        # These pile up while the worker is stuck in the first write.
        for value in (2, 3, 4):
            pump.submit(bytes([value]) * FRAME_BYTES)
        display.release.set()

        assert wait_until(lambda: display.last_frame == bytes([4]) * FRAME_BYTES)
        # Frame 1 and frame 4 only — 2 and 3 were superseded before writing.
        assert len(display.frames) == 2
    finally:
        display.release.set()
        pump.close()


def test_a_backend_failure_is_reported_rather_than_raised():
    class BrokenDisplay(Display):
        def _flush(self, framebuffer):
            raise IOError("cable fell out")

    pump = FramePump(BrokenDisplay())
    try:
        pump.submit(bytes(FRAME_BYTES))
        assert wait_until(lambda: pump.error is not None)
        assert "cable fell out" in str(pump.error)
    finally:
        pump.close()


def test_close_stops_the_worker_and_closes_the_display():
    closed = []

    class ClosingDisplay(NullDisplay):
        def close(self):
            closed.append(True)

    pump = FramePump(ClosingDisplay())
    pump.close()

    assert closed == [True]
    assert not pump._thread.is_alive()
