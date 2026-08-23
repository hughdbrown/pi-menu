"""Turning key events into the set of keys actually held down.

Kept out of the Tk module so it can be tested anywhere, and because the
rule it enforces is the only subtle thing about the input handling.

X11 auto-repeat does not send one press and one release for a held key.
It sends ``KeyRelease`` immediately followed by ``KeyPress``, over and
over, for as long as the key is down. Taken at face value that says the
player is letting go several times a second -- which in a platform game
means running stops dead and a jump cannot be held. So a release is
deferred to the next tick and cancelled if its press arrives first.
"""

from __future__ import annotations

from .session import BACK, DOWN, LEFT, RIGHT, SELECT, UP

#: Tk keysym -> the key name the session understands.
KEYSYMS = {
    "Left": LEFT,
    "Right": RIGHT,
    "Up": UP,
    "Down": DOWN,
    "Return": SELECT,
    "KP_Enter": SELECT,
    "space": SELECT,
    "Escape": BACK,
    "BackSpace": BACK,
}


class HeldKeys:
    """Which keys are down, with auto-repeat filtered out."""

    def __init__(self) -> None:
        self._held: set = set()
        self._releasing: set = set()

    @property
    def held(self) -> frozenset:
        return frozenset(self._held)

    def press(self, key: str) -> bool:
        """Note a press. True only if the key was not already down."""
        self._releasing.discard(key)
        if key in self._held:
            return False
        self._held.add(key)
        return True

    def release(self, key: str) -> None:
        """Note a release. It does not take effect until :meth:`settle`."""
        if key in self._held:
            self._releasing.add(key)

    def settle(self) -> list:
        """Apply any release that was not cancelled. Call once a tick."""
        released = sorted(self._releasing)
        self._held -= self._releasing
        self._releasing.clear()
        return released

    def clear(self) -> None:
        self._held.clear()
        self._releasing.clear()
