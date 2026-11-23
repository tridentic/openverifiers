"""D-030 item 2: pi inside integrands. The trusted integrator combines Q(pi) samples
with the rational weights of unit samples (the result is linear in the samples)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from openverifiers.raw import qpi as Q
from openverifiers.raw.formula import _Eval
from openverifiers.raw.terms import Compound, Num, Str
from openverifiers.runner import run_file

R = Compound("f.p", (Str("r"),))
PI = Compound("f.pi", ())


def _at2(e: Compound) -> object:
    return _Eval({"r": Num(Fraction(2))}).expr(e)


def test_integrals_and_derivatives_of_pi_bodies_are_exact() -> None:
    sq = Compound("*", (R, R))
    assert _at2(Compound("f.integral", (Compound("*", (PI, sq)), R, R))) == \
        Q.value(Q.apply("*", [Num(Fraction(8, 3)), Q.PI]))
    assert _at2(Compound("f.deriv", (Compound("*", (PI, sq)), R, R))) == \
        Q.value(Q.apply("*", [Num(Fraction(4)), Q.PI]))
    assert _at2(Compound("f.integral", (Compound("+", (PI, R)), R, R))) == \
        Q.value(Q.apply("+", [Q.apply("*", [Num(Fraction(2)), Q.PI]), Num(Fraction(2))]))
    assert _at2(Compound("f.integral", (sq, R, R))) == Num(Fraction(8, 3))  # unchanged


def test_three_domains_reach_the_kernel() -> None:
    f = Path(__file__).parent / "pi_integrands.ov"
    res = run_file(f, files={str(f)})
    assert [(a.verdict, sorted(a.trust_base)) for a in res.classes] == \
        [("PROVEN", ["kernel"])] * 6                    # Disc, Ball, Tube and their theorems
    assert [(a.verdict, sorted(a.trust_base)) for a in res.objects] == \
        [("PROVEN", ["kernel"])] * 3                    # 9 pi m^2, 72 pi kg, 10 pi mol
    vals = [Q.from_term(next(iter(a.bindings[0].values())).args)  # type: ignore[union-attr]
            for a in res.objects]
    assert [(v.num, v.den) for v in vals] == [((Fraction(0), Fraction(9)), (Fraction(1),)),
                                             ((Fraction(0), Fraction(72)), (Fraction(1),)),
                                             ((Fraction(0), Fraction(10)), (Fraction(1),))]
