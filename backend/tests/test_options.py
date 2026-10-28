from __future__ import annotations

import random

import pytest

from app.game.numbers import available_numbers
from app.game.options import OPTION_KEYS, generate_options
from app.game.questions import Expression, generate_expression
from tests.conftest import VALID_OP_COMBOS, combo_id

ROUNDS_NO_REPEAT = 30  # 1..100 has 99 wrong values -> 33 full rounds before reuse


def _check_set(opts, n: int) -> None:
    assert len(opts.values) == 4
    assert len(set(opts.values)) == 4
    assert all(1 <= v <= 100 for v in opts.values)
    assert [v for v in opts.values if v == n] == [n]
    assert opts.values[opts.correct_index] == n
    assert opts.correct_key == OPTION_KEYS[opts.correct_index]
    assert sorted(opts.wrong_values) == sorted(v for v in opts.values if v != n)


@pytest.mark.parametrize("combo", VALID_OP_COMBOS, ids=combo_id)
def test_options_for_every_n(combo: frozenset) -> None:
    rng = random.Random(11)
    for n in available_numbers(combo):
        expr = generate_expression(n, combo, rng)
        used: set[int] = set()
        prev: int | None = None
        for _ in range(4):
            opts = generate_options(expr, rng, used, prev)
            _check_set(opts, n)
            if prev is not None:
                assert opts.correct_index != prev
            assert used.isdisjoint(opts.wrong_values)
            used |= set(opts.wrong_values)
            prev = opts.correct_index


@pytest.mark.parametrize("n", [1, 2, 10, 50, 99, 100])
def test_many_regenerations_never_repeat_wrong_values(n: int) -> None:
    rng = random.Random(n)
    ops = {"add", "sub", "mul", "div"}
    expr = generate_expression(n, ops, rng)
    used: set[int] = set()
    prev: int | None = None
    for _ in range(ROUNDS_NO_REPEAT):
        opts = generate_options(expr, rng, used, prev)
        _check_set(opts, n)
        assert opts.correct_index != prev
        assert used.isdisjoint(opts.wrong_values)
        used |= set(opts.wrong_values)
        prev = opts.correct_index


def test_exhausted_pool_still_returns_valid_set() -> None:
    rng = random.Random(0)
    expr = Expression(op="add", a=3, b=4, result=7)
    used = set(range(1, 101)) - {7}
    opts = generate_options(expr, rng, used, previous_correct_index=0)
    _check_set(opts, 7)
    assert opts.correct_index != 0


def test_prefers_plausible_candidates() -> None:
    rng = random.Random(2)
    expr = Expression(op="mul", a=7, b=8, result=56)
    plausible = {55, 57, 54, 58, 66, 46, 65, 63, 49, 64, 48}
    for _ in range(50):
        opts = generate_options(expr, rng)
        assert set(opts.wrong_values) <= plausible
