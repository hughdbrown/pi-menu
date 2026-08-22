"""Frame server for the Pimoroni Stellar Unicorn (MicroPython).

Copy this onto the Stellar Unicorn's Pico as ``main.py`` -- with Thonny,
mpremote, or by dragging it across -- and it will run at power-on.

It does no thinking. The Raspberry Pi decides what every pixel should be
and sends whole frames over USB; this just blits them. Keeping the Pico
dumb means the Game of Life rules and the image scaling live on the Pi,
where they can be tested without hardware.

Protocol (see pi_menu/display/protocol.py, which must agree):

    "SU" 0x00                 ping   -> "STELLAR16\\n"
    "SU" 0x01 <768 bytes RGB> blit   -> "K\\n"
    "SU" 0x02 <1 byte>        bright -> "K\\n"
    "SU" 0x03                 clear  -> "K\\n"

The 768 bytes are row-major RGB, x varying fastest, top-left first.
"""

import sys
import time

from picographics import DISPLAY_STELLAR_UNICORN, PicoGraphics
from stellar import StellarUnicorn

WIDTH = 16
HEIGHT = 16
FRAME_BYTES = WIDTH * HEIGHT * 3

MAGIC_0 = ord("S")
MAGIC_1 = ord("U")

CMD_PING = 0x00
CMD_BLIT = 0x01
CMD_BRIGHTNESS = 0x02
CMD_CLEAR = 0x03

HELLO = b"STELLAR16\n"
ACK = b"K\n"

unicorn = StellarUnicorn()
graphics = PicoGraphics(display=DISPLAY_STELLAR_UNICORN)

unicorn.set_brightness(0.5)
graphics.set_pen(graphics.create_pen(0, 0, 0))
graphics.clear()
unicorn.update(graphics)

# Bound once so the test harness can substitute a pipe for the USB link.
_stdin = sys.stdin.buffer
_stdout = sys.stdout.buffer


def read_exact(count):
    """Read exactly ``count`` bytes, however many reads that takes.

    An empty read means the host has nothing for us -- it has gone away,
    or the USB link is idle. Pause briefly rather than spinning, so an
    unplugged Pi does not leave the Pico burning a whole core.
    """
    chunks = bytearray()
    while len(chunks) < count:
        chunk = _stdin.read(count - len(chunks))
        if chunk:
            chunks.extend(chunk)
        else:
            time.sleep(0.001)
    return bytes(chunks)


def reply(message):
    _stdout.write(message)


def blit(frame):
    """Paint a whole frame and push it to the LEDs."""
    offset = 0
    pen = graphics.create_pen
    pixel = graphics.pixel
    set_pen = graphics.set_pen
    for y in range(HEIGHT):
        for x in range(WIDTH):
            set_pen(pen(frame[offset], frame[offset + 1], frame[offset + 2]))
            pixel(x, y)
            offset += 3
    unicorn.update(graphics)


def clear():
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    unicorn.update(graphics)


def run():
    """Wait for framed commands forever, resynchronising after junk bytes."""
    while True:
        if read_exact(1)[0] != MAGIC_0:
            continue
        if read_exact(1)[0] != MAGIC_1:
            continue

        command = read_exact(1)[0]

        if command == CMD_BLIT:
            blit(read_exact(FRAME_BYTES))
            reply(ACK)
        elif command == CMD_PING:
            reply(HELLO)
        elif command == CMD_BRIGHTNESS:
            unicorn.set_brightness(read_exact(1)[0] / 255)
            unicorn.update(graphics)
            reply(ACK)
        elif command == CMD_CLEAR:
            clear()
            reply(ACK)
        # An unknown command is ignored; the next "SU" resynchronises us.


if __name__ == "__main__":
    # MicroPython runs main.py as __main__, so this still autostarts on
    # the Pico while leaving the module importable by the tests.
    run()
