"""W1: the solver-side symbolic layer agrees with the trusted interval evaluator."""

from __future__ import annotations

from fractions import Fraction

import pytest

from openverifiers.bench.differential import exp_derivatives, run
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


def test_refusals_are_attributed_by_class() -> None:
    out = run(300, seed=1)
    by_class = out["by_class"]
    assert isinstance(by_class, dict) and "arithmetic" in by_class
    refused: int = sum(r["refused:trusted"] + r["refused:solver"] for r in by_class.values())
    total = out["refused"]
    assert isinstance(total, int) and refused >= total   # each refusal counted in its classes


def test_exp_chain_rule_matches_finite_differences() -> None:
    out = exp_derivatives(100, seed=0)
    assert out["disagree"] == 0, out["examples"]
    agree = out["agree"]
    assert isinstance(agree, int) and agree >= 90


def test_exp_cross_check_catches_a_constant_exp(monkeypatch: pytest.MonkeyPatch) -> None:
    real = expand._depends                            # exp(u(x)) treated as a constant in x

    def wrong(v: str, tau: str) -> bool:
        return v not in expand.EXPS and real(v, tau)
    monkeypatch.setattr(expand, "_depends", wrong)
    bad = exp_derivatives(100, seed=0)["disagree"]
    assert isinstance(bad, int) and bad > 0


def test_surd_normal_form_agrees_with_the_evaluator(monkeypatch: pytest.MonkeyPatch) -> None:
    from openverifiers.bench.differential import surd_normal_form
    from openverifiers.raw import certificate
    out = surd_normal_form(400, seed=1)
    assert out["disagree"] == 0 and out["agree"] == 400, out["examples"]
    real = certificate._mul

    def wrong(a: certificate.Poly, b: certificate.Poly) -> certificate.Poly:
        r = real(a, b)                       # forget the sqrt(k)^2 = k reduction's factor
        return {m: c for m, c in r.items()} if not any(
            v.startswith("sqrt(") for m in a for v, _ in m) else {
            m: c * 2 for m, c in r.items()}
    monkeypatch.setattr(certificate, "_mul", wrong)
    assert surd_normal_form(400, seed=1)["disagree"] > 0  # type: ignore[operator]


def test_accepted_positive_sums_are_positive() -> None:
    from openverifiers.bench.differential import positive_sums
    out = positive_sums(600, seed=2)
    assert out["disagree"] == 0, out["examples"]
    assert out["accepted"] > 40 and out["rejected"] > 300   # type: ignore[operator]
