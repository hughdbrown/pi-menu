"""Serial backend: ships frames to the frame server running on the Pico."""

from __future__ import annotations

import sys
import time

from .base import Display
from . import protocol as proto


class StellarUnicornNotFound(RuntimeError):
    """No Stellar Unicorn could be opened."""


def _pyserial():
    """Import pyserial lazily so the other backends work without it."""
    try:
        import serial
        import serial.tools.list_ports as list_ports
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise StellarUnicornNotFound(
            "pyserial is not installed; run 'pip install pyserial'"
        ) from exc
    return serial, list_ports


def find_port() -> str | None:
    """Return the device path of an attached Pico, or None.

    Ports whose USB vendor id matches the Pico are preferred. If none
    advertise that id -- some USB-serial bridges do not -- fall back to
    the first ``ttyACM``/``usbmodem`` port, which is what the Pico
    enumerates as.
    """
    try:
        _, list_ports = _pyserial()
    except StellarUnicornNotFound:
        return None

    ports = list(list_ports.comports())
    for port in ports:
        if getattr(port, "vid", None) == proto.PICO_VID:
            return port.device
    for port in ports:
        name = port.device.lower()
        if "ttyacm" in name or "usbmodem" in name:
            return port.device
    return None


class SerialDisplay(Display):
    """Drives a Stellar Unicorn over USB serial.

    The Pico acknowledges every frame. Waiting for that ack is what keeps
    the Pi from running ahead of the panel and filling the kernel's
    write buffer with frames nobody has drawn yet.
    """

    def __init__(
        self,
        port: str | None = None,
        baud: int = proto.BAUD,
        brightness: float = 1.0,
        timeout: float = 2.0,
    ) -> None:
        serial, _ = _pyserial()

        self._port_name = port or find_port()
        if not self._port_name:
            raise StellarUnicornNotFound(
                "no Stellar Unicorn found; pass --port to name one explicitly"
            )

        try:
            # write_timeout matters: without it a panel that stops reading
            # would block the caller forever inside write().
            self._serial = serial.Serial(
                self._port_name, baud, timeout=timeout, write_timeout=timeout
            )
        except Exception as exc:
            # pyserial's message already names the port, so do not repeat it.
            raise StellarUnicornNotFound(str(exc)) from exc

        # The Pico reboots when the port opens; give it a moment to come up.
        time.sleep(0.3)
        self._serial.reset_input_buffer()

        self.firmware_version = self._handshake()
        if self.firmware_version is None:
            self._serial.close()
            raise StellarUnicornNotFound(
                f"{self._port_name} did not answer as a Stellar Unicorn "
                f"(last reply: {self._last_reply!r}); copy "
                "the firmware onto the Pico by running pi-menu-flash"
            )

        super().__init__(brightness=brightness)

    @property
    def port(self) -> str:
        return self._port_name

    @property
    def description(self) -> str:
        return f"Stellar Unicorn on {self._port_name} (firmware v{self.firmware_version})"

    @property
    def is_panel(self) -> bool:
        return True

    @property
    def firmware_is_current(self) -> bool:
        return self.firmware_version >= proto.PROTOCOL_VERSION

    def _handshake(self, attempts: int = 3) -> int | None:
        """Ping the panel, returning its protocol version or None.

        Several attempts, because opening the port resets the Pico and
        its startup chatter can arrive ahead of the first reply.
        """
        self._last_reply = b""
        for _ in range(attempts):
            self._serial.write(proto.encode_ping())
            self._last_reply = self._serial.readline()
            version = proto.parse_hello(self._last_reply)
            if version is not None:
                return version
        return None

    def _flush(self, framebuffer: bytes) -> None:
        self._serial.write(proto.encode_blit(framebuffer))
        self._await_ack()

    def _apply_brightness(self, brightness: float) -> None:
        self._serial.write(proto.encode_brightness(round(brightness * 255)))
        self._await_ack()

    def play_tone(
        self, channel: int, waveform: int, frequency: int, volume: int
    ) -> None:
        self._serial.write(proto.encode_tone(channel, waveform, frequency, volume))
        self._await_ack()

    def hush(self) -> None:
        self._serial.write(proto.encode_hush())
        self._await_ack()

    @property
    def has_audio(self) -> bool:
        return True

    def _await_ack(self) -> None:
        """Read one ack line, tolerating a slow or silent panel.

        A dropped ack is not worth killing a running game over, so this
        warns once per occurrence and lets the next frame try again.
        """
        line = self._serial.readline().strip()
        if line != proto.ACK:
            print(
                f"warning: Stellar Unicorn did not acknowledge a frame "
                f"(got {line!r})",
                file=sys.stderr,
            )

    def close(self) -> None:
        if getattr(self, "_serial", None) is None:
            return
        try:
            if self._serial.is_open:
                self._serial.write(proto.encode_clear())
                self._serial.close()
        except Exception:
            pass
        self._serial = None
