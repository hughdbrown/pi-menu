"""Shared harness: the real Pico firmware, driven over a pseudo-terminal.

``pi_menu/firmware/stellar_frame_server.py`` is imported with the Pimoroni
modules stubbed and run in a thread, with a pty standing in for the USB
link. Anything that opens the resulting serial path is talking to the
actual firmware code, so the Pi and Pico halves are always tested
against each other rather than against a mock of one of them.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import types
from pathlib import Path

import pytest

FIRMWARE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "pi_menu"
    / "firmware"
    / "stellar_frame_server.py"
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
        self.pressed = False

    def set_brightness(self, value):
        self.brightness = value

    def update(self, graphics):
        self.updates += 1

    def is_pressed(self, switch):
        return self.pressed


class MicroPythonDriver:
    """Models how MicroPython's USB serial driver treats incoming bytes.

    On the rp2 port the driver watches every received byte for the
    interrupt character -- 0x03 by default -- and, on a match, swallows
    it and raises KeyboardInterrupt in whatever is running. A real pty
    does no such thing, so without this model the firmware's
    ``kbd_intr(-1)`` call could be deleted and the tests would not
    notice.
    """

    def __init__(self):
        self.interrupt_char = 0x03  # what the Pico boots with

    def kbd_intr(self, value):
        self.interrupt_char = value

    def receive(self, data: bytes) -> bytes:
        """Return what the script actually sees, or raise as the Pico would."""
        if self.interrupt_char < 0 or not data:
            return data
        marker = bytes([self.interrupt_char])
        if marker in data:
            raise KeyboardInterrupt("interrupt character received")
        return data


#: Shared so the reader and the firmware stub agree on the current state.
DRIVER = MicroPythonDriver()


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
        return DRIVER.receive(data)

    def close(self):
        self._file.close()


def install_stubs():
    picographics = types.ModuleType("picographics")
    picographics.PicoGraphics = FakeGraphics
    picographics.DISPLAY_STELLAR_UNICORN = "stellar"

    # Built into MicroPython, absent from CPython.
    micropython = types.ModuleType("micropython")
    micropython.driver = DRIVER
    micropython.kbd_intr = DRIVER.kbd_intr

    stellar = types.ModuleType("stellar")
    stellar.StellarUnicorn = type(
        "StellarUnicorn", (FakeUnicorn,), {"SWITCH_A": "a"}
    )

    sys.modules["micropython"] = micropython
    sys.modules["picographics"] = picographics
    sys.modules["stellar"] = stellar


def load_firmware():
    """Import the firmware fresh, as the Pico would at boot."""
    install_stubs()
    spec = importlib.util.spec_from_file_location("stellar_frame_server", FIRMWARE)
    firmware = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(firmware)  # __name__ is not __main__, so run() waits
    return firmware


def _close_quietly(action):
    try:
        action()
    except OSError:
        pass


@pytest.fixture
def pico():
    """A running firmware instance and the serial path that reaches it."""
    DRIVER.interrupt_char = 0x03  # every Pico starts this way
    firmware = load_firmware()
    assert firmware.boot() is True, "the firmware refused to start"

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
        except SystemExit:
            pass  # the host asked the server to quit for a re-flash

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
        for name in ("micropython", "picographics", "stellar"):
            sys.modules.pop(name, None)
