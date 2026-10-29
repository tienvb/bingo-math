"""Spec *Thuật toán chi tiết* mục 1 (tập R) và mục 3 (bốc số).

`max_number` (M) has no upper bound, so R is never materialised: it is a `NumberSet`
of sorted, disjoint, inclusive intervals. Add/sub contribute one long interval each,
mul/div contribute at most a few dozen single numbers. Size, membership, k-th element
and rank are O(log #intervals); drawing is O(|excluded|).
"""

from __future__ import annotations

import bisect
import random
from collections.abc import Collection, Iterable, Iterator
from functools import lru_cache
from typing import Literal

Op = Literal["add", "sub", "mul", "div"]
ALL_OPS: tuple[Op, ...] = ("add", "sub", "mul", "div")

MIN_NUMBER = 1
DEFAULT_MAX_NUMBER = 100
MAX_NUMBER_EXCLUSIVE_MIN = 30  # max_number must be > 30
# Technical cap (CHANGELOG 2026-10-29): largest integer JavaScript represents exactly.
MAX_NUMBER_LIMIT = 2**53 - 1  # 9007199254740991
TABLE_MIN = 1
TABLE_MAX = 10
MIN_R_SIZE = 25

# Every product of the 1-10 table (filtered by M where used).
TABLE_PRODUCTS: frozenset[int] = frozenset(
    a * b for a in range(TABLE_MIN, TABLE_MAX + 1) for b in range(TABLE_MIN, TABLE_MAX + 1)
)


class NumberSet:
    """Immutable set of positive ints stored as merged inclusive intervals."""

    __slots__ = ("intervals", "_starts", "_prefix", "_size")

    def __init__(self, intervals: Iterable[tuple[int, int]]) -> None:
        merged: list[tuple[int, int]] = []
        for lo, hi in sorted((lo, hi) for lo, hi in intervals if lo <= hi):
            if merged and lo <= merged[-1][1] + 1:
                if hi > merged[-1][1]:
                    merged[-1] = (merged[-1][0], hi)
            else:
                merged.append((lo, hi))
        self.intervals: tuple[tuple[int, int], ...] = tuple(merged)
        self._starts = [lo for lo, _ in merged]
        prefix = [0]
        for lo, hi in merged:
            prefix.append(prefix[-1] + hi - lo + 1)
        self._prefix = prefix  # _prefix[i] = number of elements before interval i
        self._size = prefix[-1]

    @classmethod
    def from_values(cls, values: Iterable[int]) -> NumberSet:
        return cls((v, v) for v in values)

    @property
    def size(self) -> int:
        """Number of elements. Use this, not `len()`: `len()` overflows above 2**63."""
        return self._size

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __contains__(self, n: object) -> bool:
        if not isinstance(n, int):
            return False
        i = bisect.bisect_right(self._starts, n) - 1
        return i >= 0 and n <= self.intervals[i][1]

    def __iter__(self) -> Iterator[int]:
        for lo, hi in self.intervals:
            yield from range(lo, hi + 1)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NumberSet) and self.intervals == other.intervals

    def __hash__(self) -> int:
        return hash(self.intervals)

    def __repr__(self) -> str:
        return f"NumberSet({list(self.intervals)!r})"

    @property
    def min(self) -> int:
        return self.intervals[0][0]

    @property
    def max(self) -> int:
        return self.intervals[-1][1]

    def kth(self, k: int) -> int:
        """Element with 0-based rank `k` in ascending order."""
        if not 0 <= k < self._size:
            raise IndexError(k)
        i = bisect.bisect_right(self._prefix, k) - 1
        return self.intervals[i][0] + (k - self._prefix[i])

    def rank(self, n: int) -> int:
        """0-based rank of `n` (must be a member)."""
        i = bisect.bisect_right(self._starts, n) - 1
        if i < 0 or n > self.intervals[i][1]:
            raise ValueError(f"{n} not in set")
        return self._prefix[i] + (n - self.intervals[i][0])

    def to_list(self) -> list[int]:
        """Only for small sets (tests)."""
        return list(self)


def enabled_ops(add: bool, sub: bool, mul: bool, div: bool) -> frozenset[Op]:
    """Convert the boolean flags of `GameConfig.operations` into a set of op names."""
    flags: dict[Op, bool] = {"add": add, "sub": sub, "mul": mul, "div": div}
    return frozenset(op for op, on in flags.items() if on)


def mul_products(max_number: int) -> frozenset[int]:
    return frozenset(p for p in TABLE_PRODUCTS if p <= max_number)


def div_low(n: int) -> int:
    """Smallest allowed divisor for quotient n (b = 1 only when n = 1)."""
    return 1 if n == 1 else 2


