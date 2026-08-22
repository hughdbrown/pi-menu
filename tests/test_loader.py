import pytest
from PIL import Image

from pi_menu.imgshow.loader import (
    ScaleMode,
    apply_brightness,
    load_frames,
    pixels,
    prepare,
    to_framebuffer,
)


@pytest.fixture
def wide_image():
    """A 32x8 image: red left half, blue right half."""
    image = Image.new("RGB", (32, 8), (255, 0, 0))
    image.paste(Image.new("RGB", (16, 8), (0, 0, 255)), (16, 0))
    return image


def test_fit_letterboxes_a_wide_image_with_black_bars(wide_image):
    result = prepare(wide_image, ScaleMode.FIT)

    assert result.size == (16, 16)
    # 32x8 scaled to 16 wide is 16x4, centred, so rows 0-5 are padding.
    assert result.getpixel((8, 0)) == (0, 0, 0)
    assert result.getpixel((8, 15)) == (0, 0, 0)
    assert result.getpixel((2, 7))[0] > 200   # red survives in the middle band
    assert result.getpixel((13, 7))[2] > 200  # so does blue


def test_fill_crops_instead_of_padding(wide_image):
    result = prepare(wide_image, ScaleMode.FILL)

    assert result.size == (16, 16)
    # Nothing is padded, so no row is pure black.
    assert all(sum(p) > 0 for p in pixels(result))


def test_stretch_fills_the_panel_and_ignores_aspect_ratio(wide_image):
    result = prepare(wide_image, ScaleMode.STRETCH)

    assert result.size == (16, 16)
    assert result.getpixel((0, 0))[0] > 200
    assert result.getpixel((15, 15))[2] > 200


def test_a_square_image_is_unchanged_by_the_scale_mode():
    square = Image.new("RGB", (64, 64), (10, 200, 30))
    for mode in ScaleMode:
        result = prepare(square, mode)
        assert result.size == (16, 16)
        assert result.getpixel((8, 8)) == (10, 200, 30)


def test_an_image_smaller_than_the_panel_is_scaled_up():
    tiny = Image.new("RGB", (4, 4), (255, 255, 0))
    assert prepare(tiny, ScaleMode.STRETCH).size == (16, 16)


def test_to_framebuffer_produces_768_row_major_bytes():
    image = Image.new("RGB", (16, 16), (0, 0, 0))
    image.putpixel((1, 0), (10, 20, 30))

    buffer = to_framebuffer(image)

    assert len(buffer) == 768
    assert buffer[3:6] == bytes([10, 20, 30])


def test_to_framebuffer_refuses_an_image_that_is_not_panel_sized():
    with pytest.raises(ValueError, match="16x16"):
        to_framebuffer(Image.new("RGB", (32, 32)))


def test_brightness_scales_every_channel():
    image = Image.new("RGB", (2, 2), (200, 100, 50))
    assert apply_brightness(image, 0.5).getpixel((0, 0)) == (100, 50, 25)
    assert apply_brightness(image, 1.0) is image
    assert apply_brightness(image, 0.0).getpixel((0, 0)) == (0, 0, 0)


def test_a_still_image_loads_as_a_single_frame(tmp_path):
    path = tmp_path / "still.png"
    Image.new("RGB", (20, 20), (1, 2, 3)).save(path)

    frames = load_frames(path)

    assert len(frames) == 1
    assert frames[0].image.size == (20, 20)


def test_an_animated_gif_loads_every_frame_with_its_own_duration(tmp_path):
    path = tmp_path / "spin.gif"
    colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    images = [Image.new("RGB", (8, 8), colour) for colour in colours]
    images[0].save(path, save_all=True, append_images=images[1:], duration=120, loop=0)

    frames = load_frames(path)

    assert len(frames) == 3
    assert all(frame.duration_ms == 120 for frame in frames)
    # Each frame is its own image, not a view that mutates as we iterate.
    assert [frame.image.getpixel((4, 4)) for frame in frames] == colours


def test_animation_can_be_reduced_to_the_first_frame(tmp_path):
    path = tmp_path / "spin.gif"
    images = [Image.new("RGB", (8, 8), c) for c in [(255, 0, 0), (0, 255, 0)]]
    images[0].save(path, save_all=True, append_images=images[1:], duration=80)

    assert len(load_frames(path, animate=False)) == 1


def test_a_grayscale_image_is_converted_to_rgb(tmp_path):
    path = tmp_path / "gray.png"
    Image.new("L", (16, 16), 128).save(path)

    frame = load_frames(path)[0]

    assert frame.image.mode == "RGB"
    assert len(to_framebuffer(prepare(frame.image, ScaleMode.FIT))) == 768


def test_a_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_frames(tmp_path / "nope.png")
