"""End-to-end tests of the Pi/Pico link.

The ``pico`` fixture in conftest.py runs the real firmware against a
pseudo-terminal, so a change to either side that breaks the protocol
fails here rather than on the bench.
"""

from __future__ import annotations

import os

import pytest

from pi_menu.display import protocol as proto
from pi_menu.display.protocol import FRAME_BYTES, pixel_offset
from pi_menu.display.serial_link import SerialDisplay

pytest.importorskip("serial")

pytestmark = pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="needs pseudo-terminals"
)


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


def test_the_handshake_reports_the_firmware_protocol_version(pico):
    _, path = pico
    display = SerialDisplay(port=path)
    try:
        assert display.firmware_version == proto.PROTOCOL_VERSION
        assert display.firmware_is_current
    finally:
        display.close()


def test_frame_data_containing_the_interrupt_byte_survives(pico):
    """MicroPython reads 0x03 as Ctrl-C and swallows it.

    Any pixel with a channel value of 3 puts that byte on the wire. If
    the firmware has not disabled the interrupt character the byte is
    dropped, every following pixel shifts, and the panel fills with
    garbage before the server dies outright.
    """
    firmware, path = pico
    display = SerialDisplay(port=path)
    try:
        for y in range(16):
            for x in range(16):
                display.set_pixel(x, y, 3, 3, 3)
        display.show()

        assert firmware.graphics.pixels[(0, 0)] == (3, 3, 3)
        assert firmware.graphics.pixels[(15, 15)] == (3, 3, 3)
    finally:
        display.close()


def test_no_command_byte_is_the_interrupt_character():
    """Defence in depth: a Pico on old firmware should not be killed."""
    commands = (proto.CMD_PING, proto.CMD_BLIT, proto.CMD_BRIGHTNESS, proto.CMD_CLEAR)
    assert proto.INTERRUPT_CHAR not in commands
    assert proto.INTERRUPT_CHAR not in proto.encode_clear()
    assert proto.INTERRUPT_CHAR not in proto.encode_ping()


def test_the_firmware_disables_the_keyboard_interrupt_at_startup():
    """The one line that keeps binary frames from killing the server."""
    from conftest import FIRMWARE

    assert "micropython.kbd_intr(-1)" in FIRMWARE.read_text()


def test_holding_the_a_button_offers_an_escape_to_the_repl():
    """kbd_intr(-1) removes Ctrl-C, so there has to be another way out."""
    from conftest import load_firmware

    firmware = load_firmware()
    assert firmware.escape_requested() is False

    firmware.unicorn.pressed = True
    assert firmware.escape_requested() is True


def test_the_escape_check_happens_before_the_interrupt_is_disabled():
    from conftest import FIRMWARE

    source = FIRMWARE.read_text()
    assert source.index("escape_requested()") < source.index("micropython.kbd_intr(-1)")
