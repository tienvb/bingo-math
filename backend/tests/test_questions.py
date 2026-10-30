from __future__ import annotations

import random
import time

import pytest

from app.game.numbers import available_numbers, number_set, ops_for_number
from app.game.questions import evaluate, generate_expression
from tests.conftest import ALL_OP_COMBOS, SMALL_MAX_NUMBERS, combo_id

REPEATS = 20
ALL = {"add", "sub", "mul", "div"}


def _check(expr, n: int, combo: frozenset, m: int = 100) -> None:
    assert expr.op in combo
    assert expr.result == n
    a, b = expr.a, expr.b
    assert evaluate(expr.op, a, b) == n
    assert 1 <= a <= m and 1 <= b <= m and 1 <= n <= m  # every operand and result <= M
    if expr.op == "sub":
        assert a - b >= 1
    if expr.op == "mul":
        assert 1 <= a <= 10 and 1 <= b <= 10
    if expr.op == "div":
        assert 1 <= b <= 10 and 1 <= n <= 10 and a % b == 0
        if n != 1:
            assert b >= 2
    assert expr.operator == {"add": "+", "sub": "-", "mul": "x", "div": ":"}[expr.op]
    assert expr.text.endswith("= ?")


@pytest.mark.parametrize("combo", ALL_OP_COMBOS, ids=combo_id)
def test_every_n_in_r(combo: frozenset) -> None:
    rng = random.Random(7)
    for n in available_numbers(combo, 100):
        for _ in range(REPEATS):
            _check(generate_expression(n, combo, 100, rng), n, combo)


@pytest.mark.parametrize("m", SMALL_MAX_NUMBERS)
@pytest.mark.parametrize("combo", ALL_OP_COMBOS, ids=combo_id)
def test_every_n_in_r_for_m(combo: frozenset, m: int) -> None:
    rng = random.Random(m)
    repeats = 3 if m > 100 else 10
    for n in available_numbers(combo, m):
        for _ in range(repeats):
            _check(generate_expression(n, combo, m, rng), n, combo, m)


def test_huge_m_expressions() -> None:
    m = 10**9
    rng = random.Random(4)
    r = number_set(ALL, m)
    t0 = time.perf_counter()
    for n in [1, 2, 10, 11, 100, 101, 12345678, m - 1, m]:
        assert n in r
        for _ in range(50):
            _check(generate_expression(n, ALL, m, rng), n, ALL, m)
    assert time.perf_counter() - t0 < 1.0
    assert ops_for_number(m, ALL, m) == ["add"]  # sub cannot reach M, mul/div too small
    assert ops_for_number(90, ALL, m) == ["add", "sub", "mul"]


def test_div_respects_m() -> None:
    rng = random.Random(1)
    for _ in range(300):
        e = generate_expression(10, {"div"}, 31, rng)
        assert e.a <= 31 and e.b in (2, 3)
    assert {generate_expression(7, {"div"}, 50, rng).b for _ in range(300)} <= set(range(2, 8))


def test_sub_respects_m() -> None:
    rng = random.Random(2)
    for _ in range(300):
        e = generate_expression(40, {"sub"}, 50, rng)
        assert e.a <= 50 and 1 <= e.b <= 10


def test_mul_prefers_pairs_without_one() -> None:
    rng = random.Random(3)
    for n in available_numbers({"mul"}, 100):
        pairs_without_one = [
            (x, n // x) for x in range(2, 11) if n % x == 0 and 2 <= n // x <= 10
        ]
        for _ in range(REPEATS):
            e = generate_expression(n, {"mul"}, 100, rng)
            if pairs_without_one:
                assert 1 not in (e.a, e.b), (n, e)


def test_op_choice_is_among_possible_ops() -> None:
    rng = random.Random(5)
    seen = {generate_expression(100, {"add", "sub", "mul"}, 100, rng).op for _ in range(200)}
    assert seen == {"add", "mul"}  # sub cannot produce 100
    seen = {generate_expression(6, ALL, 100, rng).op for _ in range(400)}
    assert seen == {"add", "sub", "mul", "div"}
    seen = {generate_expression(50, ALL, 50, rng).op for _ in range(200)}
    assert seen == {"add", "mul"}  # n = M: sub would need a > M
    seen = {generate_expression(49, {"sub", "div"}, 50, rng).op for _ in range(50)}
    assert seen == {"sub"}


def test_impossible_number_raises() -> None:
    with pytest.raises(ValueError):
        generate_expression(11, {"mul"}, 100, random.Random(0))
    with pytest.raises(ValueError):
        generate_expression(64, {"mul"}, 50, random.Random(0))  # 8 x 8 > M
    assert ops_for_number(100, {"sub"}, 100) == []
    assert ops_for_number(100, {"sub"}, 101) == ["sub"]


def test_div_by_one_only_for_one() -> None:
    rng = random.Random(9)
    bs = {generate_expression(1, {"div"}, 100, rng).b for _ in range(500)}
    assert 1 in bs
