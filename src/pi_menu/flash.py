"""Copies the frame server onto the Stellar Unicorn's Pico.

    pi-menu-flash

Does the job ``mpremote`` would, using MicroPython's raw REPL over
pyserial, which this project already depends on. That matters on a fresh
Raspberry Pi where ``mpremote`` is not installed -- and it matters more
because our own firmware disables Ctrl-C: once the frame server is
running, no standard tool can interrupt it to put a new file on the
board. So this first asks a running server to step aside (protocol
command 0x05), and only falls back to Ctrl-C for a board already sitting
at its REPL.

If both fail, hold the **A button** while power-cycling the panel. That
skips the frame server and leaves a REPL to flash into.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .display import protocol as proto
from .display.serial_link import find_port
from .firmware import FRAME_SERVER

#: Control bytes MicroPython's REPL responds to.
CTRL_A = b"\x01"  # enter raw REPL
CTRL_B = b"\x02"  # back to the friendly REPL
CTRL_C = b"\x03"  # interrupt
CTRL_D = b"\x04"  # execute, or soft reset

RAW_PROMPT = b"raw REPL; CTRL-B to exit\r\n>"
#: Small enough that a chunk plus its repr() overhead never strains the
#: board's parser, big enough that a 6 KB file takes a couple of seconds.
CHUNK = 192


class FlashError(RuntimeError):
    """The board could not be reached or written to."""


class RawRepl:
    """MicroPython's raw REPL, which is how files get onto a board.

    Each :meth:`run` executes in the same interpreter session, so a file
    handle opened by one call is still usable by the next. That is what
    lets a file be written in chunks rather than as one huge literal.
    """

    def __init__(self, link, timeout: float = 5.0) -> None:
        self._link = link
        self._timeout = timeout
        # Anything read past a token belongs to the next reply, so it is
        # kept here. Dropping it loses the start of the board's answer.
        self._buffer = bytearray()

    def _read_until(self, token: bytes) -> bytes:
        deadline = time.monotonic() + self._timeout
        while True:
            found = self._buffer.find(token)
            if found >= 0:
                end = found + len(token)
                consumed = bytes(self._buffer[:end])
                del self._buffer[:end]
                return consumed
            if time.monotonic() >= deadline:
                raise FlashError(
                    f"timed out waiting for {token!r}; "
                    f"got {bytes(self._buffer)[-120:]!r}"
                )
            chunk = self._link.read(self._link.in_waiting or 1)
            if chunk:
                self._buffer.extend(chunk)

    def enter(self) -> None:
        self._link.write(b"\r" + CTRL_C + CTRL_C)
        time.sleep(0.15)
        self._link.reset_input_buffer()
        self._buffer.clear()
        self._link.write(b"\r" + CTRL_A)
        self._read_until(RAW_PROMPT)

    def run(self, code: str) -> bytes:
        """Execute a block on the board and return whatever it printed."""
        self._link.write(code.encode("utf-8") + CTRL_D)

        if b"OK" not in self._read_until(b"OK"):
            raise FlashError("the board would not accept a command")

        output = self._read_until(CTRL_D)[:-1]
        error = self._read_until(CTRL_D)[:-1]
        self._read_until(b">")

        if error.strip():
            raise FlashError(error.decode("utf-8", "replace").strip())
        return output

    def exit(self) -> None:
        self._link.write(CTRL_B)

    def soft_reset(self) -> None:
        """Restart the board so the new main.py runs."""
        self._link.write(CTRL_D)


def stand_down_frame_server(link, timeout: float = 0.5) -> bool:
    """Ask a running frame server to quit to the REPL. True if it did.

    Our firmware turns Ctrl-C off, so this is the only polite way back.
    """
    link.reset_input_buffer()
    original_timeout, link.timeout = link.timeout, timeout
    try:
        link.write(proto.encode_ping())
        # A running server replies in milliseconds, so a short wait here
        # keeps the common case -- a board already at its REPL -- quick.
        if proto.parse_hello(link.readline()) is None:
            return False
    finally:
        link.timeout = original_timeout

    link.write(proto.encode_exit())
    link.readline()  # the ack, if it arrives before the board goes
    time.sleep(0.5)
    link.reset_input_buffer()
    return True


def write_file(repl: RawRepl, remote_name: str, data: bytes, log) -> None:
    """Send ``data`` to the board as ``remote_name``, a chunk at a time."""
    repl.run(f"f = open({remote_name!r}, 'wb')\nw = f.write")
    total = len(data)
    for start in range(0, total, CHUNK):
        repl.run(f"w({data[start : start + CHUNK]!r})")
        log(f"\r  writing {min(start + CHUNK, total)}/{total} bytes", end="")
    repl.run("f.close()")
    log("")


def verify_file(repl: RawRepl, remote_name: str, data: bytes) -> None:
    """Read the file back off the board and check it byte for byte."""
    reported = repl.run(
        f"f = open({remote_name!r}, 'rb')\n"
        "d = f.read()\n"
        "f.close()\n"
        "print(len(d), sum(d))"
    )
    try:
        size, checksum = (int(part) for part in reported.split())
    except ValueError as exc:
        raise FlashError(f"could not verify the copy: {reported!r}") from exc

    if size != len(data) or checksum != sum(data):
        raise FlashError(
            f"the copy does not match: board has {size} bytes (sum {checksum}), "
            f"expected {len(data)} bytes (sum {sum(data)})"
        )


def flash(
    port: str | None = None,
    source: Path | None = None,
    remote_name: str = "main.py",
    verify: bool = True,
    log=print,
) -> str:
    """Put the frame server on the board. Returns the port it used."""
    import serial

    source = Path(source) if source else FRAME_SERVER
    if not source.is_file():
        raise FlashError(f"no firmware to copy at {source}")
    data = source.read_bytes()

    target = port or find_port()
    if not target:
        raise FlashError(
            "no Pico found. Check the USB cable is a data cable, and that "
            "the panel is powered."
        )

    log(f"Panel on {target}")
    log(f"Copying {source.name} ({len(data)} bytes) as {remote_name}")

    try:
        link = serial.Serial(target, proto.BAUD, timeout=2.0, write_timeout=5.0)
    except Exception as exc:  # noqa: BLE001
        raise FlashError(f"{exc}\nIs another program using the port?") from exc

    with link:
        time.sleep(0.3)
        if stand_down_frame_server(link):
            log("  asked the running frame server to step aside")
        else:
            log("  no frame server answered; assuming the board is at its REPL")

        repl = RawRepl(link)
        try:
            repl.enter()
        except FlashError as exc:
            raise FlashError(
                f"{exc}\n\n"
                "The board did not drop into its REPL. Hold the A button while\n"
                "power-cycling the panel, then run this again -- that skips the\n"
                "frame server, which otherwise ignores Ctrl-C."
            ) from exc

        try:
            write_file(repl, remote_name, data, log)
            if verify:
                verify_file(repl, remote_name, data)
                log("  verified byte for byte")
        finally:
            repl.exit()

        log("  restarting the panel")
        repl.soft_reset()
        time.sleep(1.5)

    return target


def confirm_running(port: str, log=print) -> bool:
    """Ping the freshly flashed board and report what answered."""
    from .display.serial_link import SerialDisplay, StellarUnicornNotFound

    try:
        display = SerialDisplay(port=port)
    except StellarUnicornNotFound as exc:
        log(f"  the panel did not come back: {exc}")
        return False
    try:
        log(f"  {display.description}")
        return display.firmware_is_current
    finally:
        display.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pi-menu-flash",
        description="Copy the frame server onto the Stellar Unicorn's Pico.",
    )
    parser.add_argument("--port", help="serial device of the Pico (default: autodetect)")
    parser.add_argument(
        "--source", help="firmware file to copy (default: the one shipped here)"
    )
    parser.add_argument(
        "--name", default="main.py", help="filename on the board (default: main.py)"
    )
    parser.add_argument(
        "--no-verify", action="store_true", help="skip reading the copy back"
    )
    args = parser.parse_args(argv)

    def log(message="", end="\n"):
        print(message, end=end, flush=True)

    try:
        port = flash(
            port=args.port,
            source=args.source,
            remote_name=args.name,
            verify=not args.no_verify,
            log=log,
        )
    except FlashError as exc:
        print(f"\nflashing failed: {exc}", file=sys.stderr)
        return 1

    if confirm_running(port, log):
        log("\nDone. The panel is running the frame server.")
        return 0
    log("\nCopied, but the panel did not answer as expected. Try pi-menu-doctor.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
