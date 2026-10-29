from __future__ import annotations

import random
import time

import pytest

from app.game.cards import card_numbers, column_groups, column_values, find_cell, generate_card
from app.game.numbers import NumberSet, number_set
from tests.conftest import MAX_NUMBERS, VALID_OP_COMBOS, case_id, combo_id, valid_cases

CARDS_PER_COMBO = 1000
CARDS_PER_CASE = 200
ALL = {"add", "sub", "mul", "div"}


def _check_card(card: list[list[int]], r: NumberSet, m: int) -> None:
    groups = column_groups(r)
    assert len(card) == 5 and all(len(row) == 5 for row in card)
    assert card[2][2] == 0
    nums = [v for row in card for v in row if v != 0]
    assert len(nums) == 24 and len(set(nums)) == 24
    for c in range(5):
        col = [card[row][c] for row in range(5) if not (row == 2 and c == 2)]
        lo, hi = r.kth(groups[c][0]), r.kth(groups[c][1] - 1)
        assert all(lo <= v <= hi and v in r for v in col), (c, col)
        assert col == sorted(col)
    assert all(1 <= n <= m for n in nums)


def test_full_ops_groups_are_blocks_of_20() -> None:
    r = number_set(ALL, 100)
    groups = [[r.kth(k) for k in range(*g)] for g in column_groups(r)]
    assert groups == [list(range(1 + 20 * c, 21 + 20 * c)) for c in range(5)]


def test_groups_sizes_differ_by_at_most_one() -> None:
    sizes = [b - a for a, b in column_groups(number_set({"mul"}, 100))]
    assert sizes == [9, 9, 8, 8, 8]


def test_groups_large_m() -> None:
    r = number_set(ALL, 10**9)
    groups = column_groups(r)
    assert [b - a for a, b in groups] == [2 * 10**8] * 5
    assert column_values(r, groups[1]).intervals == ((2 * 10**8 + 1, 4 * 10**8),)
    r = number_set({"add"}, 1003)  # 2..1003 = 1002 numbers -> 201, 201, 200, 200, 200
    assert [b - a for a, b in column_groups(r)] == [201, 201, 200, 200, 200]
    assert r.kth(column_groups(r)[2][0]) == 404


@pytest.mark.parametrize("combo", VALID_OP_COMBOS, ids=combo_id)
def test_1000_cards_valid(combo: frozenset) -> None:
    rng = random.Random(combo_id(combo))
    r = number_set(combo, 100)
    for _ in range(CARDS_PER_COMBO):
        _check_card(generate_card(r, rng), r, 100)


@pytest.mark.parametrize("case", valid_cases(MAX_NUMBERS), ids=case_id)
def test_cards_valid_for_every_m(case: tuple[frozenset, int]) -> None:
    combo, m = case
    rng = random.Random(case_id(case))
    r = number_set(combo, m)
    for _ in range(CARDS_PER_CASE):
        _check_card(generate_card(r, rng), r, m)


def test_huge_m_cards_are_fast() -> None:
    rng = random.Random(1)
    t0 = time.perf_counter()
    r = number_set(ALL, 10**9)
    for _ in range(300):
        _check_card(generate_card(r, rng), r, 10**9)
    assert time.perf_counter() - t0 < 2.0


def test_max_allowed_m_cards() -> None:
    m = 2**53 - 1  # MAX_NUMBER_LIMIT
    r = number_set(ALL, m)
    assert r.size == m
    _check_card(generate_card(r, random.Random(3)), r, m)


def test_astronomical_m_cards() -> None:
    # Above the config cap, but the pure module must not rely on len() (overflows > 2**63).
    m = 10**30
    r = number_set(ALL, m)
    assert r.size == m
    _check_card(generate_card(r, random.Random(2)), r, m)


def test_card_helpers(rng: random.Random) -> None:
    card = generate_card(number_set(ALL, 100), rng)
    nums = card_numbers(card)
    assert len(nums) == 24 and 0 not in nums
    assert find_cell(card, card[4][3]) == (4, 3)
    assert find_cell(card, 0) is None


def test_too_small_r_rejected(rng: random.Random) -> None:
    with pytest.raises(ValueError):
        generate_card(NumberSet([(1, 10)]), rng)
