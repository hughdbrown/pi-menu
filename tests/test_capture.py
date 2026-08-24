"""Captures must look like the panel: big crisp squares, never a blur."""

from __future__ import annotations

import datetime

import pytest

from pi_menu.capture import save_frame, to_image
from pi_menu.display.protocol import FRAME_BYTES, pixel_offset


def frame_with(x, y, colour):
    buf = bytearray(FRAME_BYTES)
    offset = pixel_offset(x, y)
    buf[offset : offset + 3] = bytes(colour)
    return bytes(buf)


def test_one_led_becomes_one_solid_square():
    image = to_image(frame_with(3, 5, (255, 0, 0)), scale=10)

    assert image.size == (160, 160)
    # Every pixel of the LED's square is the LED's colour, corners included.
    assert image.getpixel((30, 50)) == (255, 0, 0)
    assert image.getpixel((39, 59)) == (255, 0, 0)
    assert image.getpixel((29, 50)) == (0, 0, 0)


def test_a_wrong_sized_frame_is_refused():
    with pytest.raises(ValueError, match="bytes"):
        to_image(b"\x00" * 10)


def test_a_capture_lands_where_it_is_pointed(tmp_path):
    path = save_frame(frame_with(0, 0, (0, 255, 0)), directory=tmp_path)

    assert path.parent == tmp_path
    assert path.suffix == ".png"
    assert path.stat().st_size > 0


def test_two_captures_in_the_same_moment_do_not_collide(tmp_path):
    """The name carries microseconds; mashing the key must not overwrite."""
    ticks = iter(
        datetime.datetime(2026, 8, 23, 12, 0, 0, microsecond=us)
        for us in (1000, 2000)
    )
    first = save_frame(frame_with(0, 0, (9, 9, 9)), tmp_path, clock=lambda: next(ticks))
    second = save_frame(frame_with(0, 0, (9, 9, 9)), tmp_path, clock=lambda: next(ticks))

    assert first != second


def test_the_directory_is_created_if_missing(tmp_path):
    nested = tmp_path / "deep" / "er"

    path = save_frame(frame_with(0, 0, (1, 2, 3)), directory=nested)

    assert path.exists()
