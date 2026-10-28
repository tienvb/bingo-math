from __future__ import annotations

import random

import pytest

from app.game.cards import card_numbers, column_groups, find_cell, generate_card
from app.game.numbers import available_numbers
from tests.conftest import VALID_OP_COMBOS, combo_id

CARDS_PER_COMBO = 1000


def test_full_ops_groups_are_blocks_of_20() -> None:
    groups = column_groups(available_numbers({"add", "sub", "mul", "div"}))
    assert groups == [list(range(1 + 20 * c, 21 + 20 * c)) for c in range(5)]


def test_groups_sizes_differ_by_at_most_one() -> None:
    groups = column_groups(available_numbers({"mul"}))
    sizes = [len(g) for g in groups]
    assert sum(sizes) == 42 and max(sizes) - min(sizes) <= 1


@pytest.mark.parametrize("combo", VALID_OP_COMBOS, ids=combo_id)
def test_1000_cards_valid(combo: frozenset) -> None:
    rng = random.Random(combo_id(combo))
    r = available_numbers(combo)
    groups = column_groups(r)
    for _ in range(CARDS_PER_COMBO):
        card = generate_card(r, rng)
        assert len(card) == 5 and all(len(row) == 5 for row in card)
        assert card[2][2] == 0
        nums = [v for row in card for v in row if v != 0]
        assert len(nums) == 24 and len(set(nums)) == 24
        for c in range(5):
            col = [card[row][c] for row in range(5) if not (row == 2 and c == 2)]
            assert all(v in groups[c] for v in col), (c, col)
            assert col == sorted(col)
        assert all(n in r for n in nums)


def test_card_helpers(rng: random.Random) -> None:
    card = generate_card(list(range(1, 101)), rng)
    nums = card_numbers(card)
    assert len(nums) == 24 and 0 not in nums
    assert find_cell(card, card[4][3]) == (4, 3)
    assert find_cell(card, 0) is None


def test_too_small_r_rejected(rng: random.Random) -> None:
    with pytest.raises(ValueError):
        generate_card(list(range(1, 11)), rng)
