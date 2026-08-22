"""Checks the whole path from this machine to the LEDs, one layer at a time.

Run it when the panel stays dark:

    pi-menu-doctor

Each check reports on one boundary -- packages, serial ports, permissions,
the handshake, then real frames -- so the output says *which* layer is
broken rather than just that something is. Nothing here is clever; it is
meant to be pasted into a bug report.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass

from . import __version__
from .display import protocol as proto

OK, WARN, FAIL = "ok", "warn", "fail"

MARKS = {OK: "  ok  ", WARN: " warn ", FAIL: " FAIL "}


@dataclass
class Result:
    level: str
    title: str
    detail: str = ""

    def render(self) -> str:
        line = f"[{MARKS[self.level]}] {self.title}"
        if self.detail:
            line += "\n" + "\n".join(
                f"           {part}" for part in self.detail.splitlines()
            )
        return line


# -- individual checks ---------------------------------------------------


def check_environment() -> list[Result]:
    return [
        Result(
            OK,
            f"pi-menu {__version__} on Python {platform.python_version()}",
            f"{platform.platform()}\n{sys.executable}",
        )
    ]


def check_dependencies() -> list[Result]:
    results = []
    for module, why in (
        ("serial", "talking to the panel"),
        ("PIL", "the image shower"),
        ("tkinter", "every window"),
    ):
        try:
            __import__(module)
            results.append(Result(OK, f"{module} is importable"))
        except ImportError as exc:
            fix = (
                "sudo apt install python3-tk"
                if module == "tkinter"
                else f"pip install {'pyserial' if module == 'serial' else 'pillow'}"
            )
            results.append(
                Result(FAIL, f"{module} is missing — needed for {why}", f"{exc}\n{fix}")
            )
    return results


def check_ports() -> tuple[list[Result], list[str]]:
    """List serial ports, returning the check output and Pico candidates."""
    try:
        import serial.tools.list_ports as list_ports
    except ImportError:
        return [Result(FAIL, "cannot list serial ports without pyserial")], []

    ports = list(list_ports.comports())
    if not ports:
        return [
            Result(
                FAIL,
                "no serial ports at all",
                "Is the Stellar Unicorn plugged into the Pi with a data cable?\n"
                "Charge-only USB cables enumerate nothing.",
            )
        ], []

    described = []
    candidates = []
    for port in ports:
        vid = getattr(port, "vid", None)
        marker = ""
        if vid == proto.PICO_VID:
            marker = "  <- Raspberry Pi Pico"
            candidates.append(port.device)
        elif "ttyacm" in port.device.lower() or "usbmodem" in port.device.lower():
            marker = "  <- possible Pico"
            candidates.append(port.device)
        described.append(
            f"{port.device}  vid={vid and hex(vid)} pid="
            f"{getattr(port, 'pid', None) and hex(port.pid)}  "
            f"{port.description}{marker}"
        )

    level = OK if candidates else FAIL
    title = (
        f"{len(candidates)} likely panel port(s) among {len(ports)} serial port(s)"
        if candidates
        else f"{len(ports)} serial port(s), none look like a Pico"
    )
    return [Result(level, title, "\n".join(described))], candidates


def check_permissions(path: str) -> list[Result]:
    results = []
    if not os.path.exists(path):
        return [Result(FAIL, f"{path} does not exist")]

    readable = os.access(path, os.R_OK)
    writable = os.access(path, os.W_OK)
    if readable and writable:
        results.append(Result(OK, f"{path} is readable and writable"))
    else:
        results.append(
            Result(
                FAIL,
                f"{path} is not writable by this user",
                "sudo usermod -a -G dialout $USER, then log out and back in.\n"
                "A group change does not apply to sessions already running.",
            )
        )

    try:
        groups = subprocess.run(
            ["id", "-nG"], capture_output=True, text=True, timeout=5
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        groups = []
    if groups:
        if "dialout" in groups:
            results.append(Result(OK, "this user is in the dialout group"))
        else:
            results.append(
                Result(
                    WARN,
                    "this user is not in the dialout group",
                    "sudo usermod -a -G dialout $USER, then log out and back in.",
                )
            )
    return results


def probe(path: str, timeout: float = 2.0, attempts: int = 3) -> tuple[int | None, bytes]:
    """Ping a port raw and report the version and the literal reply."""
    import serial

    with serial.Serial(path, proto.BAUD, timeout=timeout, write_timeout=timeout) as link:
        time.sleep(0.3)
        link.reset_input_buffer()
        reply = b""
        for _ in range(attempts):
            link.write(proto.encode_ping())
            reply = link.readline()
            version = proto.parse_hello(reply)
            if version is not None:
                return version, reply
        return None, reply


def interpret_reply(reply: bytes) -> str:
    """Explain an unexpected ping reply in terms of what to do about it."""
    if not reply:
        return (
            "The port said nothing at all.\n"
            "Either main.py is not running, or something else has the port open."
        )
    text = reply.decode("utf-8", "replace")
    if ">>>" in text or "Traceback" in text or "MicroPython" in text:
        return (
            f"The Pico answered from its REPL, not the frame server: {text!r}\n"
            "main.py is not running. Run pi-menu-flash to install it, then\n"
            "power-cycle the panel."
        )
    return f"Unrecognised reply: {reply!r}"


def check_handshake(path: str) -> tuple[list[Result], int | None]:
    try:
        version, reply = probe(path)
    except Exception as exc:  # noqa: BLE001 - every failure is user-facing
        return [Result(FAIL, f"could not open {path}", str(exc))], None

    if version is None:
        return [Result(FAIL, f"{path} is not running the frame server", interpret_reply(reply))], None

    if version < proto.PROTOCOL_VERSION:
        return [
            Result(
                WARN,
                f"{path} runs protocol v{version}, this needs v{proto.PROTOCOL_VERSION}",
                "Re-copy the firmware onto the Pico by running pi-menu-flash.\n"
                "Old firmware is killed by binary frame data partway through.",
            )
        ], version

    return [Result(OK, f"frame server answered on {path}, protocol v{version}")], version


def check_frames(path: str) -> list[Result]:
    """Push real frames and time them. This is the part you watch."""
    from .display.serial_link import SerialDisplay

    patterns = [
        ("all red", (255, 0, 0)),
        ("all green", (0, 255, 0)),
        ("all blue", (0, 0, 255)),
        # 3 is MicroPython's interrupt byte: old firmware dies right here.
        ("dim grey (channel value 3)", (3, 3, 3)),
    ]

    try:
        display = SerialDisplay(port=path, brightness=0.5)
    except Exception as exc:  # noqa: BLE001
        return [Result(FAIL, "could not open the panel for the frame test", str(exc))]

    results = []
    try:
        for label, rgb in patterns:
            started = time.monotonic()
            for y in range(display.height):
                for x in range(display.width):
                    display.set_pixel(x, y, *rgb)
            display.show()
            results.append(
                Result(OK, f"sent {label}", f"{(time.monotonic() - started) * 1000:.0f} ms")
            )
            time.sleep(0.4)

        started = time.monotonic()
        for step in range(32):
            display.clear()
            display.set_pixel(step % 16, step // 2, 255, 255, 255)
            display.show()
        elapsed = time.monotonic() - started
        results.append(
            Result(
                OK,
                "sent 32 frames of a walking pixel",
                f"{elapsed:.2f} s total, {32 / elapsed:.1f} frames/second",
            )
        )
        display.clear()
        display.show()
    except Exception as exc:  # noqa: BLE001
        results.append(
            Result(
                FAIL,
                "the panel stopped responding partway through",
                f"{exc}\nThis is what stale firmware looks like: re-copy\n"
                "the firmware onto the Pico by running pi-menu-flash.",
            )
        )
    finally:
        display.close()
    return results


def check_terminal() -> list[Result]:
    from .terminal import find_terminal

    found = find_terminal()
    if found:
        return [Result(OK, f"terminal emulator: {found[0]}")]
    return [
        Result(
            WARN,
            "no terminal emulator found",
            "sudo apt install lxterminal — the menu runs apps without one,\n"
            "but you lose the console messages that explain failures.",
        )
    ]


def check_apps() -> list[Result]:
    from .config import ConfigError, apps_path, load_apps

    try:
        apps = load_apps()
    except ConfigError as exc:
        return [Result(FAIL, "the app list is unusable", str(exc))]
    names = "\n".join(f"{app.id}: {' '.join(app.resolved_command())}" for app in apps)
    return [Result(OK, f"{len(apps)} app(s) listed in {apps_path()}", names)]


# -- the run ------------------------------------------------------------


def run_checks(port: str | None = None, send_frames: bool = True) -> list[Result]:
    """Every check, in the order the data actually flows."""
    results = list(check_environment())
    results += check_dependencies()

    port_results, candidates = check_ports()
    results += port_results

    target = port or (candidates[0] if candidates else None)
    if target is None:
        results.append(
            Result(FAIL, "no panel to test", "Pass --port to name one explicitly.")
        )
        results += check_terminal() + check_apps()
        return results

    results += check_permissions(target)
    handshake, version = check_handshake(target)
    results += handshake

    if version is not None and send_frames:
        results += check_frames(target)
    elif version is not None:
        results.append(Result(WARN, "frame test skipped (--no-frames)"))

    results += check_terminal() + check_apps()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pi-menu-doctor",
        description="Diagnose the link between this machine and the Stellar Unicorn.",
    )
    parser.add_argument("--port", help="serial device to test (default: autodetect)")
    parser.add_argument(
        "--no-frames",
        action="store_true",
        help="skip the part that lights the panel up",
    )
    args = parser.parse_args(argv)

    print("pi-menu doctor")
    print("=" * 62)
    results = run_checks(port=args.port, send_frames=not args.no_frames)
    for result in results:
        print(result.render())
    print("=" * 62)

    failures = [r for r in results if r.level == FAIL]
    warnings = [r for r in results if r.level == WARN]
    if failures:
        print(f"{len(failures)} problem(s) found — see the FAIL lines above.")
        return 1
    if warnings:
        print(f"No blocking problems, but {len(warnings)} warning(s).")
        return 0
    print("Everything checks out. The panel should be working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
