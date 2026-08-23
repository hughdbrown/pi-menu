"""A small pixel font, four rows tall, with variable-width glyphs.

Three pixels is the narrowest a letter can be and still be read: at two,
``A`` has nowhere to put its crossbar and ``V`` and ``Y`` collapse into
the same shape. So the width comes down by letting narrow letters be
narrow -- ``L`` needs two columns, ``1`` needs two -- rather than by
shrinking every glyph to a size none of them survive.

Four rows rather than five keeps the menu from filling the panel. The
words are what the screen is for, not all it should hold.

Only the characters the menu needs are here. A glyph is a lot of hand
work, and glyphs nothing draws are glyphs nobody checks.
"""

from __future__ import annotations

from typing import Iterator

GLYPH_HEIGHT = 4
#: Blank column between characters.
GAP = 1

INK = "#"
SPACE = "."

GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (".#.", "#.#", "###", "#.#"),
    "L": ("#.", "#.", "#.", "##"),
    "P": ("##.", "#.#", "##.", "#.."),
    "S": (".##", "##.", "..#", "##."),
    "V": ("#.#", "#.#", "#.#", ".#."),
    "Y": ("#.#", "#.#", ".#.", ".#."),
    "0": ("###", "#.#", "#.#", "###"),
    "1": ("##", ".#", ".#", ".#"),
    "2": ("###", "..#", ".#.", "###"),
    "3": ("###", ".##", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#"),
    "5": ("###", "#..", "..#", "###"),
    "6": ("###", "#..", "###", "###"),
    "7": ("###", "..#", ".#.", ".#."),
    "8": ("###", "#.#", "###", "###"),
    "9": ("###", "#.#", "###", "..#"),
}


def width(character: str) -> int:
    """How many columns one glyph occupies."""
    return len(GLYPHS[character][0])


def text_width(text: str) -> int:
    """How many pixels ``text`` occupies, gaps included."""
    if not text:
        return 0
    return sum(width(character) for character in text) + GAP * (len(text) - 1)


def pixels(text: str, x: int, y: int) -> Iterator[tuple[int, int]]:
    """The lit pixels of ``text`` drawn with its top left at ``(x, y)``."""
    left = x
    for character in text:
        rows = GLYPHS[character]
        for row_index, row in enumerate(rows):
            for column, cell in enumerate(row):
                if cell == INK:
                    yield left + column, y + row_index
        left += len(rows[0]) + GAP
