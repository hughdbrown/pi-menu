"""Frame server for the Pimoroni Stellar Unicorn (MicroPython).

Copy this onto the Stellar Unicorn's Pico as ``main.py`` -- with Thonny,
mpremote, or by dragging it across -- and it will run at power-on.

It does no thinking. The Raspberry Pi decides what every pixel should be
and sends whole frames over USB; this just blits them. Keeping the Pico
dumb means the Game of Life rules and the image scaling live on the Pi,
where they can be tested without hardware.

Protocol (see pi_menu/display/protocol.py, which must agree):

    "SU" 0x00                 ping   -> "STELLAR16 2\\n"
    "SU" 0x01 <768 bytes RGB> blit   -> "K\\n"
    "SU" 0x02 <1 byte>        bright -> "K\\n"
    "SU" 0x04                 clear  -> "K\\n"
    "SU" 0x05                 exit   -> "K\\n", then quits to the REPL
    "SU" 0x06 <5 bytes>       tone   -> "K\\n"
    "SU" 0x07                 hush   -> "K\\n"

The five tone bytes are channel, waveform, frequency high, frequency
low, volume. Volume zero releases the note. The Pi decides every note
and when it sounds; this only sets the registers.

The 768 bytes are row-major RGB, x varying fastest, top-left first.

Ctrl-C is disabled while this runs -- see kbd_intr below -- so hold the
**A button** as the panel powers up to skip the server and get a REPL.
"""

import micropython
import sys
import time

from picographics import DISPLAY_STELLAR_UNICORN, PicoGraphics
from stellar import StellarUnicorn

PROTOCOL_VERSION = 3

WIDTH = 16
HEIGHT = 16
FRAME_BYTES = WIDTH * HEIGHT * 3

MAGIC_0 = ord("S")
MAGIC_1 = ord("U")

CMD_PING = 0x00
CMD_BLIT = 0x01
CMD_BRIGHTNESS = 0x02
CMD_CLEAR = 0x04
CMD_EXIT = 0x05
CMD_TONE = 0x06
CMD_HUSH = 0x07

SYNTH_CHANNELS = 8
TONE_BYTES = 5

HELLO = b"STELLAR16 %d\n" % PROTOCOL_VERSION
ACK = b"K\n"

unicorn = StellarUnicorn()
graphics = PicoGraphics(display=DISPLAY_STELLAR_UNICORN)

#: Channels are configured the first time they are used and reused after.
_channels = {}
#: False once the synth has proved unavailable, so a board that cannot
#: make a sound still shows pictures.
_audio = True

_stdin = sys.stdin.buffer
_stdout = sys.stdout.buffer


def escape_requested():
    """True if the A button is held, meaning 'give me a REPL instead'.

    Wrapped because a firmware build without this exact constant should
    still boot into the frame server rather than fail here.
    """
    try:
        return unicorn.is_pressed(StellarUnicorn.SWITCH_A)
    except Exception:
        return False


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


def tone(channel, waveform, frequency, volume):
    """Set one synth channel. Volume zero releases the note.

    Wrapped in its own failure guard: a board or firmware build without
    a working synth must still serve frames. A silent panel is a
    disappointment; a dark one is a broken program.
    """
    global _audio
    if not _audio or channel >= SYNTH_CHANNELS:
        return
    try:
        voice = _channels.get(channel)
        if voice is None:
            voice = unicorn.synth_channel(channel)
            _channels[channel] = voice
        voice.configure(
            waveforms=1 << waveform,
            frequency=frequency,
            volume=volume * 128,
            attack=0.01,
            decay=0.05,
            sustain=0.8,
            release=0.05,
        )
        if volume:
            voice.trigger_attack()
        else:
            voice.trigger_release()
        unicorn.play_synth()
    except Exception:
        _audio = False


def hush():
    """Silence every channel at once."""
    if not _audio:
        return
    try:
        for voice in _channels.values():
            voice.trigger_release()
        unicorn.stop_playing()
    except Exception:
        pass


def clear():
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    unicorn.update(graphics)


def handle(command):
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
    elif command == CMD_TONE:
        payload = read_exact(TONE_BYTES)
        tone(payload[0], payload[1], (payload[2] << 8) | payload[3], payload[4])
        reply(ACK)
    elif command == CMD_HUSH:
        hush()
        reply(ACK)
    elif command == CMD_EXIT:
        # Step aside so the board can be re-flashed. Ctrl-C is restored
        # first, or the next tool along would have no way to interrupt
        # whatever runs after us.
        reply(ACK)
        hush()
        time.sleep(0.1)  # let the reply reach the host before we go
        micropython.kbd_intr(3)
        raise SystemExit
    # An unknown command is ignored; the next "SU" resynchronises us.


def run():
    """Serve framed commands forever, resynchronising after junk bytes."""
    while True:
        if read_exact(1)[0] != MAGIC_0:
            continue
        if read_exact(1)[0] != MAGIC_1:
            continue
        handle(read_exact(1)[0])


def serve_forever():
    """Run the server, surviving anything a bad frame can throw at it.

    A panel that stops responding until it is power-cycled is far worse
    than one that drops a frame, so nothing here is allowed to be fatal.
    """
    while True:
        try:
            run()
        except KeyboardInterrupt:
            # Should be unreachable with kbd_intr disabled, but a stray
            # interrupt must not take the panel down for good.
            continue
        except Exception:
            time.sleep(0.05)
            continue


def boot():
    """Prepare the panel for serving. False means drop to the REPL instead.

    Kept as a function so the tests can run the real startup sequence
    rather than a copy of it.
    """
    if escape_requested():
        print("A held at boot: frame server skipped, REPL is yours.")
        return False

    # The single most important line in this file. MicroPython's USB
    # serial driver reads 0x03 as Ctrl-C and raises KeyboardInterrupt in
    # whatever is running, swallowing the byte rather than delivering it.
    # Frame data is binary, so 0x03 appears constantly -- in any pixel
    # with a channel value of 3. Without this the server dies partway
    # through the first photo, and the Pi silently falls back to its
    # terminal preview. Ctrl-C stops working; hold A at boot instead.
    micropython.kbd_intr(-1)

    unicorn.set_brightness(0.5)
    clear()
    return True


if __name__ == "__main__":
    # MicroPython runs main.py as __main__, so this still autostarts on
    # the Pico while leaving the module importable by the tests.
    if boot():
        serve_forever()
