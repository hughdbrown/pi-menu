"""Turn an image file into 16x16 frames the panel can display.

Everything here is pure image work -- no Tk, no serial -- so the scaling
rules can be tested without hardware or a display.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps, ImageSequence

from ..display.protocol import HEIGHT, WIDTH

#: Extensions offered in the file chooser and accepted by :func:`load_frames`.
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ppm")

DEFAULT_FRAME_MS = 100
MIN_FRAME_MS = 20


class ScaleMode(str, Enum):
    """How a non-square image is made to fit a square panel."""

    FIT = "fit"          # whole image, letterboxed with black
    FILL = "fill"        # fills the panel, edges cropped
    STRETCH = "stretch"  # fills the panel, aspect ratio ignored

    @property
    def label(self) -> str:
        return {
            ScaleMode.FIT: "Fit (letterbox)",
            ScaleMode.FILL: "Fill (crop)",
            ScaleMode.STRETCH: "Stretch",
        }[self]


@dataclass(frozen=True)
class Frame:
    """One image frame and how long to show it."""

    image: Image.Image
    duration_ms: int = DEFAULT_FRAME_MS


def load_frames(path: str | Path, animate: bool = True) -> list[Frame]:
    """Read an image file into a list of full-size RGB frames.

    Still images give one frame. Animated files give every frame when
    ``animate`` is true, and just the first when it is false.
    """
    path = Path(path)
    with Image.open(path) as source:
        source.load()
        if not animate or getattr(source, "n_frames", 1) <= 1:
            return [Frame(_normalise(source), DEFAULT_FRAME_MS)]

        frames = []
        for raw in ImageSequence.Iterator(source):
            duration = max(MIN_FRAME_MS, int(raw.info.get("duration", DEFAULT_FRAME_MS)))
            frames.append(Frame(_normalise(raw), duration))
        return frames


def _normalise(image: Image.Image) -> Image.Image:
    """Copy an image to standalone RGB, honouring any EXIF rotation.

    The copy matters: frames from ``ImageSequence`` share the parent's
    buffer and change under you as the iterator advances.
    """
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        # Malformed EXIF should not stop an image from being shown.
        pass
    return image.convert("RGB").copy()


def prepare(
    image: Image.Image,
    mode: ScaleMode = ScaleMode.FIT,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> Image.Image:
    """Scale an image down to panel size using ``mode``."""
    if mode is ScaleMode.STRETCH:
        return image.resize((width, height), Image.Resampling.LANCZOS)

    if mode is ScaleMode.FILL:
        return ImageOps.fit(
            image, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )

    scaled = image.copy()
    scaled.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(scaled, ((width - scaled.width) // 2, (height - scaled.height) // 2))
    return canvas


def apply_brightness(image: Image.Image, factor: float) -> Image.Image:
    """Scale every channel by ``factor`` (1.0 leaves the image alone)."""
    if factor == 1.0:
        return image
    return ImageEnhance.Brightness(image).enhance(max(0.0, factor))


def to_framebuffer(image: Image.Image) -> bytes:
    """Flatten a panel-sized RGB image into a framebuffer."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(
            f"image must be {WIDTH}x{HEIGHT} before flattening, got {image.size[0]}x{image.size[1]}"
        )
    return image.tobytes()


def pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    """Row-major list of RGB triples, handy for drawing a preview.

    Built from ``tobytes`` rather than ``getdata``, which Pillow 14
    removes.
    """
    data = image.convert("RGB").tobytes()
    return [
        (data[i], data[i + 1], data[i + 2]) for i in range(0, len(data), 3)
    ]
