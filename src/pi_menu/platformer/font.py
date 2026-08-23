"""A three-by-five pixel font, which is as large as the panel allows.

Four characters at three pixels each, with a pixel between them, comes
to fifteen -- one short of the sixteen the panel has. That is the whole
budget, and it is why the level picker is labelled LVLS rather than
LEVELS.

Only the characters the menu needs are here. A font is a lot of hand
work per glyph, and glyphs nothing draws are glyphs nobody checks.
"""

from __future__ import annotations

from typing import Iterator

GLYPH_WIDTH = 3
GLYPH_HEIGHT = 5
#: Blank column between characters.
GAP = 1

INK = "#"
SPACE = "."

GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (".#.", "#.#", "###", "#.#", "#.#"),
    "L": ("#..", "#..", "#..", "#..", "###"),
    "P": ("##.", "#.#", "##.", "#..", "#.."),
    "S": (".##", "#..", ".#.", "..#", "##."),
    "V": ("#.#", "#.#", "#.#", "#.#", ".#."),
    "Y": ("#.#", "#.#", ".#.", ".#.", ".#."),
    "0": ("###", "#.#", "#.#", "#.#", "###"),
    "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("###", "..#", "###", "#..", "###"),
    "3": ("###", "..#", ".##", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"),
    "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"),
    "7": ("###", "..#", "..#", "..#", "..#"),
    "8": ("###", "#.#", "###", "#.#", "###"),
    "9": ("###", "#.#", "###", "..#", "###"),
}


def text_width(text: str) -> int:
    """How many pixels ``text`` occupies, gaps included."""
    if not text:
        return 0
    return len(text) * GLYPH_WIDTH + (len(text) - 1) * GAP


def pixels(text: str, x: int, y: int) -> Iterator[tuple[int, int]]:
    """The lit pixels of ``text`` drawn with its top left at ``(x, y)``."""
    for index, character in enumerate(text):
        rows = GLYPHS[character]
        left = x + index * (GLYPH_WIDTH + GAP)
        for row_index, row in enumerate(rows):
            for column, cell in enumerate(row):
                if cell == INK:
                    yield left + column, y + row_index
