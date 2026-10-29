"""Spec *Thuật toán chi tiết* mục 5: sinh 4 đáp án A/B/C/D."""

from __future__ import annotations

import random
from collections.abc import Collection
from dataclasses import dataclass

from app.game.numbers import MIN_NUMBER
from app.game.questions import Expression

OPTION_KEYS: tuple[str, str, str, str] = ("A", "B", "C", "D")
WRONG_COUNT = 3
FILL_RADIUS = 15
WIDE_LIST_LIMIT = 10_000  # list 1..M only below this; sample otherwise


@dataclass(frozen=True)
class OptionSet:
    values: tuple[int, int, int, int]  # in A, B, C, D order
    correct_index: int  # 0..3, never sent to clients
    wrong_values: tuple[int, int, int]

    @property
    def correct_key(self) -> str:
        return OPTION_KEYS[self.correct_index]


def wrong_candidates(expr: Expression) -> list[int]:
    """Step 1: plausible wrong answers (unfiltered, may contain duplicates/out of range)."""
    n, a, b = expr.result, expr.a, expr.b
    cands = [n + 1, n - 1, n + 2, n - 2, n + 10, n - 10]
    if 10 <= n <= 99 and n // 10 != n % 10:
        cands.append((n % 10) * 10 + n // 10)
    if expr.op == "add":
        cands.append(a - b)
    elif expr.op == "sub":
        cands.append(a + b)
    elif expr.op == "mul":
        cands += [a * (b + 1), a * (b - 1), (a + 1) * b, (a - 1) * b]
    elif expr.op == "div":
        cands += [n + 1, n - 1]
    return cands


def _filtered(values: list[int], n: int, max_number: int, exclude: Collection[int]) -> list[int]:
    """Step 2: in 1..M, != n, unique (order kept), not in `exclude`."""
    seen: set[int] = set()
    out: list[int] = []
    for v in values:
        if MIN_NUMBER <= v <= max_number and v != n and v not in exclude and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _sample_wide(
    n: int, max_number: int, exclude: set[int], k: int, rng: random.Random
) -> list[int]:
    """Up to `k` distinct random values in 1..M, != n, not in `exclude`, without
    listing 1..M when M is large."""
    if max_number <= WIDE_LIST_LIMIT:
        pool = _filtered(list(range(MIN_NUMBER, max_number + 1)), n, max_number, exclude)
        return rng.sample(pool, min(len(pool), k))
    # M is large and `exclude` is tiny next to it: rejection sampling ends quickly.
    banned = set(exclude) | {n}
    free = max_number - sum(1 for v in banned if MIN_NUMBER <= v <= max_number)
    out: list[int] = []
    while len(out) < min(k, free):
        v = rng.randint(MIN_NUMBER, max_number)
        if v not in banned:
            banned.add(v)
            out.append(v)
    return out


def _pick_wrongs(
    expr: Expression, max_number: int, used_wrong: Collection[int], rng: random.Random
) -> list[int]:
    n = expr.result
    primary = _filtered(wrong_candidates(expr), n, max_number, used_wrong)
    if len(primary) >= WRONG_COUNT:
        return rng.sample(primary, WRONG_COUNT)

    # Step 3: fill with random numbers in n ± 15 (still in 1..M, same filter).
    near = range(max(MIN_NUMBER, n - FILL_RADIUS), min(max_number, n + FILL_RADIUS) + 1)
    fill = _filtered(list(near), n, max_number, set(used_wrong) | set(primary))
    picked = primary + rng.sample(fill, min(len(fill), WRONG_COUNT - len(primary)))
    if len(picked) >= WRONG_COUNT:
        return picked

    # Still short: widen to 1..M.
    picked += _sample_wide(n, max_number, set(used_wrong) | set(picked), WRONG_COUNT - len(picked), rng)
    if len(picked) >= WRONG_COUNT:
        return picked
    # Not in spec: every value of 1..M has been used; allow reusing old wrong values.
    picked += _sample_wide(n, max_number, set(picked), WRONG_COUNT - len(picked), rng)
    return picked


def generate_options(
    expr: Expression,
    max_number: int,
    rng: random.Random,
    used_wrong: Collection[int] = (),
    previous_correct_index: int | None = None,
) -> OptionSet:
    """Build A/B/C/D for `expr`; every value is in 1..`max_number`.

    `used_wrong`: wrong values already shown for this question (caller accumulates
    `OptionSet.wrong_values`). `previous_correct_index`: position of n last time;
    the new position is always different.
    """
    wrongs = _pick_wrongs(expr, max_number, used_wrong, rng)
    rng.shuffle(wrongs)
    positions = [i for i in range(len(OPTION_KEYS)) if i != previous_correct_index]
    correct_index = rng.choice(positions)
    values = list(wrongs)
    values.insert(correct_index, expr.result)
    return OptionSet(
        values=(values[0], values[1], values[2], values[3]),
        correct_index=correct_index,
        wrong_values=(wrongs[0], wrongs[1], wrongs[2]),
    )
