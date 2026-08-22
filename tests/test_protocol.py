import pytest

from pi_menu.display import protocol as proto


def test_frame_size_matches_a_16x16_rgb_panel():
    assert proto.FRAME_BYTES == 16 * 16 * 3 == 768


def test_blit_carries_the_frame_after_a_three_byte_header():
    frame = bytes(range(256)) * 3
    message = proto.encode_blit(frame)

    assert message[:2] == proto.MAGIC
    assert message[2] == proto.CMD_BLIT
    assert message[3:] == frame
    assert len(message) == 3 + proto.FRAME_BYTES


@pytest.mark.parametrize("size", [0, 767, 769])
def test_blit_rejects_a_wrongly_sized_frame(size):
    with pytest.raises(ValueError, match="768 bytes"):
        proto.encode_blit(bytes(size))


def test_brightness_is_clamped_into_one_byte():
    assert proto.encode_brightness(300)[3] == 255
    assert proto.encode_brightness(-5)[3] == 0
    assert proto.encode_brightness(128)[3] == 128


def test_ping_and_clear_are_bare_commands():
    assert proto.encode_ping() == b"SU\x00"
    assert proto.encode_clear() == b"SU\x03"


def test_pixels_are_row_major_with_x_varying_fastest():
    assert proto.pixel_offset(0, 0) == 0
    assert proto.pixel_offset(1, 0) == 3
    assert proto.pixel_offset(0, 1) == 48
    assert proto.pixel_offset(15, 15) == proto.FRAME_BYTES - 3
