"""Chiptune for the Stellar Unicorn's speaker.

The Pico has a synth on board but no idea what a tune is. Every note and
every rest is decided here and sent as it falls due, the same way every
pixel is: the panel plays what it is told, on three channels -- a square
lead, a triangle bass, and noise for percussion. That is the sound of a
1980s console, and it is what a sixteen-pixel platform game should sound
like.

A tune is three strings, one per channel, read a step at a time::

    "e4  -  g4  .  e4"

A note name starts it, ``-`` holds what is already sounding, and ``.``
is silence. Steps are a fixed number of ticks, so a tune's tempo is how
many ticks a step lasts.
"""

from __future__ import annotations

from typing import Iterator

from .display.protocol import WAVE_NOISE, WAVE_SQUARE, WAVE_TRIANGLE

LEAD, BASS, DRUM = 0, 1, 2

HOLD = "-"
REST = "."

#: A4, and the twelfth root of two, are all a tuning needs.
A4 = 440.0
SEMITONES = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")


def frequency(note: str) -> int:
    """Hertz for a note like ``c4``, ``f#3`` or ``a5``."""
    name = note.strip().lower()
    octave = int(name[-1])
    step = SEMITONES.index(name[:-1])
    # a4 is the ninth semitone of octave 4; everything else follows.
    half_steps = (octave - 4) * 12 + step - SEMITONES.index("a")
    return int(round(A4 * (2 ** (half_steps / 12))))


class Voice:
    """One channel's settings: what it sounds like and how loud."""

    def __init__(self, waveform: int, volume: int) -> None:
        self.waveform = waveform
        self.volume = volume


VOICES = {
    LEAD: Voice(WAVE_SQUARE, 90),
    BASS: Voice(WAVE_TRIANGLE, 110),
    DRUM: Voice(WAVE_NOISE, 60),
}


class Tune:
    """Three tracks read in step, and how fast to read them."""

    def __init__(self, name: str, lead: str, bass: str = "", drum: str = "",
                 ticks_per_step: int = 4, loop: bool = True) -> None:
        self.name = name
        self.tracks = {
            LEAD: lead.split(),
            BASS: bass.split(),
            DRUM: drum.split(),
        }
        self.ticks_per_step = ticks_per_step
        self.loop = loop
        self.steps = max((len(track) for track in self.tracks.values()), default=0)

    def at(self, channel: int, step: int) -> str | None:
        """The token for one channel at one step, or None past the end."""
        track = self.tracks[channel]
        if not track:
            return None
        if step >= len(track):
            return REST if not self.loop else track[step % len(track)]
        return track[step]

    def __repr__(self) -> str:
        return f"Tune({self.name!r}, {self.steps} steps)"


