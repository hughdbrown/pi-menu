"""MicroPython source that runs on the Stellar Unicorn's Pico.

Shipped inside the package so ``pi-menu-flash`` can find it from an
installed virtualenv, with no source checkout present. Nothing here is
importable on CPython -- it is data, read as text and copied to the
board.
"""

from pathlib import Path

FRAME_SERVER = Path(__file__).with_name("stellar_frame_server.py")

__all__ = ["FRAME_SERVER"]
