import random

import pytest

from pi_menu.life.board import Board


def make(pattern: list[str], wrap: bool = True) -> Board:
    """Build a board from rows of '.' and '#'."""
    board = Board(len(pattern[0]), len(pattern), wrap=wrap)
    for y, row in enumerate(pattern):
        for x, char in enumerate(row):
            board.set(x, y, char == "#")
    return board


def render(board: Board) -> list[str]:
    return [
        "".join("#" if board.get(x, y) else "." for x in range(board.width))
        for y in range(board.height)
    ]


def test_a_blinker_oscillates_with_period_two():
    board = make([".....", "..#..", "..#..", "..#..", "....."])
    horizontal = [".....", ".....", ".###.", ".....", "....."]

    board.step()
    assert render(board) == horizontal

    board.step()
    assert render(board) == [".....", "..#..", "..#..", "..#..", "....."]


def test_a_block_is_a_still_life_and_step_reports_no_change():
    board = make(["....", ".##.", ".##.", "...."])

    assert board.step() is False
    assert render(board) == ["....", ".##.", ".##.", "...."]


def test_an_empty_board_stays_empty():
    board = Board(8, 8)
    assert board.step() is False
    assert board.population == 0


def test_a_lone_cell_dies_of_underpopulation():
    board = make(["...", ".#.", "..."])
    board.step()
    assert board.population == 0


def test_a_glider_travels_one_cell_diagonally_every_four_generations():
    board = make(
        [
            ".#........",
            "..#.......",
            "###.......",
            "..........",
            "..........",
            "..........",
            "..........",
            "..........",
            "..........",
            "..........",
        ]
    )
    for _ in range(4):
        board.step()

    assert render(board) == [
        "..........",
        "..#.......",
        "...#......",
        ".###......",
        "..........",
        "..........",
        "..........",
        "..........",
        "..........",
        "..........",
    ]


def test_wrapping_joins_opposite_edges():
    # Three cells in the top row plus one wrapped neighbour below.
    board = make(["###", "...", "..."], wrap=True)
    assert board.neighbours(1, 0) == 2
    # The bottom row sees the top row through the wrap.
    assert board.neighbours(1, 2) == 3


def test_without_wrapping_edges_are_dead_space():
    board = make(["###", "...", "..."], wrap=False)
    assert board.neighbours(1, 2) == 0
    assert board.get(-1, 0) is False


def test_generation_counts_steps_and_resets_with_the_board():
    board = Board(4, 4)
    board.step()
    board.step()
    assert board.generation == 2

    board.clear()
    assert board.generation == 0


def test_randomize_is_reproducible_from_a_seeded_generator():
    first, second = Board(16, 16), Board(16, 16)
    first.randomize(0.5, rng=random.Random(1234))
    second.randomize(0.5, rng=random.Random(1234))
    assert first == second


@pytest.mark.parametrize("density,expected", [(0.0, 0), (1.0, 256)])
def test_extreme_densities_produce_empty_or_full_boards(density, expected):
    board = Board(16, 16)
    board.randomize(density)
    assert board.population == expected


def test_snapshot_and_restore_rewind_to_generation_zero():
    board = make([".....", "..#..", "..#..", "..#..", "....."])
    seed = board.snapshot()

    for _ in range(5):
        board.step()
    assert board.generation == 5

    board.restore(seed)
    assert board.generation == 0
    assert render(board) == [".....", "..#..", "..#..", "..#..", "....."]


def test_restore_rejects_a_snapshot_from_a_different_size_board():
    with pytest.raises(ValueError, match="snapshot"):
        Board(16, 16).restore(Board(8, 8).snapshot())


def test_toggle_flips_a_cell_and_reports_the_new_state():
    board = Board(4, 4)
    assert board.toggle(1, 1) is True
    assert board.get(1, 1) is True
    assert board.toggle(1, 1) is False


def test_off_grid_writes_are_ignored_rather_than_raising():
    board = Board(4, 4)
    board.set(9, 9, True)
    board.toggle(-1, 0)
    assert board.population == 0


def test_live_cells_lists_coordinates_in_reading_order():
    board = make(["#.#", "...", ".#."])
    assert list(board.live_cells()) == [(0, 0), (2, 0), (1, 2)]


def test_a_board_must_have_positive_dimensions():
    with pytest.raises(ValueError, match="at least 1x1"):
        Board(0, 5)
