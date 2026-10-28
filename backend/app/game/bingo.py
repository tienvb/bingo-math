"""Spec *Thuật toán chi tiết* mục 8: bitmask và 12 đường thắng.

Cell index = row * 5 + col.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.game.cards import FREE_COL, FREE_ROW, FREE_VALUE, SIZE, Card

LineType = Literal["row", "col", "diag"]


@dataclass(frozen=True)
class WinLine:
    type: LineType
    index: int  # diag 0: top-left -> bottom-right, 1: top-right -> bottom-left
    mask: int


def cell_bit(row: int, col: int) -> int:
    return 1 << (row * SIZE + col)


def _build_lines() -> tuple[WinLine, ...]:
    lines: list[WinLine] = []
    for r in range(SIZE):
        lines.append(WinLine("row", r, sum(cell_bit(r, c) for c in range(SIZE))))
    for c in range(SIZE):
        lines.append(WinLine("col", c, sum(cell_bit(r, c) for r in range(SIZE))))
    lines.append(WinLine("diag", 0, sum(cell_bit(i, i) for i in range(SIZE))))
    lines.append(WinLine("diag", 1, sum(cell_bit(i, SIZE - 1 - i) for i in range(SIZE))))
    return tuple(lines)


WIN_LINES: tuple[WinLine, ...] = _build_lines()
FREE_BIT = cell_bit(FREE_ROW, FREE_COL)


def marked_mask(card: Card, drawn: Iterable[int]) -> int:
    """Bitmask of marked cells: FREE or a drawn number."""
    drawn_set = set(drawn)
    mask = 0
    for r in range(SIZE):
        for c in range(SIZE):
            v = card[r][c]
            if v == FREE_VALUE or v in drawn_set:
                mask |= cell_bit(r, c)
    return mask


def marked_cells(card: Card, drawn: Iterable[int]) -> list[tuple[int, int]]:
    """[row, col] of cells marked by drawn numbers (FREE excluded), row-major order."""
    drawn_set = set(drawn)
    return [
        (r, c)
        for r in range(SIZE)
        for c in range(SIZE)
        if card[r][c] != FREE_VALUE and card[r][c] in drawn_set
    ]


def winning_lines(mask: int) -> list[WinLine]:
    return [line for line in WIN_LINES if (mask & line.mask) == line.mask]


def is_bingo(mask: int) -> bool:
    return any((mask & line.mask) == line.mask for line in WIN_LINES)


def card_winning_lines(card: Card, drawn: Iterable[int]) -> list[WinLine]:
    return winning_lines(marked_mask(card, drawn))
