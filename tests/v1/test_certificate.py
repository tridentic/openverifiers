"""The trusted certificate checker (raw/certificate.py) and its use (W1)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.objects.certify import find
from openverifiers.raw.certificate import Certificate, check, poly
from openverifiers.raw.formula import Unsupported
from openverifiers.raw.terms import Compound, Num, Str, Term
from openverifiers.runner import run_file

ROOT = Path(__file__).resolve().parents[2]


def n(x: int | Fraction) -> Num:
    return Num(Fraction(x))


def p(name: str) -> Compound:
    return Compound("f.p", (Str(name),))


def op(f: str, *a: Term) -> Compound:
    return Compound(f, a)


def cmp(o: str, a: Term, b: Term) -> Compound:
    return op("f.cmp", Str(o), a, b)


A, B, F, M, X = p("a"), p("b"), p("F"), p("m"), p("x")


def test_identity_and_ideal_membership() -> None:
    sq = op("*", op("+", A, B), op("+", A, B))
    goal = cmp("=", sq, op("+", op("+", op("*", A, A), op("*", n(2), op("*", A, B))),
                           op("*", B, B)))
    assert check(goal, {}, Certificate())                       # (a + b)^2 expands
    # From F = m a with m > 0: a = F / m, i.e. m a = F, a law solved for a.
    hyps = {"newton": cmp("=", F, op("*", M, A)), "pos": cmp(">", M, n(0))}
    goal2 = cmp("=", op("*", A, M), F)
    assert check(goal2, hyps, Certificate((), (("newton", n(-1)),)))
    # The same law, with the multiplier: m (a - F/m) = 0 needs m != 0.
    goal3 = cmp("=", A, op("/", F, n(1)))                       # a = F (false in general)
    assert not check(goal3, hyps, Certificate(("pos",), (("newton", n(-1)),)))


def test_inequalities_by_squares() -> None:
    goal = cmp(">=", op("+", op("*", A, A), op("*", B, B)), op("*", n(2), op("*", A, B)))
    cert = Certificate((), (), ((Fraction(1), op("-", A, B)),))
    assert check(goal, {}, cert)
    assert not check(goal, {}, Certificate((), (), ((Fraction(-1), op("-", A, B)),)))
    assert not check(goal, {}, Certificate((), (), ((Fraction(1), op("+", A, B)),)))
    # Squares never prove an equation.
    assert not check(cmp("=", A, A), {}, Certificate((), (), ((Fraction(0), A),)))


def test_rejections() -> None:
    hyps = {"ne": cmp("!=", X, n(0)), "eq": cmp("=", op("*", X, A), op("*", X, B)),
            "ge": cmp(">=", X, n(0))}
    goal = cmp("=", A, B)
    good = Certificate(("ne",), (("eq", n(1)),))
    assert check(goal, hyps, good)                              # x a = x b, x != 0 => a = b
    assert not check(goal, hyps, Certificate((), (("eq", n(1)),)))   # no multiplier
    assert not check(goal, hyps, Certificate(("ge",), (("eq", n(1)),)))  # x >= 0: may be 0
    assert not check(goal, hyps, Certificate(("ne",), (("eq", n(2)),)))  # wrong coefficient
    assert not check(goal, hyps, Certificate(("ne",), (("ge", n(1)),)))  # not an equation
    assert not check(cmp(">", A, B), hyps, good)                # strict goals: not supported
    # A != multiplier cannot justify an inequality (its sign is unknown).
    assert not check(cmp(">=", op("*", A, A), n(0)), hyps,
                     Certificate(("ne",), (), ((Fraction(1), A),)))
    with pytest.raises(Unsupported):
        poly(op("f.sqrt", A))


def test_finder_never_certifies_a_false_theorem() -> None:
    hyps = {"newton": cmp("=", F, op("*", M, A)), "pos": cmp(">", M, n(0))}
    for false in (cmp("=", A, F), cmp(">=", A, n(0)), cmp("=", op("*", M, A), op("+", F, n(1)))):
        assert find(false, hyps) is None


def test_calculus_in_normal_form() -> None:
    t = p("t")
    s = op("f.integral", op("+", p("u"), op("f.integral", A, t, t)), t, t)
    goal = cmp("=", s, op("+", op("*", p("u"), t), op("/", op("*", A, op("*", t, t)), n(2))))
    assert check(goal, {}, Certificate())                       # SUVAT s = ut + at^2/2


def test_library_theorems_move_to_kernel() -> None:
    """W1: the mechanics and calculus theorems are certified, so --strict keeps them."""
    from openverifiers.objects.engine import Settings
    for pkg in ("physics/mechanics.ov", "math/calculus.ov"):
        f = ROOT / "src/openverifiers/packages" / pkg
        res = run_file(f, files={str(f)}, settings=Settings(strict=True))
        th = [a for a in res.classes if a.kind == "theorem"]
        assert th and all(a.verdict == "PROVEN" and a.trust_base == {"kernel"} for a in th), \
            [(a.title, a.verdict) for a in th if a.trust_base != {"kernel"}]
        assert all(any("certificate [kernel" in s for s in a.steps) for a in th)


def test_normal_form_edge_paths() -> None:
    assert poly(op("^", op("+", A, n(1)), n(2))) == poly(op("+", op("+", op("*", A, A),
                                                                    op("*", n(2), A)), n(1)))
    with pytest.raises(Unsupported):
        poly(Str("a"))                                          # not an expression
    with pytest.raises(Unsupported):
        poly(op("^", A, B))                                     # symbolic exponent
    goal = cmp("<=", op("*", n(2), op("*", A, B)), op("+", op("*", A, A), op("*", B, B)))
    assert check(goal, {}, Certificate((), (), ((Fraction(1), op("-", A, B)),)))   # <= form
    with pytest.raises(Unsupported):
        check(A, {}, Certificate())                             # the goal is no comparison