class Player:
    """Reads a tune out to a panel, one tick at a time.

    Holds no timer of its own: the app already ticks twenty times a
    second for the game, and a second clock would only be a second thing
    to drift.
    """

    def __init__(self, sink=None) -> None:
        #: Called as ``sink(channel, waveform, frequency, volume)``.
        self._sink = sink
        self.tune: Tune | None = None
        self.step = 0
        self.finished = False
        self._tick = 0
        self._sounding: dict = {}
        #: Loudness, 0.0 to 1.0, applied to every note as it is sent.
        self.music_gain = 1.0
        self.effects_gain = 1.0
        #: A short one-shot playing over the music, borrowing channels.
        self._effect: Tune | None = None
        self._effect_step = 0
        self._effect_tick = 0

    def play(self, tune: Tune | None, restart: bool = False) -> None:
        """Start a tune from the top. The same tune again is left alone,
        unless ``restart`` asks for it -- which is how one sound effect
        can fire twice in a row."""
        if tune is self.tune and not restart:
            return
        self.silence()
        self.tune = tune
        self.step = 0
        self._tick = 0
        self.finished = tune is None
        if tune is not None:
            self._sound_step(0)

    def effect(self, tune: Tune) -> None:
        """Fire a short one-shot over whatever is playing.

        The effect's channels borrow their voices from the music until
        it ends, then hand back whatever note the music was holding.
        """
        self._effect = tune
        self._effect_step = 0
        self._effect_tick = 0
        self._effect_sound_step(0)

    def silence(self) -> None:
        """Stop everything that is sounding."""
        self._effect = None
        for channel in list(self._sounding):
            self._emit(channel, 0, 0)
        self._sounding.clear()

    def tick(self) -> None:
        """Advance one game tick, sounding whatever falls due."""
        self._tick_music()
        self._tick_effect()

    def _tick_music(self) -> None:
        if self.tune is None or self.finished:
            return
        self._tick += 1
        if self._tick < self.tune.ticks_per_step:
            return
        self._tick = 0
        self.step += 1
        if self.step >= self.tune.steps:
            if not self.tune.loop:
                self.silence()
                self.finished = True
                return
            self.step = 0
        self._sound_step(self.step)

    def _tick_effect(self) -> None:
        if self._effect is None:
            return
        self._effect_tick += 1
        if self._effect_tick < self._effect.ticks_per_step:
            return
        self._effect_tick = 0
        self._effect_step += 1
        if self._effect_step >= self._effect.steps:
            self._end_effect()
        else:
            self._effect_sound_step(self._effect_step)

    def _borrowed(self) -> set:
        """The channels the current effect is using."""
        if self._effect is None:
            return set()
        return {
            channel
            for channel, track in self._effect.tracks.items()
            if track
        }

    def _sound_step(self, step: int) -> None:
        borrowed = self._borrowed()
        for channel, voice in VOICES.items():
            token = self.tune.at(channel, step)
            if token is None or token == HOLD:
                continue
            if token == REST:
                if channel in self._sounding:
                    if channel not in borrowed:
                        self._emit(channel, 0, 0)
                    del self._sounding[channel]
                continue
            hertz = frequency(token)
            # The bookkeeping happens either way, so a borrowed channel
            # can pick its tune back up the moment the effect ends.
            if channel not in borrowed:
                self._emit(channel, hertz, self._gained(voice.volume, self.music_gain))
            self._sounding[channel] = hertz

    def _effect_sound_step(self, step: int) -> None:
        for channel, voice in VOICES.items():
            token = self._effect.at(channel, step)
            if token is None or token == HOLD:
                continue
            if token == REST:
                self._emit(channel, 0, 0)
                continue
            self._emit(
                channel, frequency(token), self._gained(voice.volume, self.effects_gain)
            )

    def _end_effect(self) -> None:
        borrowed = self._borrowed()
        self._effect = None
        for channel in borrowed:
            held = self._sounding.get(channel)
            if held is not None:
                self._emit(channel, held, self._gained(VOICES[channel].volume, self.music_gain))
            else:
                self._emit(channel, 0, 0)

    @staticmethod
    def _gained(volume: int, gain: float) -> int:
        return int(round(volume * max(0.0, min(1.0, gain))))

    def _emit(self, channel: int, hertz: int, volume: int) -> None:
        if self._sink is not None:
            self._sink(channel, VOICES[channel].waveform, hertz, volume)

    def notes_sounding(self) -> Iterator:
        yield from self._sounding.items()


# ======================================================================
# The tunes. All original -- written for this game, in the style of the
# consoles it looks like, not transcribed from anything.
# ======================================================================

#: The menu. Bright, unhurried, and content to loop for a while.
TITLE = Tune(
    "title",
    lead=(
        "e5 . g5 . e5 . c5 . d5 . e5 . d5 . b4 . "
        "c5 . e5 . g5 . e5 . f5 . e5 . d5 . c5 . "
        "g4 . c5 . e5 . g5 . a5 . g5 . e5 . c5 . "
        "d5 . f5 . a5 . f5 . e5 . d5 . c5 . . . "
    ),
    bass=(
        "c3 - - - - - - - a2 - - - - - - - "
        "f2 - - - - - - - g2 - - - - - - - "
        "c3 - - - - - - - a2 - - - - - - - "
        "f2 - - - - - - - g2 - - - - - - - "
    ),
    drum=("c2 . g3 . c2 . g3 . " * 8),
    ticks_per_step=3,
)

#: Levels one through however many. Quick, and stays out of the way.
FIELD = Tune(
    "field",
    lead=(
        "c5 e5 g5 e5 c5 e5 g5 a5 g5 e5 c5 e5 d5 . . . "
        "d5 f5 a5 f5 d5 f5 a5 b5 a5 f5 d5 f5 e5 . . . "
        "e5 g5 c6 g5 e5 g5 c6 . b5 g5 e5 g5 a5 . . . "
        "g5 e5 c5 e5 d5 c5 b4 c5 g4 . c5 . e5 . . . "
    ),
    bass=(
        "c3 . c3 . g2 . g2 . a2 . a2 . e3 . e3 . "
        "d3 . d3 . a2 . a2 . b2 . b2 . f3 . f3 . "
        "e3 . e3 . b2 . b2 . c3 . c3 . g2 . g2 . "
        "f3 . f3 . c3 . c3 . g2 . g2 . c3 . . . "
    ),
    drum=("c2 . g3 g3 c2 . g3 . " * 8),
    ticks_per_step=3,
)

