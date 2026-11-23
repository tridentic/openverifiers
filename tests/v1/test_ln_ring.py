"""D-030 item 3: ln in the exp ring. d ln(u) = u' inv(u); a / u = a inv(u); the
relation u inv(u) = 1, and any ln or inv in a goal, need a checked witness u > 0."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from openverifiers.raw.certificate import Certificate, check, poly
from openverifiers.raw.terms import Compound, Num, Str, Term
from openverifiers.runner import run_file

FIX = Path(__file__).parent / "ln_ring.ov"


def n(x: int | Fraction) -> Num:
    return Num(Fraction(x))


def p(name: str) -> Compound:
    return Compound("f.p", (Str(name),))


def cmp(o: str, a: Term, b: Term) -> Compound:
    return Compound("f.cmp", (Str(o), a, b))


X = p("x")
LN_X = Compound("f.ln", (X,))


def test_three_domains_reach_the_kernel() -> None:
    res = run_file(FIX, files={str(FIX)})
    assert [(a.title, a.verdict, sorted(a.trust_base)) for a in res.classes
            if a.kind == "theorem"] == [
        ("theorem HomogeneousOde.solves", "PROVEN", ["kernel"]),       # JEE math p2q9's
        ("theorem FirstOrderDecay.log_slope", "PROVEN", ["kernel"]),   # closed form
        ("theorem IsothermalWork.pressure", "PROVEN", ["kernel"])]


def test_no_witness_no_proof_and_false_ln_claims_are_not_proven(tmp_path: Path) -> None:
    src = FIX.read_text()
    f = tmp_path / "a.ov"
    f.write_text(src.replace("  invariant positive: a0 > 0\n", "  invariant some: a0 != 0\n"))
    res = run_file(f, files={str(f)})
    [log] = [a for a in res.classes if a.title == "theorem FirstOrderDecay.log_slope"]
    assert log.verdict != "PROVEN" or "kernel" not in log.trust_base or log.certified is False
    f.write_text(src.replace("= n * R * temp / V", "= 2 * n * R * temp / V"))
    res = run_file(f, files={str(f)})
    [pr] = [a for a in res.classes if a.title == "theorem IsothermalWork.pressure"]
    assert pr.verdict != "PROVEN"


def test_the_checker_demands_a_true_witness() -> None:
    hyps = {"pos": cmp(">", X, n(0)), "nz": cmp("!=", X, n(0))}
    goal = cmp("=", Compound("f.deriv", (LN_X, X, X)), Compound("/", (n(1), X)))
    good = Certificate(positive=((X, n(1), ("pos",), ()),))
    assert check(goal, hyps, good)                        # d ln x = 1/x, with x > 0
    assert not check(goal, hyps, Certificate())           # an ln/inv with no witness
    for bad in ((X, n(-1), ("pos",), ()),                 # c not > 0
                (X, n(1), ("nz",), ()),                   # x != 0 is not x > 0
                (X, n(2), ("pos",), ()),                  # 2 x is not x
                (X, n(1), ("pos",), (X,))):               # not an exp atom
        assert not check(goal, hyps, Certificate(positive=(bad,)))
    # x inv(x) = 1 is usable only under its witness, as the coefficient name "@pos0"
    one = cmp("=", Compound("*", (X, Compound("/", (n(1), X)))), n(1))
    assert check(one, hyps, Certificate(coeffs=(("@pos0", n(1)),), positive=good.positive))
    assert not check(one, hyps, Certificate(coeffs=(("@pos0", n(1)),)))
    # the atoms: d inv(x) = -inv(x)^2; division by a constant stays rational
    assert poly(Compound("f.deriv", (Compound("/", (n(1), X)), X, X))) == \
        {k: -v for k, v in poly(Compound("*", (Compound("/", (n(1), X)),
                                                Compound("/", (n(1), X))))).items()}
    assert poly(Compound("/", (X, n(4)))) == {((str(X), 1),): Fraction(1, 4)}
