import pytest
from hypothesis import given
from hypothesis import strategies as st
from solution import clamp


def test_R1_inside_range_is_identity():
    assert clamp(5, 0, 10) == 5


def test_R2_outside_range_hits_bound():
    assert clamp(-3, 0, 10) == 0
    assert clamp(42, 0, 10) == 10


def test_R3_empty_range_raises():
    with pytest.raises(ValueError):
        clamp(1, 5, 4)


@given(st.integers(), st.integers(), st.integers())
def test_R4_result_within_bounds(x, a, b):
    lo, hi = min(a, b), max(a, b)
    assert lo <= clamp(x, lo, hi) <= hi
