"""Spec *Thuật toán chi tiết* mục 5: sinh 4 đáp án A/B/C/D."""

from __future__ import annotations

import random
from collections.abc import Collection
from dataclasses import dataclass

from app.game.numbers import MAX_NUMBER, MIN_NUMBER
from app.game.questions import Expression

OPTION_KEYS: tuple[str, str, str, str] = ("A", "B", "C", "D")
WRONG_COUNT = 3
FILL_RADIUS = 15


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


def _filtered(values: list[int], n: int, exclude: Collection[int]) -> list[int]:
    """Step 2: in 1..100, != n, unique (order kept), not in `exclude`."""
    seen: set[int] = set()
    out: list[int] = []
    for v in values:
        if MIN_NUMBER <= v <= MAX_NUMBER and v != n and v not in exclude and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _pick_wrongs(expr: Expression, used_wrong: Collection[int], rng: random.Random) -> list[int]:
    n = expr.result
    primary = _filtered(wrong_candidates(expr), n, used_wrong)
    if len(primary) >= WRONG_COUNT:
        return rng.sample(primary, WRONG_COUNT)

    # Step 3: fill with random numbers in n ± 15 (same filter).
    near = range(max(MIN_NUMBER, n - FILL_RADIUS), min(MAX_NUMBER, n + FILL_RADIUS) + 1)
    fill = _filtered(list(near), n, set(used_wrong) | set(primary))
    picked = primary + rng.sample(fill, min(len(fill), WRONG_COUNT - len(primary)))
    if len(picked) >= WRONG_COUNT:
        return picked

    # Not in spec: after many regenerations n ± 15 runs out. Widen to 1..100, and
    # as a last resort allow reusing previously used wrong values.
    wide = _filtered(list(range(MIN_NUMBER, MAX_NUMBER + 1)), n, set(used_wrong) | set(picked))
    picked += rng.sample(wide, min(len(wide), WRONG_COUNT - len(picked)))
    if len(picked) >= WRONG_COUNT:
        return picked
    reuse = _filtered(list(range(MIN_NUMBER, MAX_NUMBER + 1)), n, set(picked))
    picked += rng.sample(reuse, WRONG_COUNT - len(picked))
    return picked


def generate_options(
    expr: Expression,
    rng: random.Random,
    used_wrong: Collection[int] = (),
    previous_correct_index: int | None = None,
) -> OptionSet:
    """Build A/B/C/D for `expr`.

    `used_wrong`: wrong values already shown for this question (caller accumulates
    `OptionSet.wrong_values`). `previous_correct_index`: position of n last time;
    the new position is always different.
    """
    wrongs = _pick_wrongs(expr, used_wrong, rng)
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
