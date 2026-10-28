from __future__ import annotations

import itertools
import random

import pytest

from app.game.numbers import ALL_OPS, Op, is_valid_ops

ALL_OP_COMBOS: list[frozenset[Op]] = [
    frozenset(c) for k in range(1, 5) for c in itertools.combinations(ALL_OPS, k)
]
VALID_OP_COMBOS: list[frozenset[Op]] = [c for c in ALL_OP_COMBOS if is_valid_ops(c)]


def combo_id(combo: frozenset[Op]) -> str:
    return "+".join(op for op in ALL_OPS if op in combo)


@pytest.fixture
def rng() -> random.Random:
    return random.Random(12345)
