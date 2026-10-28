"""Spec *Thuật toán chi tiết* mục 1 (tập R) và mục 3 (bốc số)."""

from __future__ import annotations

import random
from collections.abc import Collection, Iterable
from typing import Literal

Op = Literal["add", "sub", "mul", "div"]
ALL_OPS: tuple[Op, ...] = ("add", "sub", "mul", "div")

MIN_NUMBER = 1
MAX_NUMBER = 100
TABLE_MIN = 1
TABLE_MAX = 10
MIN_R_SIZE = 25

MUL_PRODUCTS: frozenset[int] = frozenset(
    a * b for a in range(TABLE_MIN, TABLE_MAX + 1) for b in range(TABLE_MIN, TABLE_MAX + 1)
)


def enabled_ops(add: bool, sub: bool, mul: bool, div: bool) -> frozenset[Op]:
    """Convert the boolean flags of `GameConfig.operations` into a set of op names."""
    flags: dict[Op, bool] = {"add": add, "sub": sub, "mul": mul, "div": div}
    return frozenset(op for op, on in flags.items() if on)


def results_for_op(op: Op) -> frozenset[int]:
    """All values that operator `op` can produce under the game rules."""
    if op == "add":
        return frozenset(range(2, MAX_NUMBER + 1))  # a, b >= 1
    if op == "sub":
        return frozenset(range(1, MAX_NUMBER))  # a <= 100, b >= 1, result >= 1
    if op == "mul":
        return MUL_PRODUCTS
    if op == "div":
        return frozenset(range(TABLE_MIN, TABLE_MAX + 1))
    raise ValueError(f"unknown op: {op!r}")


def ops_for_number(n: int, ops: Iterable[Op]) -> list[Op]:
    """Enabled ops that can produce `n`, in canonical order."""
    enabled = set(ops)
    return [op for op in ALL_OPS if op in enabled and n in results_for_op(op)]


def available_numbers(ops: Iterable[Op]) -> list[int]:
    """Tập R, sorted ascending."""
    result: set[int] = set()
    for op in set(ops):
        result |= results_for_op(op)
    return sorted(result)


def is_valid_ops(ops: Collection[Op]) -> bool:
    """Config is valid when at least one op is on and |R| >= 25."""
    return len(ops) > 0 and len(available_numbers(ops)) >= MIN_R_SIZE


def draw_pool(
    r_numbers: Iterable[int],
    drawn: Iterable[int],
    card_numbers: Iterable[int] | None,
) -> list[int]:
    """Kho bốc: numbers in R, not drawn yet and (if `card_numbers` is given) on some card.

    Pass `card_numbers=None` when `draw_only_card_numbers` is off.
    """
    drawn_set = set(drawn)
    pool = set(r_numbers) - drawn_set
    if card_numbers is not None:
        pool &= set(card_numbers)
    pool.discard(0)
    return sorted(pool)


def draw_number(pool: Collection[int], rng: random.Random, avoid: int | None = None) -> int | None:
    """Pick uniformly from `pool`. `avoid` (the last skipped number) is not picked
    unless it is the only number left. Returns None when the pool is empty."""
    if not pool:
        return None
    choices = sorted(pool)
    if avoid is not None and len(choices) > 1:
        choices = [x for x in choices if x != avoid] or choices
    return rng.choice(choices)
