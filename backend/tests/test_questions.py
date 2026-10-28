from __future__ import annotations

import random

import pytest

from app.game.numbers import available_numbers, ops_for_number
from app.game.questions import evaluate, generate_expression
from tests.conftest import ALL_OP_COMBOS, combo_id

REPEATS = 20


def _check(expr, n: int, combo: frozenset) -> None:
    assert expr.op in combo
    assert expr.result == n
    a, b = expr.a, expr.b
    assert evaluate(expr.op, a, b) == n
    if expr.op in ("add", "sub"):
        assert 1 <= a <= 100 and 1 <= b <= 100 and 1 <= n <= 100
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
    for n in available_numbers(combo):
        for _ in range(REPEATS):
            _check(generate_expression(n, combo, rng), n, combo)


def test_mul_prefers_pairs_without_one() -> None:
    rng = random.Random(3)
    for n in available_numbers({"mul"}):
        pairs_without_one = [
            (x, n // x) for x in range(2, 11) if n % x == 0 and 2 <= n // x <= 10
        ]
        for _ in range(REPEATS):
            e = generate_expression(n, {"mul"}, rng)
            if pairs_without_one:
                assert 1 not in (e.a, e.b), (n, e)


def test_op_choice_is_among_possible_ops() -> None:
    rng = random.Random(5)
    seen = {generate_expression(100, {"add", "sub", "mul"}, rng).op for _ in range(200)}
    assert seen == {"add", "mul"}  # sub cannot produce 100
    seen = {generate_expression(6, {"add", "sub", "mul", "div"}, rng).op for _ in range(400)}
    assert seen == {"add", "sub", "mul", "div"}


def test_impossible_number_raises() -> None:
    with pytest.raises(ValueError):
        generate_expression(11, {"mul"}, random.Random(0))
    assert ops_for_number(100, {"sub"}) == []


def test_div_by_one_only_for_one() -> None:
    rng = random.Random(9)
    bs = {generate_expression(1, {"div"}, rng).b for _ in range(500)}
    assert 1 in bs
