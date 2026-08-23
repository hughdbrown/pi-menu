"""The tiny font the panel menu is written in.

Sixteen pixels across is enough for four characters three pixels wide
with a pixel between them, and not one more. That is why the level
picker is labelled LVLS.
"""

from __future__ import annotations

import pytest

from pi_menu.display.protocol import WIDTH
from pi_menu.platformer import font


def test_every_glyph_is_five_rows_of_three():
    for character, rows in font.GLYPHS.items():
        assert len(rows) == font.GLYPH_HEIGHT, character
        assert all(len(row) == font.GLYPH_WIDTH for row in rows), character


def test_every_glyph_uses_only_ink_and_space():
    for character, rows in font.GLYPHS.items():
        assert set("".join(rows)) <= {font.INK, font.SPACE}, character


@pytest.mark.parametrize("word", ["PLAY", "LVLS"])
def test_the_menu_words_can_be_written(word):
    assert all(character in font.GLYPHS for character in word)


def test_every_digit_can_be_written():
    assert all(str(digit) in font.GLYPHS for digit in range(10))


def test_four_characters_are_exactly_one_short_of_the_panel():
    assert font.text_width("PLAY") == WIDTH - 1


def test_width_counts_the_gaps_between_characters():
    assert font.text_width("1") == 3
    assert font.text_width("12") == 7


def test_an_empty_string_has_no_width():
    assert font.text_width("") == 0


def test_pixels_are_placed_relative_to_the_origin():
    at_origin = set(font.pixels("1", 0, 0))
    moved = set(font.pixels("1", 5, 2))

    assert moved == {(x + 5, y + 2) for x, y in at_origin}


def test_a_glyph_lights_something():
    assert set(font.pixels("8", 0, 0))


def test_the_second_character_starts_after_the_gap():
    columns = {x for x, _ in font.pixels("11", 0, 0)}

    assert max(columns) == font.text_width("11") - 1


def test_an_unknown_character_is_refused():
    with pytest.raises(KeyError):
        list(font.pixels("~", 0, 0))
