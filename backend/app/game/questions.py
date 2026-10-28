"""Spec *Thuật toán chi tiết* mục 4: sinh phép tính cho số n."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.game.numbers import MAX_NUMBER, TABLE_MAX, TABLE_MIN, Op, ops_for_number

Operator = Literal["+", "-", "x", ":"]

OPERATOR_SYMBOL: dict[Op, Operator] = {"add": "+", "sub": "-", "mul": "x", "div": ":"}
# Fallback `text` (Vietnamese style); FE builds its own display from operator, a, b.
DISPLAY_SYMBOL: dict[Op, str] = {"add": "+", "sub": "−", "mul": "×", "div": ":"}


@dataclass(frozen=True)
class Expression:
    op: Op
    a: int
    b: int
    result: int

    @property
    def operator(self) -> Operator:
        return OPERATOR_SYMBOL[self.op]

    @property
    def text(self) -> str:
        return f"{self.a} {DISPLAY_SYMBOL[self.op]} {self.b} = ?"


def evaluate(op: Op, a: int, b: int) -> int:
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "div":
        if a % b != 0:
            raise ValueError(f"{a} is not divisible by {b}")
        return a // b
    raise ValueError(f"unknown op: {op!r}")


def generate_expression(n: int, ops: Iterable[Op], rng: random.Random) -> Expression:
    """Pick uniformly one enabled op able to produce `n`, then build operands."""
    candidates = ops_for_number(n, ops)
    if not candidates:
        raise ValueError(f"no enabled operation can produce {n}")
    op = rng.choice(candidates)

    if op == "add":
        a = rng.randint(1, n - 1)
        b = n - a
    elif op == "sub":
        b = rng.randint(1, MAX_NUMBER - n)
        a = n + b
    elif op == "mul":
        pairs = [
            (x, n // x)
            for x in range(TABLE_MIN, TABLE_MAX + 1)
            if n % x == 0 and TABLE_MIN <= n // x <= TABLE_MAX
        ]
        without_one = [p for p in pairs if 1 not in p]
        a, b = rng.choice(without_one or pairs)
    else:  # div
        low = 1 if n == 1 else 2
        b = rng.randint(low, TABLE_MAX)
        a = n * b

    return Expression(op=op, a=a, b=b, result=n)
