"""Spec *Thuật toán chi tiết* mục 2: sinh vé 5x5."""

from __future__ import annotations

import random
from collections.abc import Sequence

SIZE = 5
FREE_ROW = 2
FREE_COL = 2
FREE_VALUE = 0

Card = list[list[int]]


def column_groups(r_numbers: Sequence[int]) -> list[list[int]]:
    """Split sorted R into 5 consecutive groups whose sizes differ by at most 1.

    Larger groups come first (e.g. 42 numbers -> 9, 9, 8, 8, 8).
    """
    values = sorted(set(r_numbers))
    if len(values) < SIZE * SIZE:
        raise ValueError(f"R must have at least 25 numbers, got {len(values)}")
    base, extra = divmod(len(values), SIZE)
    groups: list[list[int]] = []
    start = 0
    for c in range(SIZE):
        size = base + (1 if c < extra else 0)
        groups.append(values[start : start + size])
        start += size
    return groups


def generate_card(r_numbers: Sequence[int], rng: random.Random) -> Card:
    """Return card[row][col]; column c draws from group c, sorted top to bottom;
    card[2][2] = 0 (FREE)."""
    groups = column_groups(r_numbers)
    card: Card = [[FREE_VALUE] * SIZE for _ in range(SIZE)]
    for c, group in enumerate(groups):
        count = SIZE - 1 if c == FREE_COL else SIZE
        picks = sorted(rng.sample(group, count))
        if c == FREE_COL:
            picks.insert(FREE_ROW, FREE_VALUE)
        for r in range(SIZE):
            card[r][c] = picks[r]
    return card


def card_numbers(card: Card) -> set[int]:
    """All numbers on a card except FREE."""
    return {v for row in card for v in row if v != FREE_VALUE}


def find_cell(card: Card, n: int) -> tuple[int, int] | None:
    """[row, col] of number `n` on the card, or None."""
    if n == FREE_VALUE:
        return None
    for r, row in enumerate(card):
        for c, v in enumerate(row):
            if v == n:
                return (r, c)
    return None
