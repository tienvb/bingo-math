from __future__ import annotations

import random
import time

import pytest

from app.game.numbers import available_numbers
from app.game.options import OPTION_KEYS, generate_options
from app.game.questions import Expression, generate_expression
from tests.conftest import SMALL_MAX_NUMBERS, VALID_OP_COMBOS, case_id, combo_id, valid_cases

ROUNDS_NO_REPEAT = 30  # 1..100 has 99 wrong values -> 33 full rounds before reuse
ALL = {"add", "sub", "mul", "div"}


def _check_set(opts, n: int, m: int = 100) -> None:
    assert len(opts.values) == 4
    assert len(set(opts.values)) == 4
    assert all(1 <= v <= m for v in opts.values)
    assert [v for v in opts.values if v == n] == [n]
    assert opts.values[opts.correct_index] == n
    assert opts.correct_key == OPTION_KEYS[opts.correct_index]
    assert sorted(opts.wrong_values) == sorted(v for v in opts.values if v != n)


def _regenerate(expr: Expression, m: int, rng: random.Random, rounds: int) -> None:
    used: set[int] = set()
    prev: int | None = None
    for _ in range(rounds):
        opts = generate_options(expr, m, rng, used, prev)
        _check_set(opts, expr.result, m)
        if prev is not None:
            assert opts.correct_index != prev
        assert used.isdisjoint(opts.wrong_values)
        used |= set(opts.wrong_values)
        prev = opts.correct_index


@pytest.mark.parametrize("combo", VALID_OP_COMBOS, ids=combo_id)
def test_options_for_every_n(combo: frozenset) -> None:
    rng = random.Random(11)
    for n in available_numbers(combo, 100):
        _regenerate(generate_expression(n, combo, 100, rng), 100, rng, 4)


@pytest.mark.parametrize("case", valid_cases(SMALL_MAX_NUMBERS), ids=case_id)
def test_options_for_every_m(case: tuple[frozenset, int]) -> None:
    combo, m = case
    rng = random.Random(case_id(case))
    for n in available_numbers(combo, m):
        _regenerate(generate_expression(n, combo, m, rng), m, rng, 2)


@pytest.mark.parametrize("m", [31, 50])
def test_small_m_many_regenerations(m: int) -> None:
    rng = random.Random(m)
    for n in (1, m // 2, m - 1, m):
        expr = generate_expression(n, ALL, m, rng)
        _regenerate(expr, m, rng, (m - 1) // 3)  # every wrong value used once, no repeat


@pytest.mark.parametrize("n", [1, 2, 10, 50, 99, 100])
def test_many_regenerations_never_repeat_wrong_values(n: int) -> None:
    rng = random.Random(n)
    _regenerate(generate_expression(n, ALL, 100, rng), 100, rng, ROUNDS_NO_REPEAT)


def test_huge_m_options_fast_and_in_range() -> None:
    m = 10**9
    rng = random.Random(5)
    t0 = time.perf_counter()
    for n in (1, 2, 56, 12345, m - 1, m):
        # 40 rounds = 120 wrong values: exhausts n ± 15 and widens to 1..M.
        _regenerate(generate_expression(n, ALL, m, rng), m, rng, 40)
    assert time.perf_counter() - t0 < 2.0


def test_exhausted_pool_still_returns_valid_set() -> None:
    rng = random.Random(0)
    expr = Expression(op="add", a=3, b=4, result=7)
    used = set(range(1, 101)) - {7}
    opts = generate_options(expr, 100, rng, used, previous_correct_index=0)
    _check_set(opts, 7)
    assert opts.correct_index != 0
    used = set(range(1, 32)) - {7}
    _check_set(generate_options(expr, 31, rng, used), 7, 31)


def test_candidates_above_m_are_dropped() -> None:
    rng = random.Random(1)
    expr = Expression(op="sub", a=50, b=1, result=49)  # a + b = 51 > M
    for _ in range(100):
        opts = generate_options(expr, 50, rng)
        _check_set(opts, 49, 50)


def test_prefers_plausible_candidates() -> None:
    rng = random.Random(2)
    expr = Expression(op="mul", a=7, b=8, result=56)
    plausible = {55, 57, 54, 58, 66, 46, 65, 63, 49, 64, 48}
    for _ in range(50):
        opts = generate_options(expr, 100, rng)
        assert set(opts.wrong_values) <= plausible
