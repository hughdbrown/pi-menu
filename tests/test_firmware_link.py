"""End-to-end test of the Pi/Pico link.

The real firmware from ``firmware/stellar_frame_server.py`` runs in a
thread with stubbed Pimoroni modules, connected to a pseudo-terminal.
:class:`SerialDisplay` opens the other end and talks to it exactly as it
would to a real panel, so a change to either side that breaks the
protocol fails here rather than on the bench.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import types
from pathlib import Path

import pytest

from pi_menu.display.protocol import FRAME_BYTES, pixel_offset
from pi_menu.display.serial_link import SerialDisplay

pytest.importorskip("serial")

FIRMWARE = Path(__file__).resolve().parents[1] / "firmware" / "stellar_frame_server.py"

pytestmark = pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="needs pseudo-terminals"
)


class FakeGraphics:
    """Stands in for PicoGraphics, recording what was drawn."""

    def __init__(self, display=None):
        self.display = display
        self.pen = (0, 0, 0)
        self.pixels: dict[tuple[int, int], tuple[int, int, int]] = {}

    def create_pen(self, r, g, b):
        return (r, g, b)

    def set_pen(self, pen):
        self.pen = pen

    def pixel(self, x, y):
        self.pixels[(x, y)] = self.pen

    def clear(self):
        self.pixels = {(x, y): self.pen for x in range(16) for y in range(16)}


class FakeUnicorn:
    """Stands in for StellarUnicorn."""

    def __init__(self):
        self.brightness = None
        self.updates = 0

    def set_brightness(self, value):
        self.brightness = value

    def update(self, graphics):
        self.updates += 1


def _install_stubs():
    picographics = types.ModuleType("picographics")
    picographics.PicoGraphics = FakeGraphics
    picographics.DISPLAY_STELLAR_UNICORN = "stellar"

    stellar = types.ModuleType("stellar")
    stellar.StellarUnicorn = FakeUnicorn

    sys.modules["picographics"] = picographics
    sys.modules["stellar"] = stellar


class PtyReader:
    """The firmware's stdin, with a way to break it out of a blocking read.

    Closing a pty master while another thread sits in ``read()`` on it
    hangs, so teardown closes the slave first -- which makes the read
    return end-of-file -- and this wrapper then raises to end the loop.
    """

    def __init__(self, fd):
        self._file = os.fdopen(fd, "rb", buffering=0)
        self.stopped = threading.Event()

    def read(self, count):
        if self.stopped.is_set():
            raise OSError("link closed")
        data = self._file.read(count)
        if self.stopped.is_set():
            raise OSError("link closed")
        return data

    def close(self):
        self._file.close()


@pytest.fixture
def pico():
    """A running firmware instance and the serial path that reaches it."""
    _install_stubs()

    spec = importlib.util.spec_from_file_location("stellar_frame_server", FIRMWARE)
    firmware = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(firmware)  # __name__ is not __main__, so run() waits

    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)

    reader = PtyReader(master_fd)
    writer = os.fdopen(os.dup(master_fd), "wb", buffering=0)
    firmware._stdin = reader
    firmware._stdout = writer

    def serve():
        try:
            firmware.run()
        except (OSError, ValueError, IndexError):
            pass  # the link went away at teardown

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    try:
        yield firmware, slave_path
    finally:
        reader.stopped.set()
        _close_quietly(lambda: os.close(slave_fd))  # EOF unblocks the reader
        thread.join(timeout=2.0)
        if not thread.is_alive():
            # Only safe to close the master once nobody is reading it.
            _close_quietly(reader.close)
            _close_quietly(writer.close)
        for name in ("picographics", "stellar"):
            sys.modules.pop(name, None)


def _close_quietly(action):
    try:
        action()
    except OSError:
        pass


def test_the_handshake_identifies_the_panel(pico):
    _, path = pico
    display = SerialDisplay(port=path)
    try:
        assert display.port == path
    finally:
        display.close()


def test_a_frame_arrives_pixel_for_pixel(pico):
    firmware, path = pico
    display = SerialDisplay(port=path)
    try:
        display.set_pixel(0, 0, 255, 0, 0)
        display.set_pixel(15, 15, 0, 0, 255)
        display.set_pixel(7, 3, 10, 20, 30)
        display.show()

        assert firmware.graphics.pixels[(0, 0)] == (255, 0, 0)
        assert firmware.graphics.pixels[(15, 15)] == (0, 0, 255)
        assert firmware.graphics.pixels[(7, 3)] == (10, 20, 30)
        assert firmware.graphics.pixels[(1, 1)] == (0, 0, 0)
    finally:
        display.close()


def test_the_pi_and_the_pico_agree_on_which_byte_is_which_pixel(pico):
    """Catches a row/column transposition, the classic panel bug."""
    firmware, path = pico
    display = SerialDisplay(port=path)
    try:
        frame = bytearray(FRAME_BYTES)
        # x=2, y=5 -- deliberately not on the diagonal.
        offset = pixel_offset(2, 5)
        frame[offset : offset + 3] = bytes((99, 88, 77))
        display.set_frame(bytes(frame))
        display.show()

        assert firmware.graphics.pixels[(2, 5)] == (99, 88, 77)
        assert firmware.graphics.pixels[(5, 2)] == (0, 0, 0)
    finally:
        display.close()


def test_successive_frames_are_all_drawn(pico):
    firmware, path = pico
    display = SerialDisplay(port=path)
    try:
        before = firmware.unicorn.updates
        for value in range(1, 6):
            display.set_pixel(0, 0, value, value, value)
            display.show()
        assert firmware.unicorn.updates - before == 5
        assert firmware.graphics.pixels[(0, 0)] == (5, 5, 5)
    finally:
        display.close()


def test_brightness_reaches_the_panel_as_a_fraction(pico):
    firmware, path = pico
    display = SerialDisplay(port=path, brightness=0.25)
    try:
        assert firmware.unicorn.brightness == pytest.approx(0.25, abs=0.01)

        display.set_brightness(1.0)
        assert firmware.unicorn.brightness == pytest.approx(1.0, abs=0.01)
    finally:
        display.close()


def test_closing_blanks_the_panel(pico):
    firmware, path = pico
    display = SerialDisplay(port=path)
    display.set_pixel(4, 4, 255, 255, 255)
    display.show()
    assert firmware.graphics.pixels[(4, 4)] == (255, 255, 255)

    display.close()

    # close() sends a clear; give the firmware thread a moment to act.
    import time

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if firmware.graphics.pixels.get((4, 4)) == (0, 0, 0):
            break
        time.sleep(0.01)
    assert firmware.graphics.pixels[(4, 4)] == (0, 0, 0)


def test_junk_on_the_wire_does_not_desynchronise_the_firmware(pico):
    """Line noise or a half-written frame must not wedge the panel."""
    firmware, path = pico
    display = SerialDisplay(port=path)
    try:
        display._serial.write(b"\x00garbage\xffSS")

        display.set_pixel(9, 9, 1, 2, 3)
        display.show()
        assert firmware.graphics.pixels[(9, 9)] == (1, 2, 3)
    finally:
        display.close()


def test_a_port_that_never_answers_is_rejected():
    from pi_menu.display.serial_link import StellarUnicornNotFound

    master_fd, slave_fd = os.openpty()
    try:
        with pytest.raises(StellarUnicornNotFound, match="did not answer"):
            SerialDisplay(port=os.ttyname(slave_fd), timeout=0.2)
    finally:
        os.close(master_fd)
        os.close(slave_fd)


def test_a_nonexistent_port_is_rejected(tmp_path):
    from pi_menu.display.serial_link import StellarUnicornNotFound

    with pytest.raises(StellarUnicornNotFound, match="could not open"):
        SerialDisplay(port=str(tmp_path / "ttyNOPE"))
