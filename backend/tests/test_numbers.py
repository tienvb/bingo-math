from __future__ import annotations

import random
import time
from collections import Counter

import pytest

from app.game.numbers import (
    TABLE_PRODUCTS,
    NumberSet,
    available_numbers,
    draw_number,
    enabled_ops,
    is_valid_config,
    number_set,
    pool_size,
)
from tests.conftest import ALL_OP_COMBOS, MAX_NUMBERS, SMALL_MAX_NUMBERS, combo_id

ALL = {"add", "sub", "mul", "div"}


def _brute_r(ops: frozenset, m: int) -> set[int]:
    """Reference R by enumerating operands (small M only)."""
    out: set[int] = set()
    if "add" in ops:
        out |= {a + b for a in range(1, m) for b in range(1, m - a + 1)}
    if "sub" in ops:
        out |= {a - b for a in range(1, m + 1) for b in range(1, a)}
    if "mul" in ops:
        out |= {a * b for a in range(1, 11) for b in range(1, 11) if a * b <= m}
    if "div" in ops:
        out |= {n for n in range(1, 11) for b in range(1, 11)
                if n * b <= m and (b >= 2 or n == 1)}
    return out


def test_all_ops_cover_1_to_100() -> None:
    assert available_numbers(ALL, 100) == list(range(1, 101))


def test_single_op_sets_m100() -> None:
    assert available_numbers({"add"}, 100) == list(range(2, 101))
    assert available_numbers({"sub"}, 100) == list(range(1, 100))
    assert available_numbers({"div"}, 100) == list(range(1, 11))
    assert len(available_numbers({"mul"}, 100)) == 42
    assert set(available_numbers({"mul"}, 100)) == TABLE_PRODUCTS


def test_spec_examples() -> None:
    assert len(number_set({"mul"}, 100)) == 42 and is_valid_config({"mul"}, 100)
    assert len(number_set({"mul"}, 31)) == 22 and not is_valid_config({"mul"}, 31)


@pytest.mark.parametrize("m", [31, 37, 50, 100, 150])
@pytest.mark.parametrize("combo", ALL_OP_COMBOS, ids=combo_id)
def test_r_matches_brute_force(combo: frozenset, m: int) -> None:
    assert available_numbers(combo, m) == sorted(_brute_r(combo, m))


@pytest.mark.parametrize("m", MAX_NUMBERS)
@pytest.mark.parametrize("combo", ALL_OP_COMBOS, ids=combo_id)
def test_r_within_1_to_m(combo: frozenset, m: int) -> None:
    r = number_set(combo, m)
    assert r.min >= 1 and r.max <= m
    if "add" in combo or "sub" in combo:
        assert len(r.intervals) <= 2
        assert len(r) >= m - 1
    else:
        assert len(r) <= 42 + 10


def test_validity() -> None:
    assert not is_valid_config(frozenset(), 100)
    assert not is_valid_config({"div"}, 100)  # |R| = 10
    assert not is_valid_config({"div"}, 10**9)
    assert is_valid_config({"mul"}, 100)  # |R| = 42
    assert is_valid_config({"mul", "div"}, 100)
    assert is_valid_config({"add"}, 31)
    assert is_valid_config(ALL, 10**9)
    assert not is_valid_config(ALL, 30)  # M must be > 30
    assert not is_valid_config(ALL, 1)
    assert is_valid_config(ALL, 2**53 - 1)
    assert not is_valid_config(ALL, 2**53)


def test_enabled_ops() -> None:
    assert enabled_ops(True, False, True, False) == {"add", "mul"}
    assert enabled_ops(False, False, False, False) == frozenset()


def test_number_set_basics() -> None:
    s = NumberSet([(10, 12), (1, 3), (4, 4), (20, 20), (11, 15)])
    assert s.intervals == ((1, 4), (10, 15), (20, 20))
    assert len(s) == 11 and s.to_list() == [1, 2, 3, 4, 10, 11, 12, 13, 14, 15, 20]
    for i, v in enumerate(s.to_list()):
        assert s.kth(i) == v and s.rank(v) == i and v in s
    assert 5 not in s and 0 not in s and 21 not in s
    with pytest.raises(IndexError):
        s.kth(11)
    with pytest.raises(ValueError):
        s.rank(5)


def test_huge_number_set_is_compact() -> None:
    r = number_set(ALL, 10**9)
    assert r.intervals == ((1, 10**9),)
    assert len(r) == 10**9 and r.kth(10**9 - 1) == 10**9 and r.rank(123456789) == 123456788


@pytest.mark.parametrize("m", SMALL_MAX_NUMBERS)
def test_pool_size_and_draw_without_card_filter(m: int) -> None:
    r = number_set(ALL, m)
    assert pool_size(r, [1, 2], None) == m - 2
    assert pool_size(r, [1, 2, 10**12], None) == m - 2  # numbers outside R ignored
    rng = random.Random(m)
    drawn: list[int] = []
    for _ in range(len(r)):
        n = draw_number(r, drawn, None, rng)
        assert n is not None and n in r and n not in drawn
        drawn.append(n)
    assert sorted(drawn) == r.to_list()
    assert pool_size(r, drawn, None) == 0
    assert draw_number(r, drawn, None, rng) is None


def test_pool_with_card_filter() -> None:
    r = number_set(ALL, 100)
    assert pool_size(r, [5], {0, 5, 7, 200}) == 1  # 0 = FREE, 200 not in R
    rng = random.Random(0)
    assert draw_number(r, [5], {0, 5, 7, 200}, rng) == 7
    assert draw_number(r, [5, 7], {0, 5, 7}, rng) is None


def test_draw_number_avoids_skipped_unless_only_one() -> None:
    rng = random.Random(1)
    r = number_set(ALL, 100)
    for _ in range(200):
        assert draw_number(r, [], {3, 4}, rng, avoid=3) == 4
    assert draw_number(r, [], {3}, rng, avoid=3) == 3
    # Without the card filter: R = {1..100} minus 98 drawn numbers.
    drawn = [n for n in range(1, 101) if n not in (3, 4)]
    for _ in range(200):
        assert draw_number(r, drawn, None, rng, avoid=3) == 4
    assert draw_number(r, drawn + [4], None, rng, avoid=3) == 3


def test_draw_without_card_filter_is_uniform() -> None:
    r = number_set({"mul"}, 100)  # 42 values, mostly isolated
    drawn = [r.kth(0), r.kth(20), r.kth(41)]
    rng = random.Random(3)
    counts = Counter(draw_number(r, drawn, None, rng) for _ in range(39 * 400))
    assert set(counts) == set(r.to_list()) - set(drawn)
    assert min(counts.values()) > 250 and max(counts.values()) < 600


def test_huge_m_draw_is_fast() -> None:
    r = number_set(ALL, 10**9)
    rng = random.Random(9)
    drawn: list[int] = []
    t0 = time.perf_counter()
    for _ in range(500):
        n = draw_number(r, drawn, None, rng, avoid=drawn[-1] if drawn else None)
        assert n is not None and 1 <= n <= 10**9 and n not in drawn
        drawn.append(n)
    assert pool_size(r, drawn, None) == 10**9 - 500
    assert time.perf_counter() - t0 < 2.0
