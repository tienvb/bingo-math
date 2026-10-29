from __future__ import annotations

import random

from app.game.bingo import (
    FREE_BIT,
    WIN_LINES,
    card_winning_lines,
    cell_bit,
    is_bingo,
    marked_cells,
    marked_mask,
    winning_lines,
)
from app.game.cards import generate_card
from app.game.numbers import ALL_OPS, number_set


def _cells(line) -> list[tuple[int, int]]:
    return [(i // 5, i % 5) for i in range(25) if line.mask >> i & 1]


def test_twelve_distinct_lines() -> None:
    assert len(WIN_LINES) == 12
    assert len({line.mask for line in WIN_LINES}) == 12
    assert [(l.type, l.index) for l in WIN_LINES] == (
        [("row", i) for i in range(5)] + [("col", i) for i in range(5)] + [("diag", 0), ("diag", 1)]
    )
    for line in WIN_LINES:
        assert bin(line.mask).count("1") == 5


def test_line_geometry() -> None:
    by_key = {(l.type, l.index): l for l in WIN_LINES}
    assert _cells(by_key[("row", 1)]) == [(1, c) for c in range(5)]
    assert _cells(by_key[("col", 3)]) == [(r, 3) for r in range(5)]
    assert _cells(by_key[("diag", 0)]) == [(i, i) for i in range(5)]
    assert sorted(_cells(by_key[("diag", 1)])) == sorted((i, 4 - i) for i in range(5))


def test_each_line_wins_alone() -> None:
    for line in WIN_LINES:
        assert winning_lines(line.mask) == [line]
        assert is_bingo(line.mask)


def test_near_wins_do_not_count() -> None:
    for line in WIN_LINES:
        for i in range(25):
            if line.mask >> i & 1:
                assert not is_bingo(line.mask & ~(1 << i))


def test_scattered_marks_no_bingo() -> None:
    # one cell missing from every line: the 4 corners + center + a few, but no full line
    mask = FREE_BIT
    for r, c in [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (2, 0), (3, 0), (1, 1), (3, 3)]:
        mask |= cell_bit(r, c)
    assert not is_bingo(mask)
    assert winning_lines(0) == []


def test_free_cell_counts_on_card() -> None:
    rng = random.Random(4)
    card = generate_card(number_set(ALL_OPS, 100), rng)
    row2 = [card[2][c] for c in range(5) if c != 2]
    assert not card_winning_lines(card, row2[:-1])
    lines = card_winning_lines(card, row2)
    assert [(l.type, l.index) for l in lines] == [("row", 2)]
    assert marked_mask(card, []) == FREE_BIT


def test_multiple_lines_at_once() -> None:
    rng = random.Random(8)
    card = generate_card(number_set(ALL_OPS, 100), rng)
    drawn = [card[0][c] for c in range(5)] + [card[r][0] for r in range(1, 5)]
    lines = card_winning_lines(card, drawn)
    assert {(l.type, l.index) for l in lines} == {("row", 0), ("col", 0)}


def test_marked_cells_excludes_free() -> None:
    rng = random.Random(6)
    card = generate_card(number_set(ALL_OPS, 100), rng)
    drawn = [card[4][4], card[0][2], 999]
    assert marked_cells(card, drawn) == [(0, 2), (4, 4)]
