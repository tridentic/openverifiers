"""W1: the solver-side symbolic layer agrees with the trusted interval evaluator."""

from __future__ import annotations

from fractions import Fraction

import pytest

from openverifiers.bench.differential import run
from openverifiers.objects import expand
from openverifiers.raw import interval as I


def test_symbolic_layer_agrees_with_the_trusted_evaluator() -> None:
    out = run(500, seed=0)
    assert out["disagree"] == 0, out["examples"]
    agree = out["agree"]
    assert isinstance(agree, int) and agree >= 450    # the comparison is not vacuous


def test_the_differential_test_catches_a_planted_bug(monkeypatch: pytest.MonkeyPatch) -> None:
    real = expand.root_var

    def wrong(x: expand.Poly) -> expand.SNum:         # sqrt(x) computed as sqrt(x) + 1
        return expand.SNum(real(x).p + expand.Poly.const(Fraction(1)))
    monkeypatch.setattr(expand, "root_var", wrong)
    bad = run(500, seed=0)["disagree"]
    assert isinstance(bad, int) and bad > 0


def test_huge_exponents_are_refused_not_hung() -> None:
    with pytest.raises(I.IntervalError):
        I.exp(I.Iv.of(Fraction(10**6)))
