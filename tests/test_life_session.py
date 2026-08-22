"""Every Game of Life control must reach the panel.

Start, Stop, Reset, Random, Clear and drawing a cell by hand all change
what the LEDs show, so each one is checked twice: against a recording
display for the exact pixels, and against the real Pico firmware over a
pseudo-terminal to prove the frame survives the whole path.
"""

from __future__ import annotations

import os
import random

import pytest

from pi_menu.display.null_ import NullDisplay
from pi_menu.display.protocol import FRAME_BYTES, pixel_offset
from pi_menu.life.session import EMPTY_NOTE, SETTLED_NOTE, LifeSession
from pi_menu.palette import PALETTE


class Recorder:
    """Collects the frames a session pushes."""

    def __init__(self):
        self.frames: list[bytes] = []

    def __call__(self, framebuffer: bytes) -> None:
        self.frames.append(framebuffer)

    @property
    def last(self) -> bytes:
        return self.frames[-1]

    def lit(self, framebuffer: bytes | None = None) -> set[tuple[int, int]]:
        frame = self.last if framebuffer is None else framebuffer
        return {
            (x, y)
            for y in range(16)
            for x in range(16)
            if frame[pixel_offset(x, y) : pixel_offset(x, y) + 3] != b"\x00\x00\x00"
        }


@pytest.fixture
def session():
    recorder = Recorder()
    return LifeSession(recorder, rng=random.Random(7)), recorder


# -- every control pushes ------------------------------------------------


def test_creating_a_session_blanks_the_panel(session):
    _, recorder = session
    assert recorder.frames == [bytes(FRAME_BYTES)]


def test_drawing_a_cell_by_hand_lights_that_pixel(session):
    life, recorder = session
    before = len(recorder.frames)

    assert life.set_cell(3, 9, True) is True

    assert len(recorder.frames) == before + 1
    assert recorder.lit() == {(3, 9)}


def test_erasing_a_cell_by_hand_clears_that_pixel(session):
    life, recorder = session
    life.set_cell(3, 9, True)

    life.set_cell(3, 9, False)

    assert recorder.lit() == set()


def test_setting_a_cell_to_what_it_already_is_pushes_nothing(session):
    life, recorder = session
    life.set_cell(3, 9, True)
    before = len(recorder.frames)

    assert life.set_cell(3, 9, True) is False
    assert len(recorder.frames) == before


def test_random_pushes_a_populated_frame(session):
    life, recorder = session

    life.randomize(0.5)

    assert life.board.population > 0
    assert len(recorder.lit()) == life.board.population


def test_reset_pushes_the_seed_back_to_the_panel(session):
    life, recorder = session
    life.set_cell(1, 1, True)
    life.set_cell(2, 1, True)
    life.set_cell(3, 1, True)
    seeded = recorder.lit()

    life.start()
    life.step()
    assert recorder.lit() != seeded  # a blinker has rotated

    life.reset()

    assert recorder.lit() == seeded
    assert life.board.generation == 0
    assert life.running is False


def test_clear_pushes_a_blank_frame(session):
    life, recorder = session
    life.randomize(0.5)

    life.clear()

    assert recorder.last == bytes(FRAME_BYTES)
    assert life.running is False


def test_start_and_stop_both_push(session):
    life, recorder = session
    life.set_cell(5, 5, True)
    before = len(recorder.frames)

    life.start()
    life.stop()

    assert len(recorder.frames) == before + 2


def test_stepping_pushes_the_new_generation(session):
    life, recorder = session
    for x in range(1, 4):
        life.set_cell(x, 1, True)  # a blinker

    life.step()

    assert recorder.lit() == {(2, 0), (2, 1), (2, 2)}


def test_changing_colour_repaints_the_panel(session):
    life, recorder = session
    life.set_cell(0, 0, True)
    assert recorder.last[:3] == bytes(PALETTE["Green"])

    life.set_colour("Magenta")

    assert recorder.last[:3] == bytes(PALETTE["Magenta"])


# -- seed and note behaviour --------------------------------------------


def test_hand_edits_become_the_seed_that_reset_returns_to(session):
    life, recorder = session
    life.randomize(0.4)
    life.set_cell(0, 0, True)
    drawn = recorder.lit()

    life.start()
    life.step()
    life.reset()

    assert recorder.lit() == drawn


def test_starting_an_empty_board_explains_itself_rather_than_going_quiet(session):
    life, _ = session

    assert life.start() is False
    assert life.running is False
    assert life.note == EMPTY_NOTE
    assert EMPTY_NOTE in life.status_text()


def test_a_settled_board_stops_itself_and_says_so(session):
    life, _ = session
    for x, y in [(1, 1), (2, 1), (1, 2), (2, 2)]:  # a block, which never changes
        life.set_cell(x, y, True)
    life.start()

    assert life.step() is False
    assert life.running is False
    assert SETTLED_NOTE in life.status_text()


def test_the_settle_note_is_not_wiped_by_the_next_status_read(session):
    """The note used to be overwritten before anyone could read it."""
    life, _ = session
    for x, y in [(1, 1), (2, 1), (1, 2), (2, 2)]:  # a block
        life.set_cell(x, y, True)
    life.start()
    life.step()

    assert SETTLED_NOTE in life.status_text()
    assert SETTLED_NOTE in life.status_text()  # still there on a second read


def test_a_dying_cell_counts_as_change_rather_than_settling(session):
    """A lone cell vanishing is a change, so the board is not settled yet."""
    life, _ = session
    life.set_cell(0, 0, True)
    life.start()

    assert life.step() is True
    assert life.note is None
    assert life.step() is False  # now nothing is left to change


def test_random_clears_a_stale_note(session):
    life, _ = session
    life.start()
    assert life.note == EMPTY_NOTE

    life.randomize(0.5)

    assert life.note is None


# -- the same controls, against the real firmware ------------------------

pytestmark_pty = pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="needs pseudo-terminals"
)


@pytestmark_pty
def test_every_control_reaches_the_real_panel(pico):
    """Random, Reset and a hand-drawn cell must all light real LEDs."""
    pytest.importorskip("serial")
    from pi_menu.display.serial_link import SerialDisplay

    firmware, path = pico
    display = SerialDisplay(port=path, brightness=1.0)

    def sink(framebuffer: bytes) -> None:
        display.set_frame(framebuffer)
        display.show()

    def lit_on_panel() -> set[tuple[int, int]]:
        return {
            position
            for position, colour in firmware.graphics.pixels.items()
            if colour != (0, 0, 0)
        }

    try:
        life = LifeSession(sink, rng=random.Random(11))
        assert lit_on_panel() == set()

        # Manual: drawing one cell lights exactly that LED.
        life.set_cell(4, 6, True)
        assert lit_on_panel() == {(4, 6)}
        assert firmware.graphics.pixels[(4, 6)] == PALETTE["Green"]

        # Random: the panel matches the board.
        life.randomize(0.5)
        assert lit_on_panel() == set(life.board.live_cells())
        randomised = lit_on_panel()

        # Start then step: the panel follows the simulation.
        life.start()
        life.step()
        assert lit_on_panel() == set(life.board.live_cells())

        # Reset: the panel goes back to the random seed.
        life.reset()
        assert lit_on_panel() == randomised

        # Clear: the panel goes dark.
        life.clear()
        assert lit_on_panel() == set()
    finally:
        display.close()