#: The second half. Same idea, minor, a little more urgent.
DEEPER = Tune(
    "deeper",
    lead=(
        "a4 c5 e5 c5 a4 c5 e5 f5 e5 c5 a4 c5 b4 . . . "
        "g4 b4 d5 b4 g4 b4 d5 e5 d5 b4 g4 b4 a4 . . . "
        "f4 a4 c5 a4 f4 a4 c5 d5 c5 a4 f4 a4 g4 . . . "
        "e5 d5 c5 b4 a4 b4 c5 d5 e5 . a4 . . . . . "
    ),
    bass=(
        "a2 . a2 . e2 . e2 . f2 . f2 . c3 . c3 . "
        "g2 . g2 . d2 . d2 . e2 . e2 . b2 . b2 . "
        "f2 . f2 . c3 . c3 . d3 . d3 . a2 . a2 . "
        "e3 . e3 . b2 . b2 . a2 . a2 . a2 . . . "
    ),
    drum=("c2 . g3 . c2 g3 g3 . " * 8),
    ticks_per_step=3,
)

#: A boss. Low, slow and chromatic, so it never quite settles.
DEMON = Tune(
    "demon",
    lead=(
        "d4 . d4 . d#4 . d4 . a4 . g#4 . g4 . f4 . "
        "d4 . d4 . f4 . d4 . a#4 . a4 . g#4 . g4 . "
        "a4 . a#4 . a4 . g#4 . g4 . f#4 . f4 . e4 . "
        "d4 . . . a3 . . . d4 . . . . . . . "
    ),
    bass=(
        "d2 - - - - - - - d2 - - - - - - - "
        "d2 - - - - - - - c2 - - - - - - - "
        "a#1 - - - - - - - a1 - - - - - - - "
        "d2 - - - - - - - a1 - - - - - - - "
    ),
    drum=("c2 c2 . g3 c2 . g3 . " * 8),
    ticks_per_step=4,
)

#: Level sixty. A victory lap: four to the floor, a hook that keeps
#: climbing, and no intention of letting the moment pass quietly. It is
#: an original piece written for this game -- there is a well-known
#: eighties record you might have expected here, but its melody is
#: somebody's copyright, and writing it out as note data is copying it.
FINALE = Tune(
    "finale",
    lead=(
        "f5 . f5 g5 a5 . a5 . g5 . f5 . c5 . . . "
        "d5 . d5 e5 f5 . f5 . e5 . d5 . a4 . . . "
        "a#4 . c5 . d5 . f5 . e5 . d5 . c5 . . . "
        "c5 . d5 . e5 . f5 . g5 . a5 . f5 . . . "
        "a5 . a5 g5 f5 . f5 . e5 . f5 . g5 . . . "
        "a5 . c6 . a5 . f5 . g5 . e5 . d5 . . . "
        "a#5 . a5 . g5 . f5 . e5 . d5 . c5 . . . "
        "f5 . a5 . c6 . a5 . f5 . . . . . . . "
    ),
    bass=(
        "f2 f2 f2 f2 f2 f2 f2 f2 d2 d2 d2 d2 d2 d2 d2 d2 "
        "a#1 a#1 a#1 a#1 a#1 a#1 a#1 a#1 c2 c2 c2 c2 c2 c2 c2 c2 "
        "a#1 a#1 a#1 a#1 a#1 a#1 a#1 a#1 f2 f2 f2 f2 f2 f2 f2 f2 "
        "d2 d2 d2 d2 d2 d2 d2 d2 c2 c2 c2 c2 c2 c2 c2 c2 "
        "f2 f2 f2 f2 f2 f2 f2 f2 d2 d2 d2 d2 d2 d2 d2 d2 "
        "a#1 a#1 a#1 a#1 a#1 a#1 a#1 a#1 c2 c2 c2 c2 c2 c2 c2 c2 "
        "a#1 a#1 a#1 a#1 a#1 a#1 a#1 a#1 f2 f2 f2 f2 f2 f2 f2 f2 "
        "d2 d2 d2 d2 d2 d2 d2 d2 c2 c2 c2 c2 c2 c2 c2 c2 "
    ),
    drum=("c2 . g3 . c2 . g3 g3 " * 16),
    ticks_per_step=3,
)

#: Four notes down. Plays once and stops.
DEATH = Tune(
    "death",
    lead="e5 d#5 d5 c#5 c5 b4 a#4 a4",
    bass="a2 - - - a1 - - -",
    ticks_per_step=3,
    loop=False,
)

#: Four notes up. Plays once and stops.
FANFARE = Tune(
    "fanfare",
    lead="c5 e5 g5 c6 . g5 c6 .",
    bass="c3 - - - c3 - - -",
    drum="c2 . c2 . g3 g3 g3 .",
    ticks_per_step=3,
    loop=False,
)

