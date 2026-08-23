"""The chiptune: tuning, tune shape, and what actually gets sent.

The Pico has a synth but no idea what a tune is, so every note and every
rest is decided here. These check the decisions, not the sound -- a note
that never gets released is silent on a recording and deafening on a
desk.
"""

from __future__ import annotations

import pytest

from pi_menu.display.protocol import WAVEFORMS
from pi_menu.music import (
    ALL_TUNES,
    BASS,
    DEATH,
    DEMON,
    DRUM,
    FANFARE,
    FIELD,
    FINALE,
    LEAD,
    TITLE,
    VOICES,
    Player,
    Tune,
    frequency,
    level_tune,
)


class Recorder:
    """Collects the notes a player sends."""

    def __init__(self):
        self.notes = []

    def __call__(self, channel, waveform, hertz, volume):
        self.notes.append((channel, waveform, hertz, volume))

    def sounded(self):
        return [note for note in self.notes if note[3] > 0]

    def released(self):
        return [note for note in self.notes if note[3] == 0]


# -- tuning --------------------------------------------------------------


def test_the_tuning_is_concert_pitch():
    assert frequency("a4") == 440


def test_an_octave_up_is_twice_the_frequency():
    assert frequency("a5") == 2 * frequency("a4")
    assert frequency("c5") == pytest.approx(2 * frequency("c4"), rel=0.01)


def test_the_semitones_run_in_order():
    rising = [frequency(f"{name}4") for name in ("c", "d", "e", "f", "g", "a", "b")]

    assert rising == sorted(rising)


def test_a_sharp_sits_between_its_neighbours():
    assert frequency("f4") < frequency("f#4") < frequency("g4")


def test_an_unknown_note_is_refused():
    with pytest.raises(ValueError):
        frequency("h4")


# -- the tunes -----------------------------------------------------------


@pytest.mark.parametrize("tune", ALL_TUNES, ids=[t.name for t in ALL_TUNES])
def test_every_note_in_every_tune_can_be_played(tune):
    for track in tune.tracks.values():
        for token in track:
            if token not in ("-", "."):
                assert frequency(token) > 0


@pytest.mark.parametrize("tune", ALL_TUNES, ids=[t.name for t in ALL_TUNES])
def test_every_tune_has_something_in_it(tune):
    assert tune.steps > 0
    assert any(tune.tracks.values())


@pytest.mark.parametrize("tune", ALL_TUNES, ids=[t.name for t in ALL_TUNES])
def test_no_tune_is_so_short_it_grates(tune):
    """A loop under a couple of seconds is a ringtone, not a soundtrack."""
    if tune.loop:
        assert tune.steps * tune.ticks_per_step >= 40


def test_the_stings_do_not_loop():
    assert DEATH.loop is False
    assert FANFARE.loop is False


def test_every_voice_uses_a_waveform_the_panel_knows():
    assert all(voice.waveform in WAVEFORMS for voice in VOICES.values())


def test_the_tunes_are_all_different():
    assert len({tune.name for tune in ALL_TUNES}) == len(ALL_TUNES)


# -- which tune plays where ----------------------------------------------


def test_the_last_level_gets_the_finale():
    assert level_tune(59, 60, has_boss=True) is FINALE


def test_a_boss_level_gets_the_demon_theme():
    assert level_tune(14, 60, has_boss=True) is DEMON


def test_the_first_half_and_the_second_half_sound_different():
    assert level_tune(0, 60, has_boss=False) is not level_tune(40, 60, has_boss=False)


# -- the player ----------------------------------------------------------


@pytest.fixture
def player():
    recorder = Recorder()
    return Player(recorder), recorder


def test_starting_a_tune_sounds_its_first_notes(player):
    music, recorder = player

    music.play(TITLE)

    assert recorder.sounded()


def test_nothing_sounds_until_a_tune_is_playing(player):
    music, recorder = player

    music.tick()

    assert recorder.notes == []


def test_a_step_lasts_the_tunes_tempo(player):
    music, recorder = player
    music.play(FIELD)
    before = len(recorder.notes)

    for _ in range(FIELD.ticks_per_step - 1):
        music.tick()
    assert len(recorder.notes) == before, "the step ended early"

    music.tick()
    assert len(recorder.notes) > before


def test_a_looping_tune_starts_again_at_the_end(player):
    music, _ = player
    music.play(FIELD)

    for _ in range(FIELD.steps * FIELD.ticks_per_step + 2):
        music.tick()

    assert music.finished is False
    assert music.step < FIELD.steps


def test_a_sting_stops_when_it_runs_out(player):
    music, recorder = player
    music.play(DEATH)

    for _ in range(DEATH.steps * DEATH.ticks_per_step + 4):
        music.tick()

    assert music.finished is True
    assert recorder.released(), "the last note was left sounding"


def test_changing_tune_releases_what_was_sounding(player):
    music, recorder = player
    music.play(TITLE)
    recorder.notes.clear()

    music.play(DEMON)

    assert recorder.released(), "the old tune was left hanging"


def test_playing_the_same_tune_again_does_not_restart_it(player):
    music, recorder = player
    music.play(FIELD)
    for _ in range(20):
        music.tick()
    step = music.step
    recorder.notes.clear()

    music.play(FIELD)

    assert music.step == step
    assert recorder.notes == []


def test_silencing_releases_every_channel(player):
    music, recorder = player
    music.play(FINALE)
    recorder.notes.clear()

    music.silence()

    channels = {note[0] for note in recorder.released()}
    assert channels
    assert all(note[3] == 0 for note in recorder.notes)


def test_a_hold_does_not_retrigger_the_note(player):
    music, recorder = player
    held = Tune("held", lead="c4 - - -", ticks_per_step=1)
    music.play(held)
    recorder.notes.clear()

    music.tick()
    music.tick()

    assert recorder.notes == [], "a held note was struck again"


def test_a_rest_releases_the_note(player):
    music, recorder = player
    resting = Tune("resting", lead="c4 .", ticks_per_step=1)
    music.play(resting)
    recorder.notes.clear()

    music.tick()

    assert recorder.released()


def test_each_channel_keeps_its_own_voice(player):
    music, recorder = player
    music.play(FINALE)

    for _ in range(60):
        music.tick()

    for channel, waveform, _hertz, _volume in recorder.notes:
        assert waveform == VOICES[channel].waveform


def test_a_player_with_no_panel_to_talk_to_still_runs():
    """No sink is the ordinary case on a machine with no speaker."""
    music = Player()
    music.play(TITLE)
    for _ in range(50):
        music.tick()

    assert music.tune is TITLE
