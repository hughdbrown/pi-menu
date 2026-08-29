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

from .. import music as chiptune
from . import render, world as physics
from .level import Level
from .levels import LEVELS, title
from .autopilot import Autopilot
from .progress import Progress
from .routes import ROUTES
from .sound_settings import Sound
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
AUTO_ENTRY = 2
MENU_ENTRIES = 3

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
        music: "chiptune.Player | None" = None,
        sound: Sound = Sound.MUSIC,
        sound_saver: Callable[[Sound], None] | None = None,
    ) -> None:
        self.levels = tuple(levels)
        # A player with nowhere to send notes is silent and harmless,
        # which is what every machine without a panel gets.
        self.music = music if music is not None else chiptune.Player()
        self.sound = sound
        self._sound_saver = sound_saver
        self._jumps_seen = 0
        self._fist_was_out = False
        self.progress = progress if progress is not None else Progress()
        self.screen = Screen.MENU
        self.menu_entry = PLAY_ENTRY
        # Open on the first level not yet finished, so Play means carry
        # on rather than start again.
        self.index = self._first_unfinished()
        self.world: World | None = None
        self.phase = 0
        #: In auto-play the recorded route drives the level, not the keys.
        self.auto = False
        self._pilot: Autopilot | None = None

        self._sink = sink
        self._held: set = set()
        self._countdown = 0

        self._update_music()
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
        elif self.screen is Screen.PLAY:
            if key == BACK:
                self._to_menu()
            elif self.auto and key in (LEFT, RIGHT):
                # Skipping straight to the level you want to film beats
                # waiting for the tour to arrive there.
                step = 1 if key == RIGHT else -1
                self.start((self.index + step) % len(self.levels), auto=True)

        self._update_music()
        self.push()

    def release(self, key: str) -> None:
        self._held.discard(GAME_KEYS.get(key, key))

    def _menu_key(self, key: str) -> None:
        # Left/Right cycle the sound setting -- the menu has no room for
        # a fourth word, so the corner bar is the whole display of it.
        if key in (LEFT, RIGHT):
            order = list(Sound)
            step = 1 if key == RIGHT else -1
            here = order.index(self.sound)
            self.set_sound(order[(here + step) % len(order)])
            return
        if key == UP:
            self.menu_entry = max(0, self.menu_entry - 1)
        elif key == DOWN:
            self.menu_entry = min(MENU_ENTRIES - 1, self.menu_entry + 1)
        elif key == SELECT:
            if self.menu_entry == PLAY_ENTRY:
                self.start(self.index)
            elif self.menu_entry == PICKER_ENTRY:
                self.screen = Screen.PICKER
            else:
                # Auto-play starts wherever the cursor last was, so the
                # way to film level N is: LVLS, move to N, Esc, AUTO.
                # Starting the tour at level one regardless made picking
                # a level and then choosing AUTO feel like the choice
                # had been thrown away -- because it had.
                self.start(self.index, auto=True)

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

    def start(self, index: int, auto: bool = False) -> None:
        """Begin a level.

        Keys still physically down stay down. Clearing them here would
        desync this set from the window's, which only reports a press
        when a key goes *from* up *to* down: after a death with Right
        held, the player would be stuck until they let go and pressed it
        again. The window's key state is the truth; this follows it.
        """
        self.index = index
        self.world = World(self.levels[index])
        self.screen = Screen.PLAY
        self.auto = auto
        self._pilot = Autopilot(ROUTES[self.levels[index].id]) if auto else None
        self._jumps_seen = 0
        self._fist_was_out = False

    def _to_menu(self) -> None:
        self.screen = Screen.MENU
        self.world = None
        self.auto = False
        self._pilot = None

    # -- the clock -------------------------------------------------------

    def tick(self) -> None:
        """Advance one frame of whatever is on screen."""
        self.phase += 1

        if self.screen is Screen.PLAY:
            self._play_tick()
        elif self.screen in (Screen.DEAD, Screen.WON):
            self._flash_tick()

        self._update_music()
        self.music.tick()
        self.push()

    # -- what is playing -------------------------------------------------

    def set_sound(self, mode: Sound) -> None:
        """Switch between music, event sounds, and silence, immediately."""
        self.sound = mode
        if self._sound_saver is not None:
            self._sound_saver(mode)
        self._update_music()

    def _update_music(self) -> None:
        """Keep the speaker in step with the screen and the sound setting.

        Asking for the tune that is already playing does nothing, so this
        is safe to call on every tick and there is no separate bookkeeping
        about what changed.
        """
        if self.sound is Sound.OFF:
            self.music.play(None)
            return
        if self.sound is Sound.MUSIC:
            self.music.play(self._tune_for_screen())
            return
        # Events only: no background tunes, but a death or a win is an
        # event and its jingle still plays.
        if self.screen is Screen.DEAD:
            self.music.play(chiptune.DEATH)
            return
        if self.screen is Screen.WON:
            self.music.play(chiptune.FANFARE)
            return
        playing = self.music.tune
        if playing is not None and not playing.loop and not self.music.finished:
            return  # a blip is mid-flight; let it end
        self.music.play(None)

    def _sound_effects(self, event: Event) -> None:
        """Blip for what just happened, when events are what sounds.

        The counters advance in every mode, so switching to effects
        mid-level starts from now rather than replaying the backlog.
        """
        blip = None
        fist_out = bool(self.world.fist_cells())
        if fist_out and not self._fist_was_out:
            blip = chiptune.FIST_THUD
        self._fist_was_out = fist_out

        if self.world.jumps != self._jumps_seen:
            self._jumps_seen = self.world.jumps
            blip = chiptune.JUMP_BLIP

        if event is Event.COIN:
            blip = chiptune.COIN_BLIP

        if blip is not None and self.sound is Sound.EFFECTS:
            self.music.play(blip, restart=True)

    def _tune_for_screen(self):
        if self.screen is Screen.DEAD:
            return chiptune.DEATH
        if self.screen is Screen.WON:
            return chiptune.FANFARE
        if self.screen is Screen.PLAY:
            return chiptune.level_tune(
                self.index, len(self.levels), self.levels[self.index].boss is not None
            )
        return chiptune.TITLE

    def silence(self) -> None:
        """Stop the music, for leaving the game."""
        self.music.silence()

    def _play_tick(self) -> None:
        if self.auto:
            held = self._pilot.held()
            self._pilot.advance()
        else:
            held = self._held
        event = self.world.step(held)
        self._sound_effects(event)
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
            # No lives to lose: the level simply starts again. In auto
            # this should be unreachable -- the routes are replayed
            # solver output -- but a fresh pilot beats a stuck one.
            self.world.reset()
            self.screen = Screen.PLAY
            if self.auto:
                self._pilot = Autopilot(ROUTES[self.world.level.id])
        elif self.index + 1 < len(self.levels):
            self.start(self.index + 1, auto=self.auto)
        else:
            self._to_menu()

    # -- output ----------------------------------------------------------

    def framebuffer(self) -> bytes:
        if self.screen is Screen.MENU:
            return render.draw_menu(self.menu_entry, self.phase, sound=self.sound.value)
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
            return (
                "menu  ·  Up/Down to choose, Enter to pick  ·  "
                f"Left/Right: sound ({self.sound.value})"
            )
        if self.screen is Screen.PICKER:
            return (
                f"choose a level  ·  {title(self.index)}  ·  "
                f"{len(self.finished_indexes())} of {len(self.levels)} finished"
            )
        if self.screen is Screen.DEAD:
            return f"{title(self.index)}  ·  ouch — starting again"
        if self.screen is Screen.WON:
            return f"{title(self.index)}  ·  finished!"
        auto = "auto-play  ·  " if self.auto else ""
        return (
            f"{auto}{title(self.index)}  ·  {len(self.world.coins)} coins left"
            f"{'' if self.world.coins else '  ·  the goal is open'}"
        )
