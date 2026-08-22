"""Wire protocol between the Pi and the Stellar Unicorn's Pico.

Every message is ``b"SU"`` + a one-byte command + a fixed-size payload.
The payload length is implied by the command, so the Pico never has to
parse a length field or scan for a delimiter.

The Pi is the only talker; the Pico answers pings with ``HELLO`` and
every other command with ``ACK``.
"""

WIDTH = 16
HEIGHT = 16
NUM_PIXELS = WIDTH * HEIGHT
FRAME_BYTES = NUM_PIXELS * 3

MAGIC = b"SU"

CMD_PING = 0x00
CMD_BLIT = 0x01
CMD_BRIGHTNESS = 0x02
CMD_CLEAR = 0x03

HELLO = b"STELLAR16"
ACK = b"K"

#: The Pico presents a native USB CDC port, which ignores the baud rate
#: entirely. It only matters if the link ever runs over a UART bridge.
BAUD = 115200

#: USB vendor id Raspberry Pi uses for the Pico family.
PICO_VID = 0x2E8A


def encode_ping() -> bytes:
    return MAGIC + bytes([CMD_PING])


def encode_clear() -> bytes:
    return MAGIC + bytes([CMD_CLEAR])


def encode_brightness(level: int) -> bytes:
    """Encode a brightness command. ``level`` is clamped to 0-255."""
    return MAGIC + bytes([CMD_BRIGHTNESS, _clamp_byte(level)])


def encode_blit(framebuffer: bytes) -> bytes:
    """Encode a full-frame blit.

    ``framebuffer`` is row-major RGB, x varying fastest, exactly
    ``FRAME_BYTES`` long.
    """
    if len(framebuffer) != FRAME_BYTES:
        raise ValueError(
            f"framebuffer must be {FRAME_BYTES} bytes, got {len(framebuffer)}"
        )
    return MAGIC + bytes([CMD_BLIT]) + bytes(framebuffer)


def pixel_offset(x: int, y: int) -> int:
    """Byte offset of pixel ``(x, y)`` within a framebuffer."""
    return (y * WIDTH + x) * 3


def _clamp_byte(value: int) -> int:
    return max(0, min(255, int(value)))
