import pytest
from hypothesis import given
from hypothesis import strategies as st
from solution import parse_duration


def test_R1_single_units():
    assert parse_duration("90s") == 90
    assert parse_duration("5m") == 300
    assert parse_duration("2h") == 7200


def test_R2_combined_units():
    assert parse_duration("1h30m") == 5400
    assert parse_duration("1h2m3s") == 3723


@pytest.mark.parametrize("bad", ["", "10", "5x", "m5", "1m1h", "1h 2m", "1h1h"])
def test_R3_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)


@given(st.integers(0, 99), st.integers(0, 99), st.integers(0, 99))
def test_R4_round_trip(h, m, s):
    text = "".join(f"{n}{u}" for n, u in ((h, "h"), (m, "m"), (s, "s")) if n)
    if text:
        assert parse_duration(text) == 3600 * h + 60 * m + s
