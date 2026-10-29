from __future__ import annotations

import itertools
import random

import pytest

from app.game.numbers import ALL_OPS, Op, is_valid_config

ALL_OP_COMBOS: list[frozenset[Op]] = [
    frozenset(c) for k in range(1, 5) for c in itertools.combinations(ALL_OPS, k)
]
VALID_OP_COMBOS: list[frozenset[Op]] = [c for c in ALL_OP_COMBOS if is_valid_config(c, 100)]

# M values exercised by the tests (CHANGELOG 2026-10-29).
MAX_NUMBERS: list[int] = [31, 50, 100, 1000, 10**9]
SMALL_MAX_NUMBERS: list[int] = [31, 50, 100, 1000]  # small enough to iterate all of R


def combo_id(combo: frozenset[Op]) -> str:
    return "+".join(op for op in ALL_OPS if op in combo)


def valid_cases(max_numbers: list[int]) -> list[tuple[frozenset[Op], int]]:
    """Every (ops, M) pair that is a valid config."""
    return [(c, m) for m in max_numbers for c in ALL_OP_COMBOS if is_valid_config(c, m)]


def case_id(case: tuple[frozenset[Op], int]) -> str:
    return f"{combo_id(case[0])}-M{case[1]}"


@pytest.fixture
def rng() -> random.Random:
    return random.Random(12345)
