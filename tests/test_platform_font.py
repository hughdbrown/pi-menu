"""The tiny font the panel menu is written in.

Three pixels is as narrow as a letter can be and still be read, so the
width is won back by letting narrow letters be narrow rather than by
shrinking every glyph. Four rows rather than five keeps the two menu
words from filling the panel.
"""

from __future__ import annotations

import pytest

from pi_menu.display.protocol import WIDTH
from pi_menu.platformer import font


def test_every_glyph_is_four_rows_of_a_constant_width():
    for character, rows in font.GLYPHS.items():
        assert len(rows) == font.GLYPH_HEIGHT, character
        assert len(set(len(row) for row in rows)) == 1, character


def test_no_glyph_is_narrower_than_two_or_wider_than_three():
    for character in font.GLYPHS:
        assert 2 <= font.width(character) <= 3, character


def test_every_glyph_uses_only_ink_and_space():
    for character, rows in font.GLYPHS.items():
        assert set("".join(rows)) <= {font.INK, font.SPACE}, character


@pytest.mark.parametrize("word", ["PLAY", "LVLS"])
def test_the_menu_words_can_be_written(word):
    assert all(character in font.GLYPHS for character in word)


def test_every_digit_can_be_written():
    assert all(str(digit) in font.GLYPHS for digit in range(10))


def test_the_menu_words_leave_a_margin_on_the_panel():
    """The old five-row font filled all but one column. This does not."""
    assert font.text_width("PLAY") <= WIDTH - 2
    assert font.text_width("LVLS") <= WIDTH - 2


def test_width_counts_the_gaps_between_characters():
    assert font.text_width("0") == 3
    assert font.text_width("00") == 7


def test_a_narrow_glyph_takes_less_room_than_a_wide_one():
    assert font.text_width("L") < font.text_width("P")


def test_an_empty_string_has_no_width():
    assert font.text_width("") == 0


def test_pixels_are_placed_relative_to_the_origin():
    at_origin = set(font.pixels("1", 0, 0))
    moved = set(font.pixels("1", 5, 2))

    assert moved == {(x + 5, y + 2) for x, y in at_origin}


def test_a_glyph_lights_something():
    assert set(font.pixels("8", 0, 0))


def test_the_last_character_ends_where_the_width_says_it_does():
    for text in ("00", "PLAY", "LVLS", "27"):
        columns = {x for x, _ in font.pixels(text, 0, 0)}
        assert max(columns) == font.text_width(text) - 1, text


def test_an_unknown_character_is_refused():
    with pytest.raises(KeyError):
        list(font.pixels("~", 0, 0))