def div_high(n: int, max_number: int) -> int:
    """Largest allowed divisor b with n * b <= M."""
    return min(TABLE_MAX, max_number // n)


def div_results(max_number: int) -> frozenset[int]:
    return frozenset(
        n for n in range(TABLE_MIN, TABLE_MAX + 1) if div_low(n) <= div_high(n, max_number)
    )


def _op_intervals(op: Op, max_number: int) -> list[tuple[int, int]]:
    if op == "add":
        return [(2, max_number)]  # a, b >= 1, a + b <= M
    if op == "sub":
        return [(1, max_number - 1)]  # a <= M, b >= 1, result >= 1
    if op == "mul":
        return [(p, p) for p in mul_products(max_number)]
    if op == "div":
        return [(n, n) for n in div_results(max_number)]
    raise ValueError(f"unknown op: {op!r}")


def results_for_op(op: Op, max_number: int) -> NumberSet:
    """All values operator `op` can produce under the game rules for M = max_number."""
    return NumberSet(_op_intervals(op, max_number))


def can_produce(op: Op, n: int, max_number: int) -> bool:
    if op == "add":
        return 2 <= n <= max_number
    if op == "sub":
        return 1 <= n <= max_number - 1
    if op == "mul":
        return n <= max_number and n in TABLE_PRODUCTS
    if op == "div":
        return TABLE_MIN <= n <= TABLE_MAX and div_low(n) <= div_high(n, max_number)
    raise ValueError(f"unknown op: {op!r}")


def ops_for_number(n: int, ops: Iterable[Op], max_number: int) -> list[Op]:
    """Enabled ops that can produce `n`, in canonical order."""
    enabled = set(ops)
    return [op for op in ALL_OPS if op in enabled and can_produce(op, n, max_number)]


@lru_cache(maxsize=256)
def _number_set_cached(ops: frozenset[Op], max_number: int) -> NumberSet:
    intervals: list[tuple[int, int]] = []
    for op in ops:
        intervals += _op_intervals(op, max_number)
    return NumberSet(intervals)


def number_set(ops: Iterable[Op], max_number: int) -> NumberSet:
    """Tập R for the enabled ops and M."""
    return _number_set_cached(frozenset(ops), max_number)


def available_numbers(ops: Iterable[Op], max_number: int) -> list[int]:
    """Tập R as a sorted list. Only for small M (tests); the engine uses `number_set`."""
    return number_set(ops, max_number).to_list()


def is_valid_max_number(max_number: int) -> bool:
    return MAX_NUMBER_EXCLUSIVE_MIN < max_number <= MAX_NUMBER_LIMIT


def is_valid_config(ops: Collection[Op], max_number: int) -> bool:
    """Valid when at least one op is on, M > 30 and |R| >= 25."""
    return (
        len(ops) > 0
        and is_valid_max_number(max_number)
        and number_set(ops, max_number).size >= MIN_R_SIZE
    )


# ---------------------------------------------------------------------------
# Drawing (mục 3)
# ---------------------------------------------------------------------------


def _card_pool(r: NumberSet, drawn: Collection[int], card_numbers: Iterable[int]) -> list[int]:
    drawn_set = set(drawn)
    return sorted({n for n in card_numbers if n != 0 and n in r and n not in drawn_set})


def pool_size(r: NumberSet, drawn: Collection[int], card_numbers: Iterable[int] | None) -> int:
    """Size of the kho bốc. `card_numbers=None` means `draw_only_card_numbers` is off."""
    if card_numbers is not None:
        return len(_card_pool(r, drawn, card_numbers))
    return r.size - sum(1 for n in set(drawn) if n in r)


def sample_distinct(start: int, stop: int, k: int, rng: random.Random) -> list[int]:
    """`k` distinct ints from range(start, stop), uniformly, in O(k) even when the range
    is astronomically large (`random.sample` needs `len()`, which overflows)."""
    width = stop - start
    if k > width:
        raise ValueError("sample larger than population")
    if width <= 1 << 20:
        return rng.sample(range(start, stop), k)
    out: list[int] = []
    seen: set[int] = set()
    while len(out) < k:
        v = start + rng.randrange(width)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _kth_excluding(r: NumberSet, k: int, excluded_ranks: list[int]) -> int:
    """k-th (0-based) element of R whose rank is not in `excluded_ranks` (sorted, unique)."""
    rank = k
    for ex in excluded_ranks:
        if ex <= rank:
            rank += 1
        else:
            break
    return r.kth(rank)


def draw_number(
    r: NumberSet,
    drawn: Collection[int],
    card_numbers: Iterable[int] | None,
    rng: random.Random,
    avoid: int | None = None,
) -> int | None:
    """Pick uniformly from the kho bốc; None when it is empty.

    With `card_numbers` (draw_only_card_numbers on) the pool is small and listed. Without,
    it is R minus `drawn`, sampled by rank without listing R. `avoid` (the last skipped
    number) is not picked unless it is the only number left.
    """
    if card_numbers is not None:
        pool = _card_pool(r, drawn, card_numbers)
        if not pool:
            return None
        if avoid is not None and len(pool) > 1:
            pool = [x for x in pool if x != avoid] or pool
        return rng.choice(pool)

    excluded = {n for n in drawn if n in r}
    remaining = r.size - len(excluded)
    if remaining <= 0:
        return None
    if avoid is not None and remaining > 1 and avoid in r and avoid not in excluded:
        excluded.add(avoid)
        remaining -= 1
    ranks = sorted(r.rank(n) for n in excluded)
    return _kth_excluding(r, rng.randrange(remaining), ranks)
