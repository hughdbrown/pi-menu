"""Screens, transitions, and what the panel is showing at any moment.

The panel is the whole interface: the menu, the level picker and the
game are all drawn on it, and the arrow keys drive all three. So this
owns a small state machine rather than a game loop, and every way in and
out of every screen pushes a frame.

Nothing here knows a display exists. Like :class:`~pi_menu.life.session.LifeSession`
it takes a sink -- a callable handed a complete framebuffer -- which is a
:class:`~pi_menu.display.pump.FramePump` in the app and a list in the
tests. That is what makes every transition checkable pixel by pixel.
"""

from __future__ import annotations

import enum
from typing import Callable, Sequence

from . import render, world as physics
from .level import Level
from .levels import LEVELS, title
from .progress import Progress
from .world import Event, World

#: Called with a complete framebuffer whenever the panel should change.
Sink = Callable[[bytes], None]

# Keys, named for what the player pressed rather than for what Tk calls it.
LEFT = "left"
RIGHT = "right"
UP = "up"
DOWN = "down"
SELECT = "select"
BACK = "back"

#: Which key does what once a level is running.
GAME_KEYS = {LEFT: physics.LEFT, RIGHT: physics.RIGHT, UP: physics.JUMP}

PLAY_ENTRY = 0
PICKER_ENTRY = 1
MENU_ENTRIES = 2

#: How long a death or a win holds the screen before moving on.
FLASH_TICKS = 8


class Screen(enum.Enum):
    MENU = "menu"
    PICKER = "picker"
    PLAY = "play"
    DEAD = "dead"
    WON = "won"


class PlatformSession:
    """One sitting: the menu, the picker, and whichever level is running."""

    def __init__(
        self,
        sink: Sink,
        progress: Progress | None = None,
        levels: Sequence[Level] = LEVELS,
    ) -> None:
        self.levels = tuple(levels)
        self.progress = progress if progress is not None else Progress()
        self.screen = Screen.MENU
        self.menu_entry = PLAY_ENTRY
        # Open on the first level not yet finished, so Play means carry
        # on rather than start again.
        self.index = self._first_unfinished()
        self.world: World | None = None
        self.phase = 0

        self._sink = sink
        self._held: set = set()
        self._countdown = 0

        self.push()

    def _first_unfinished(self) -> int:
        for index, level in enumerate(self.levels):
            if not self.progress.is_done(level.id):
                return index
        return 0

    # -- what the picker paints ------------------------------------------

    def finished_indexes(self) -> set:
        return {
            index
            for index, level in enumerate(self.levels)
            if self.progress.is_done(level.id)
        }

    @property
    def held(self) -> frozenset:
        """The game keys currently held down."""
        return frozenset(self._held)

    # -- input -----------------------------------------------------------

    def press(self, key: str) -> None:
        if key in GAME_KEYS:
            self._held.add(GAME_KEYS[key])

        if self.screen is Screen.MENU:
            self._menu_key(key)
        elif self.screen is Screen.PICKER:
            self._picker_key(key)
        elif self.screen is Screen.PLAY and key == BACK:
            self._to_menu()

        self.push()

    def release(self, key: str) -> None:
        self._held.discard(GAME_KEYS.get(key, key))

    def _menu_key(self, key: str) -> None:
        if key == UP:
            self.menu_entry = max(0, self.menu_entry - 1)
        elif key == DOWN:
            self.menu_entry = min(MENU_ENTRIES - 1, self.menu_entry + 1)
        elif key == SELECT:
            if self.menu_entry == PLAY_ENTRY:
                self.start(self.index)
            else:
                self.screen = Screen.PICKER

    def _picker_key(self, key: str) -> None:
        last = len(self.levels) - 1
        if key == LEFT:
            self.index = max(0, self.index - 1)
        elif key == RIGHT:
            self.index = min(last, self.index + 1)
        elif key == UP:
            self.index = max(0, self.index - render.PICKER_COLUMNS)
        elif key == DOWN:
            self.index = min(last, self.index + render.PICKER_COLUMNS)
        elif key == SELECT:
            self.start(self.index)
        elif key == BACK:
            self.screen = Screen.MENU

    # -- transitions -----------------------------------------------------

    def start(self, index: int) -> None:
        """Begin a level. Keys held while choosing it do not carry over."""
        self.index = index
        self.world = World(self.levels[index])
        self.screen = Screen.PLAY
        self._held.clear()

    def _to_menu(self) -> None:
        self.screen = Screen.MENU
        self.world = None
        self._held.clear()

    # -- the clock -------------------------------------------------------

    def tick(self) -> None:
        """Advance one frame of whatever is on screen."""
        self.phase += 1

        if self.screen is Screen.PLAY:
            self._play_tick()
        elif self.screen in (Screen.DEAD, Screen.WON):
            self._flash_tick()

        self.push()

    def _play_tick(self) -> None:
        event = self.world.step(self._held)
        if event is Event.DIED:
            self.screen = Screen.DEAD
            self._countdown = FLASH_TICKS
        elif event is Event.WON:
            self.progress.mark(self.world.level.id)
            self.screen = Screen.WON
            self._countdown = FLASH_TICKS

    def _flash_tick(self) -> None:
        self._countdown -= 1
        if self._countdown > 0:
            return

        if self.screen is Screen.DEAD:
            # No lives to lose: the level simply starts again.
            self.world.reset()
            self.screen = Screen.PLAY
            self._held.clear()
        elif self.index + 1 < len(self.levels):
            self.start(self.index + 1)
        else:
            self._to_menu()

    # -- output ----------------------------------------------------------

    def framebuffer(self) -> bytes:
        if self.screen is Screen.MENU:
            return render.draw_menu(self.menu_entry, self.phase)
        if self.screen is Screen.PICKER:
            return render.draw_picker(
                self.index, self.finished_indexes(), len(self.levels), self.phase
            )
        if self.screen is Screen.DEAD:
            return self._flash_frame(render.DEATH_FLASH)
        if self.screen is Screen.WON:
            return self._flash_frame(render.WIN_FLASH)
        return render.draw_world(self.world, self.phase)

    def _flash_frame(self, colour: tuple[int, int, int]) -> bytes:
        """Blink between the colour and the level, so it reads as a flash.

        Holding one flat colour for half a second looks like the program
        has stopped; alternating with the level it happened on does not.
        """
        if (self._countdown // 2) % 2 == 0:
            return render.flash(colour)
        return render.draw_world(self.world, self.phase)

    def push(self) -> None:
        self._sink(self.framebuffer())

    def status_text(self) -> str:
        if self.screen is Screen.MENU:
            return "menu  ·  Up/Down to choose, Enter to pick"
        if self.screen is Screen.PICKER:
            return (
                f"choose a level  ·  {title(self.index)}  ·  "
                f"{len(self.finished_indexes())} of {len(self.levels)} finished"
            )
        if self.screen is Screen.DEAD:
            return f"{title(self.index)}  ·  ouch — starting again"
        if self.screen is Screen.WON:
            return f"{title(self.index)}  ·  finished!"
        return (
            f"{title(self.index)}  ·  {len(self.world.coins)} coins left"
            f"{'' if self.world.coins else '  ·  the goal is open'}"
        )
