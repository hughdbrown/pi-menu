"""Holding an arrow key down, as X11 actually reports it.

Auto-repeat does not send one press and one release. It sends a release
immediately followed by another press, over and over, for as long as the
key is down. Read literally that says the player is letting go several
times a second, which in a platform game means the player stops dead
mid-run and cannot hold a jump. So a release is deferred by one tick and
cancelled if the matching press arrives first.
"""

from __future__ import annotations

from pi_menu.platformer.keys import KEYSYMS, HeldKeys
from pi_menu.platformer.session import BACK, LEFT, RIGHT, SELECT, UP


def test_a_press_is_reported_once():
    keys = HeldKeys()

    assert keys.press(RIGHT) is True
    assert keys.held == frozenset({RIGHT})


def test_pressing_a_key_already_held_is_not_a_new_press():
    keys = HeldKeys()
    keys.press(RIGHT)

    assert keys.press(RIGHT) is False


def test_a_release_takes_effect_on_the_next_settle():
    keys = HeldKeys()
    keys.press(RIGHT)
    keys.release(RIGHT)

    assert keys.held == frozenset({RIGHT}), "released too early"
    assert keys.settle() == [RIGHT]
    assert keys.held == frozenset()


def test_a_repeat_press_cancels_the_pending_release():
    keys = HeldKeys()
    keys.press(RIGHT)

    keys.release(RIGHT)  # auto-repeat's release...
    assert keys.press(RIGHT) is False  # ...and its immediate press
    assert keys.settle() == []
    assert keys.held == frozenset({RIGHT})


def test_a_long_hold_never_reports_a_release():
    keys = HeldKeys()
    keys.press(RIGHT)

    for _ in range(20):  # twenty auto-repeat cycles
        keys.release(RIGHT)
        keys.press(RIGHT)
        assert keys.settle() == []

    assert keys.held == frozenset({RIGHT})


def test_letting_go_for_real_reports_a_release():
    keys = HeldKeys()
    keys.press(RIGHT)
    keys.release(RIGHT)
    keys.settle()

    assert keys.held == frozenset()
    assert keys.settle() == []


def test_releasing_a_key_that_was_never_held_does_nothing():
    keys = HeldKeys()
    keys.release(LEFT)

    assert keys.settle() == []


def test_several_keys_are_held_at_once():
    keys = HeldKeys()
    keys.press(RIGHT)
    keys.press(UP)

    assert keys.held == frozenset({RIGHT, UP})


def test_clearing_forgets_everything():
    keys = HeldKeys()
    keys.press(RIGHT)
    keys.release(RIGHT)

    keys.clear()

    assert keys.held == frozenset()
    assert keys.settle() == []


def test_the_arrow_keys_and_the_enter_keys_are_mapped():
    assert KEYSYMS["Left"] == LEFT
    assert KEYSYMS["Return"] == SELECT
    assert KEYSYMS["KP_Enter"] == SELECT
    assert KEYSYMS["Escape"] == BACK


def test_an_unmapped_key_is_simply_absent():
    assert "F13" not in KEYSYMS
