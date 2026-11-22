"""Edge paths of the trusted exact-value code: surds, intervals, numeric checks."""

from __future__ import annotations

from fractions import Fraction

import pytest

from openverifiers.raw import interval as I
from openverifiers.raw.formula import ClassDef, Unsupported, _Eval, holds
from openverifiers.raw.numeric import failing_numeric
from openverifiers.raw.surd import Surd, SurdError
from openverifiers.raw.terms import Compound, Num, Str, Term


def n(x: int | Fraction) -> Num:
    return Num(Fraction(x))


def c(f: str, *a: Term) -> Compound:
    return Compound(f, a)


def p(name: str) -> Compound:
    return c("f.p", Str(name))


def ev(term: Term, **props: Term) -> object:
    return _Eval(props).expr(term)


def cmp(op: str, a: Term, b: Term) -> Compound:
    return c("f.cmp", Str(op), a, b)


R2 = c("f.sqrt", n(2))


def test_surd_arithmetic_paths() -> None:
    assert ev(c("-", R2)) == Surd.make({2: Fraction(-1)})                  # negation
    assert ev(c("/", R2, R2)) == n(1)                                     # single-term division
    assert ev(c("^", R2, n(4))) == n(4)                                   # integer power
    assert ev(c("*", R2, R2)) == n(2)
    with pytest.raises(Unsupported):                                      # sum in a divisor
        ev(c("/", n(1), c("+", R2, c("f.sqrt", n(3)))))
    with pytest.raises(Unsupported):
        ev(c("^", R2, c("f.sqrt", n(2))))                                 # irrational exponent
    with pytest.raises(SurdError):
        (Surd.sqrt(Fraction(2)) + Surd.sqrt(Fraction(3))).inverse()


def test_sign_needs_more_than_ten_digits() -> None:
    close = Surd.sqrt(Fraction(2)) - Surd.of(Fraction(141421356237309504880168872,
                                                       10**26))
    assert close.sign() == 1                                              # refines past 1e-10


def test_points_with_surd_coordinates_and_bad_points() -> None:
    a = c("f.tuple", n(0), n(0))
    b = c("f.tuple", c("f.surd", n(2), n(1)), n(0))                       # (sqrt 2, 0)
    assert holds(cmp("=", c("f.dist2", a, b), n(2)), {})
    assert holds(cmp("=", c("f.dist", a, b), R2), {})
    with pytest.raises(Unsupported):                                      # not a coordinate
        ev(c("f.dist2", a, c("f.tuple", Str("x"), n(0))))
    with pytest.raises(Unsupported):                                      # unreducible radicand
        ev(c("f.dist2", a, c("f.tuple", c("f.surd", n(1_000_003 * 1_000_033), n(1)), n(0))))
    # A nested root against a negative number, and a set of surds.
    nested = c("f.dist", a, c("f.tuple", c("f.surd", n(1), n(1), n(2), n(1)), n(0)))
    assert holds(cmp(">", nested, n(-1)), {})
    s = ev(c("f.set", R2, n(1)))
    assert isinstance(s, Compound) and c("f.surd", n(2), n(1)) in s.args


def test_value_type_errors() -> None:
    with pytest.raises(Unsupported):
        ev(c("+", R2, Str("x")))                                          # not a number
    with pytest.raises(Unsupported):
        ev(c("f.sqrt", R2))                                               # sqrt of a surd
    with pytest.raises(Unsupported):
        ev(c("f.subsets", c("f.set", n(1)), R2))


def test_calculus_edge_paths() -> None:
    t = p("t")
    quot = c("f.integral", c("/", c("*", t, t), n(2)), t, t)              # degree through /
    assert ev(quot, t=n(3)) == n(Fraction(9, 2))
    powr = c("f.deriv", c("^", t, n(3)), t, t)                            # degree through ^
    assert ev(powr, t=n(2)) == n(12)
    with pytest.raises(Unsupported):                                      # other variable
        ev(c("f.integral", c("f.integral", t, p("u"), p("u")), t, t), t=n(1), u=n(1))
    with pytest.raises(Unsupported):                                      # non-number body
        ev(c("f.integral", c("f.tuple", t), t, t), t=n(1))
    with pytest.raises(Unsupported):                                      # non-number limit
        ev(c("f.integral", t, t, c("f.tuple", n(1))), t=n(1))


def test_interval_paths() -> None:
    with pytest.raises(I.IntervalError):
        I.Iv.of(Fraction(1)) / I.Iv(Fraction(-1), Fraction(1))
    assert I.Iv.of(Fraction(3)).power(2) == I.Iv.of(Fraction(9))
    small = I.ln(I.Iv.of(Fraction(1, 8)))                                 # reduces upward
    assert Fraction(-20795, 10000) < small.lo <= small.hi < Fraction(-20794, 10000)
    with pytest.raises(I.IntervalError):
        I.ln(I.Iv(Fraction(1, 10), Fraction(100)))                       # too wide to reduce
    with pytest.raises(I.IntervalError):
        I.sqrt(I.Iv.of(Fraction(-1)))
    e = I.from_surd(((2, Fraction(1)),))
    assert e.lo < Fraction(14143, 10000) and e.hi > Fraction(14142, 10000)
    # Intervals mixed with surds and negated / raised in the evaluator.
    iv = c("f.iv", n(1), n(2))
    assert holds(cmp("<", c("-", iv), n(0)), {})
    assert holds(cmp(">", c("^", iv, n(2)), n(Fraction(1, 2))), {})
    assert holds(cmp(">", c("+", iv, R2), n(2)), {})
    with pytest.raises(Unsupported):
        ev(c("f.ln", c("-", iv)))                                         # ln of a negative
    with pytest.raises(Unsupported):
        holds(cmp("=", iv, n(1)), {})                                     # overlap: undecided
    st = ev(c("f.set", c("f.exp", n(0))))
    assert isinstance(st, Compound) and st.args[0].functor == "f.iv"      # type: ignore[union-attr]


def test_numeric_check_paths() -> None:
    eq = cmp("=", p("x"), c("f.exp", n(1)))
    cls = ClassDef("C", ("x", "y"), (("C.d", eq), ("C.pos", cmp(">", p("y"), n(5)))), ())
    iv = c("f.iv", n(2), n(3))
    assert failing_numeric(cls, {"x": iv, "y": n(1)}) == ("C.pos",)       # strict invariant
    with pytest.raises(Unsupported):
        failing_numeric(cls, {"x": iv})                                   # missing property
    nodef = ClassDef("C", ("x",), (("C.pos", cmp(">", p("x"), n(0))),), ())
    with pytest.raises(Unsupported):
        failing_numeric(nodef, {"x": iv})                                 # no definition
