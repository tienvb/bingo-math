"""Spec *Thuật toán chi tiết* mục 2: sinh vé 5x5."""

from __future__ import annotations

import random

from app.game.numbers import NumberSet, sample_distinct

SIZE = 5
FREE_ROW = 2
FREE_COL = 2
FREE_VALUE = 0

Card = list[list[int]]


def column_groups(r: NumberSet) -> list[tuple[int, int]]:
    """Split sorted R into 5 consecutive groups whose sizes differ by at most 1.

    Larger groups come first (e.g. 42 numbers -> 9, 9, 8, 8, 8). Groups are returned
    as half-open (start, stop) ranges of *ranks* in R (use `r.kth`), so nothing is
    materialised for large M.
    """
    total = r.size
    if total < SIZE * SIZE:
        raise ValueError(f"R must have at least 25 numbers, got {total}")
    base, extra = divmod(total, SIZE)
    groups: list[tuple[int, int]] = []
    start = 0
    for c in range(SIZE):
        size = base + (1 if c < extra else 0)
        groups.append((start, start + size))
        start += size
    return groups


def column_values(r: NumberSet, group: tuple[int, int]) -> NumberSet:
    """The numbers of one column group, as a NumberSet (cheap: one slice per interval)."""
    start, stop = group
    if stop <= start:
        return NumberSet(())
    lo, hi = r.kth(start), r.kth(stop - 1)
    return NumberSet((max(a, lo), min(b, hi)) for a, b in r.intervals)


def generate_card(r: NumberSet, rng: random.Random) -> Card:
    """Return card[row][col]; column c draws from group c, sorted top to bottom;
    card[2][2] = 0 (FREE)."""
    groups = column_groups(r)
    card: Card = [[FREE_VALUE] * SIZE for _ in range(SIZE)]
    for c, group in enumerate(groups):
        count = SIZE - 1 if c == FREE_COL else SIZE
        picks = sorted(r.kth(k) for k in sample_distinct(group[0], group[1], count, rng))
        if c == FREE_COL:
            picks.insert(FREE_ROW, FREE_VALUE)
        for row in range(SIZE):
            card[row][c] = picks[row]
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
