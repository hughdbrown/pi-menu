import io

import pytest

from pi_menu.display import open_display
from pi_menu.display.null_ import NullDisplay
from pi_menu.display.protocol import FRAME_BYTES, pixel_offset
from pi_menu.display.term import TerminalDisplay


def test_drawing_does_not_reach_the_backend_until_show():
    display = NullDisplay()
    display.set_pixel(0, 0, 255, 0, 0)
    assert display.frames == []

    display.show()
    assert len(display.frames) == 1
    assert display.last_frame[:3] == b"\xff\x00\x00"


def test_pixels_land_at_their_row_major_offset():
    display = NullDisplay()
    display.set_pixel(3, 2, 1, 2, 3)
    offset = pixel_offset(3, 2)
    assert display.framebuffer[offset : offset + 3] == bytes([1, 2, 3])


def test_off_panel_pixels_are_dropped_silently():
    display = NullDisplay()
    display.set_pixel(16, 0, 255, 255, 255)
    display.set_pixel(-1, -1, 255, 255, 255)
    assert display.framebuffer == bytes(FRAME_BYTES)


def test_channel_values_are_clamped_to_a_byte():
    display = NullDisplay()
    display.set_pixel(0, 0, 999, -20, 128)
    assert display.framebuffer[:3] == bytes([255, 0, 128])


def test_clear_blanks_the_buffer():
    display = NullDisplay()
    display.set_pixel(5, 5, 255, 255, 255)
    display.clear()
    assert display.framebuffer == bytes(FRAME_BYTES)


def test_set_frame_replaces_everything_at_once():
    display = NullDisplay()
    frame = bytes(range(256)) * 3
    display.set_frame(frame)
    assert display.framebuffer == frame


def test_set_frame_rejects_a_wrongly_sized_buffer():
    with pytest.raises(ValueError, match="768 bytes"):
        NullDisplay().set_frame(bytes(10))


@pytest.mark.parametrize(
    "given,expected", [(-1.0, 0.0), (0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (4.0, 1.0)]
)
def test_brightness_is_clamped_to_a_fraction(given, expected):
    assert NullDisplay(brightness=given).brightness == expected


def test_the_terminal_backend_draws_two_pixel_rows_per_text_row():
    stream = io.StringIO()
    display = TerminalDisplay(stream=stream)
    display.set_pixel(0, 0, 255, 0, 0)
    display.show()

    output = stream.getvalue()
    assert output.count("\n") == 8
    assert "38;2;255;0;0" in output


def test_the_terminal_backend_dims_pixels_itself():
    stream = io.StringIO()
    display = TerminalDisplay(brightness=0.5, stream=stream)
    display.set_pixel(0, 0, 200, 100, 50)
    display.show()
    assert "38;2;100;50;25" in stream.getvalue()


def test_open_display_honours_an_explicit_backend():
    display = open_display("null")
    assert isinstance(display, NullDisplay)
    display.close()


def test_open_display_falls_back_to_the_terminal_when_no_panel_is_found(
    monkeypatch, capsys
):
    import pi_menu.display as display_module
    from pi_menu.display.serial_link import StellarUnicornNotFound

    def no_panel(*args, **kwargs):
        raise StellarUnicornNotFound("nothing plugged in")

    monkeypatch.setattr(display_module, "SerialDisplay", no_panel)

    display = open_display("auto")
    try:
        assert isinstance(display, TerminalDisplay)
        assert "nothing plugged in" in capsys.readouterr().err
    finally:
        display.close()


def test_asking_for_serial_explicitly_reports_the_failure(monkeypatch):
    import pi_menu.display as display_module
    from pi_menu.display.serial_link import StellarUnicornNotFound

    def no_panel(*args, **kwargs):
        raise StellarUnicornNotFound("nothing plugged in")

    monkeypatch.setattr(display_module, "SerialDisplay", no_panel)

    with pytest.raises(StellarUnicornNotFound):
        open_display("serial")


def test_each_backend_says_what_it_is():
    """A preview must never be mistaken for the panel."""
    from pi_menu.display.term import TerminalDisplay

    assert NullDisplay().description == "no display"

    preview = TerminalDisplay(stream=io.StringIO())
    try:
        assert "TERMINAL PREVIEW" in preview.description
        assert preview.is_panel is False
    finally:
        preview.close()


def test_the_panel_backend_names_the_port_and_firmware(pico):
    from pi_menu.display.serial_link import SerialDisplay

    _, path = pico
    display = SerialDisplay(port=path)
    try:
        assert display.is_panel is True
        assert path in display.description
        assert "firmware v" in display.description
    finally:
        display.close()


def test_the_fallback_shouts_rather_than_murmurs(monkeypatch, capsys):
    """The quiet version of this message went unread and cost a session."""
    import pi_menu.display as display_module
    from pi_menu.display.serial_link import StellarUnicornNotFound

    def no_panel(*args, **kwargs):
        raise StellarUnicornNotFound("nothing plugged in")

    monkeypatch.setattr(display_module, "SerialDisplay", no_panel)

    display = open_display("auto")
    try:
        stderr = capsys.readouterr().err
        assert "NO STELLAR UNICORN FOUND" in stderr
        assert "mpremote cp" in stderr        # tells you how to fix it
        assert "pi-menu-doctor" in stderr
        assert "nothing plugged in" in stderr  # and why it happened
    finally:
        display.close()
