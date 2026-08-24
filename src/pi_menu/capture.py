"""Saving what the panel is showing as an image file.

The panel is sixteen pixels square, which as a screenshot is a speck.
Frames are scaled up with each LED kept as a crisp square -- nearest
neighbour, never smoothing -- because a blurred LED grid stops looking
like the hardware.

Files land in ``~/Pictures`` when there is one, else the home
directory, named with a timestamp so mashing the capture key mid-jump
never overwrites the shot before it.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from .display.protocol import FRAME_BYTES, HEIGHT, WIDTH

#: Each LED becomes a square this many pixels on a side.
DEFAULT_SCALE = 24


def to_image(framebuffer: bytes, scale: int = DEFAULT_SCALE):
    """A framebuffer as a PIL image, one crisp square per LED."""
    from PIL import Image

    if len(framebuffer) != FRAME_BYTES:
        raise ValueError(
            f"framebuffer must be {FRAME_BYTES} bytes, got {len(framebuffer)}"
        )
    image = Image.frombytes("RGB", (WIDTH, HEIGHT), bytes(framebuffer))
    return image.resize((WIDTH * scale, HEIGHT * scale), Image.NEAREST)


def default_directory() -> Path:
    pictures = Path.home() / "Pictures"
    return pictures if pictures.is_dir() else Path.home()


def save_frame(
    framebuffer: bytes,
    directory: Path | None = None,
    prefix: str = "pi-menu",
    scale: int = DEFAULT_SCALE,
    clock=datetime.datetime.now,
) -> Path:
    """Write the frame as a PNG and return where it landed."""
    directory = Path(directory) if directory is not None else default_directory()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = clock().strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"{prefix}-{stamp}.png"
    to_image(framebuffer, scale).save(path)
    return path
