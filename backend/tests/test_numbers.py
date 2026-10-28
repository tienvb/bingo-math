from __future__ import annotations

import random

import pytest

from app.game.numbers import (
    MUL_PRODUCTS,
    available_numbers,
    draw_number,
    draw_pool,
    enabled_ops,
    is_valid_ops,
)
from tests.conftest import ALL_OP_COMBOS, combo_id


def test_all_ops_cover_1_to_100() -> None:
    assert available_numbers({"add", "sub", "mul", "div"}) == list(range(1, 101))


def test_single_op_sets() -> None:
    assert available_numbers({"add"}) == list(range(2, 101))
    assert available_numbers({"sub"}) == list(range(1, 100))
    assert available_numbers({"div"}) == list(range(1, 11))
    assert len(available_numbers({"mul"})) == 42
    assert set(available_numbers({"mul"})) == MUL_PRODUCTS


def test_validity() -> None:
    assert not is_valid_ops(frozenset())
    assert not is_valid_ops({"div"})  # |R| = 10
    assert is_valid_ops({"mul"})  # |R| = 42
    assert is_valid_ops({"mul", "div"})
    assert is_valid_ops({"add"})


@pytest.mark.parametrize("combo", ALL_OP_COMBOS, ids=combo_id)
def test_r_is_union(combo: frozenset) -> None:
    r = available_numbers(combo)
    assert r == sorted(set(r))
    assert all(1 <= n <= 100 for n in r)


def test_enabled_ops() -> None:
    assert enabled_ops(True, False, True, False) == {"add", "mul"}
    assert enabled_ops(False, False, False, False) == frozenset()


def test_draw_pool_filters() -> None:
    r = list(range(1, 101))
    assert draw_pool(r, drawn=[1, 2], card_numbers=None) == list(range(3, 101))
    assert draw_pool(r, drawn=[5], card_numbers={0, 5, 7, 200}) == [7]


def test_draw_number_avoids_skipped_unless_only_one() -> None:
    rng = random.Random(1)
    for _ in range(200):
        assert draw_number([3, 4], rng, avoid=3) == 4
    assert draw_number([3], rng, avoid=3) == 3
    assert draw_number([], rng) is None