#: Option three. Bouncing and syncopated, wider leaps than FIELD, and a
#: bass that walks instead of pumping.
SKYWAYS = Tune(
    "skyways",
    lead=(
        "g5 . . e5 . g5 . c6 . g5 . e5 g5 . . . "
        "a5 . . f5 . a5 . d6 . a5 . f5 a5 . . . "
        "b5 . . g5 . b5 . d6 . c6 . b5 g5 . . . "
        "c6 . g5 . e5 . g5 . c5 . e5 . c5 . . . "
    ),
    bass=(
        "c3 . d3 . e3 . g3 . a3 . g3 . e3 . d3 . "
        "d3 . e3 . f3 . a3 . b3 . a3 . f3 . e3 . "
        "g2 . a2 . b2 . d3 . g3 . d3 . b2 . a2 . "
        "c3 . e3 . g3 . e3 . c3 . g2 . c3 . . . "
    ),
    drum=("c2 . . g3 . . c2 . c2 . . g3 . g3 . . " * 4),
    ticks_per_step=3,
)

#: Option four. Sparse and minor, long notes, room to breathe -- for
#: anyone who found the others busy.
CAVERNS = Tune(
    "caverns",
    lead=(
        "e5 - - . b4 - - . c5 - - . g4 - - . "
        "a4 - - . e5 - - . d5 - c5 - b4 - - . "
        "e5 - - . g5 - - . f5 - e5 - d5 - - . "
        "c5 - b4 - a4 - - - e4 - - - . . . . "
    ),
    bass=(
        "a2 - - - - - - - e2 - - - - - - - "
        "f2 - - - - - - - e2 - - - - - - - "
        "a2 - - - - - - - d2 - - - - - - - "
        "f2 - - - e2 - - - a1 - - - - - - - "
    ),
    drum=(". . c2 . . . g3 . " * 8),
    ticks_per_step=4,
)

#: Option five. Clockwork: staccato octaves, everything short, nothing
#: held -- the most video-game of the five.
CLOCKWORK = Tune(
    "clockwork",
    lead=(
        "c5 c6 . c5 g5 . c5 c6 . g5 e5 . g5 c6 . . "
        "d5 d6 . d5 a5 . d5 d6 . a5 f5 . a5 d6 . . "
        "e5 e6 . e5 b5 . e5 e6 . b5 g5 . b5 e6 . . "
        "f5 d6 . e5 c6 . d5 b5 . g5 . . c6 . . . "
    ),
    bass=(
        "c2 . c3 . c2 . c3 . c2 . c3 . c2 . c3 . "
        "d2 . d3 . d2 . d3 . d2 . d3 . d2 . d3 . "
        "e2 . e3 . e2 . e3 . e2 . e3 . e2 . e3 . "
        "f2 . f3 . g2 . g3 . c2 . c3 . c2 . . . "
    ),
    drum=("c2 g3 . c2 g3 . c2 g3 " * 8),
    ticks_per_step=3,
)

#: The gameplay tunes to choose from, numbered 1-5 in the settings.
GAME_TUNES = (FIELD, DEEPER, SKYWAYS, CAVERNS, CLOCKWORK)


# ----------------------------------------------------------------------
# Sound effects, for the sound-on-events setting. Each is a few ticks
# long, plays once, and restarts cleanly if the same thing happens twice.
# ----------------------------------------------------------------------

#: A coin. Two bright notes, up and gone.
COIN_BLIP = Tune("coin", lead="c6 e6", ticks_per_step=1, loop=False)

#: Leaving the ground. A quick fifth.
JUMP_BLIP = Tune("jump", lead="c5 g5", ticks_per_step=1, loop=False)

#: A boss fist coming down. Noise, low, brief.
FIST_THUD = Tune("fist", lead="", drum="c2 g2", ticks_per_step=2, loop=False)


#: What plays behind each level, by index. The finale gets its own.
def level_tune(index: int, total: int, has_boss: bool, choice: int = 1) -> Tune:
    """Which tune a level plays. ``choice`` numbers GAME_TUNES from 1."""
    if index == total - 1:
        return FINALE
    if has_boss:
        return DEMON
    return GAME_TUNES[max(1, min(len(GAME_TUNES), choice)) - 1]


ALL_TUNES = (
    TITLE, FIELD, DEEPER, SKYWAYS, CAVERNS, CLOCKWORK,
    DEMON, FINALE, DEATH, FANFARE,
    COIN_BLIP, JUMP_BLIP, FIST_THUD,
)
