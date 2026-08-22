"""Copying the firmware onto the board.

A fake MicroPython REPL runs behind a pseudo-terminal and really
executes what the flasher sends it, writing into an in-memory
filesystem. So the file that ends up "on the board" is compared with
the source byte for byte, rather than the transfer being mocked out.
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from pi_menu import flash
from pi_menu.display import protocol as proto
from pi_menu.firmware import FRAME_SERVER

pytest.importorskip("serial")

pytestmark = pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="needs pseudo-terminals"
)

FRIENDLY_PROMPT = b"\r\n>>> "
BANNER = b"\r\nMicroPython v1.22.0 on Raspberry Pi Pico W\r\n>>> "


class FakeRepl:
    """Enough of MicroPython's REPL to accept a file.

    Raw-REPL blocks are executed for real in a persistent namespace, so
    the flasher's chunked ``open``/``write``/``close`` sequence has to
    actually work rather than merely look right.
    """

    def __init__(self, fd):
        self.fd = fd
        self.raw = False
        self.pending = bytearray()
        self.files: dict[str, bytes] = {}
        self.reboots = 0
        self.interrupts = 0
        self.namespace: dict = {"open": self._open, "print": self._print}
        self._printed = bytearray()
        self.stop = threading.Event()

    # -- the fake filesystem --------------------------------------------

    def _open(self, name, mode="r"):
        repl = self

        class Handle:
            def __init__(self):
                self.buffer = bytearray()
                self.reading = "r" in mode

            def write(self, data):
                self.buffer.extend(data)
                return len(data)

            def read(self):
                return repl.files.get(name, b"")

            def close(self):
                if not self.reading:
                    repl.files[name] = bytes(self.buffer)

        return Handle()

    def _print(self, *parts):
        self._printed.extend(" ".join(str(p) for p in parts).encode() + b"\r\n")

    # -- the byte-level state machine -----------------------------------

    def _send(self, data: bytes) -> None:
        os.write(self.fd, data)

    def _execute(self) -> None:
        code = bytes(self.pending).decode("utf-8")
        self.pending.clear()
        self._printed.clear()
        self._send(b"OK")
        try:
            exec(code, self.namespace)  # noqa: S102 - that is the point
            self._send(bytes(self._printed) + b"\x04" + b"\x04>")
        except Exception as exc:  # noqa: BLE001
            self._send(b"\x04" + repr(exc).encode() + b"\x04>")

    def serve(self) -> None:
        while not self.stop.is_set():
            try:
                data = os.read(self.fd, 1024)
            except OSError:
                return
            if not data:
                return
            for byte in data:
                if byte == 0x01:  # Ctrl-A
                    self.raw = True
                    self.pending.clear()
                    self._send(b"\r\n" + flash.RAW_PROMPT)
                elif byte == 0x02:  # Ctrl-B
                    self.raw = False
                    self._send(BANNER)
                elif byte == 0x03:  # Ctrl-C
                    self.interrupts += 1
                    self.pending.clear()
                    if not self.raw:
                        self._send(FRIENDLY_PROMPT)
                elif byte == 0x04:  # Ctrl-D
                    if self.raw:
                        self._execute()
                    else:
                        self.reboots += 1
                        self._send(b"\r\nMPY: soft reboot" + BANNER)
                elif self.raw:
                    self.pending.append(byte)
                elif byte in (0x0A, 0x0D):
                    self._send(FRIENDLY_PROMPT)


@pytest.fixture
def board():
    """A fake Pico at its REPL, and the serial path that reaches it."""
    master_fd, slave_fd = os.openpty()
    repl = FakeRepl(master_fd)
    thread = threading.Thread(target=repl.serve, daemon=True)
    thread.start()
    try:
        yield repl, os.ttyname(slave_fd)
    finally:
        repl.stop.set()
        for fd in (slave_fd, master_fd):
            try:
                os.close(fd)
            except OSError:
                pass
        thread.join(timeout=2.0)


# -- the transfer --------------------------------------------------------


def test_the_firmware_arrives_on_the_board_byte_for_byte(board):
    repl, path = board

    flash.flash(port=path, log=lambda *a, **k: None)

    assert repl.files["main.py"] == FRAME_SERVER.read_bytes()


def test_it_lands_as_main_py_so_it_runs_at_power_on(board):
    repl, path = board
    flash.flash(port=path, log=lambda *a, **k: None)
    assert list(repl.files) == ["main.py"]


def test_the_board_is_restarted_so_the_new_file_takes_effect(board):
    repl, path = board
    flash.flash(port=path, log=lambda *a, **k: None)
    assert repl.reboots >= 1


def test_a_file_larger_than_one_chunk_is_split_and_rejoined(board):
    repl, path = board
    assert FRAME_SERVER.stat().st_size > flash.CHUNK  # otherwise this proves nothing

    flash.flash(port=path, log=lambda *a, **k: None)

    assert len(repl.files["main.py"]) == FRAME_SERVER.stat().st_size


def test_an_arbitrary_source_file_can_be_sent_under_any_name(board, tmp_path):
    repl, path = board
    source = tmp_path / "thing.py"
    source.write_bytes(b"# quotes ' \" and a backslash \\ and bytes \x00\x03\xff\n" * 20)

    flash.flash(port=path, source=source, remote_name="lib.py", log=lambda *a, **k: None)

    assert repl.files["lib.py"] == source.read_bytes()


def test_verification_catches_a_corrupted_copy(board, monkeypatch):
    repl, path = board

    original = flash.write_file

    def lossy(repl_, name, data, log):
        original(repl_, name, data[:-5], log)  # drop the tail

    monkeypatch.setattr(flash, "write_file", lossy)

    with pytest.raises(flash.FlashError, match="does not match"):
        flash.flash(port=path, log=lambda *a, **k: None)


def test_missing_firmware_is_reported_before_anything_is_opened(tmp_path):
    with pytest.raises(flash.FlashError, match="no firmware to copy"):
        flash.flash(source=tmp_path / "absent.py", log=lambda *a, **k: None)


def test_no_board_is_reported_with_advice(monkeypatch):
    monkeypatch.setattr(flash, "find_port", lambda: None)
    with pytest.raises(flash.FlashError, match="no Pico found"):
        flash.flash(log=lambda *a, **k: None)


def test_a_board_that_never_reaches_its_repl_says_how_to_force_it():
    """The A-button hint is the only way out once Ctrl-C is disabled."""
    master_fd, slave_fd = os.openpty()  # nothing is listening
    try:
        with pytest.raises(flash.FlashError, match="A button"):
            flash.flash(port=os.ttyname(slave_fd), log=lambda *a, **k: None)
    finally:
        os.close(master_fd)
        os.close(slave_fd)


# -- standing a running frame server down --------------------------------


def test_a_running_frame_server_is_asked_to_step_aside(pico):
    """Ctrl-C cannot stop it, so it has to be asked over the protocol."""
    import serial

    firmware, path = pico
    link = serial.Serial(path, proto.BAUD, timeout=2.0)
    try:
        assert flash.stand_down_frame_server(link) is True
    finally:
        link.close()


def test_the_firmware_restores_ctrl_c_before_it_leaves(pico):
    """Otherwise the next tool along would have no way to interrupt."""
    import serial

    from conftest import DRIVER

    firmware, path = pico
    assert DRIVER.interrupt_char == -1  # disabled while serving

    link = serial.Serial(path, proto.BAUD, timeout=2.0)
    try:
        flash.stand_down_frame_server(link)
    finally:
        link.close()

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and DRIVER.interrupt_char != 3:
        time.sleep(0.01)
    assert DRIVER.interrupt_char == 3


def test_a_board_at_its_repl_reports_no_frame_server(board):
    import serial

    _, path = board
    link = serial.Serial(path, proto.BAUD, timeout=2.0)
    try:
        assert flash.stand_down_frame_server(link) is False
    finally:
        link.close()


def test_the_firmware_ships_inside_the_package():
    """pi-menu-flash runs from an installed venv with no checkout present.

    That only works while the file lives under the package directory, so
    a move back out to the repo root would break it silently.
    """
    from pathlib import Path

    import pi_menu

    package_root = Path(pi_menu.__file__).resolve().parent
    assert FRAME_SERVER.is_file()
    assert package_root in FRAME_SERVER.resolve().parents
