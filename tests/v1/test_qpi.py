"""D-026: exact Q(pi) in the checker, the exp differential ring in the trusted normal
form, the untrusted Q(pi) lift, and uniqueness certificates."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.objects.engine import Settings
from openverifiers.raw import qpi as Q
from openverifiers.raw.certificate import Certificate, check, poly
from openverifiers.raw.formula import ClassDef, Unsupported, failing, holds
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


PI = op("f.pi")


def test_qpi_arithmetic_is_exact() -> None:
    two_pi = Q.apply("*", [n(2), Q.PI])
    assert Q.apply("/", [two_pi, Q.PI]).rational() == 2             # 2 pi / pi = 2, exactly
    assert Q.apply("-", [two_pi, two_pi]).rational() == 0
    assert Q.apply("-", [Q.PI]).sign() == -1
    assert Q.apply("^", [Q.PI, n(2)]).num == tuple(map(Fraction, (0, 0, 1)))
    assert Q.value(Q.apply("*", [n(3), n(1)])) == n(3)
    t2 = Q.to_term(two_pi)
    assert isinstance(t2, Compound) and Q.from_term(t2.args) == two_pi   # round trip
    sq = Q.apply("^", [Q.PI, n(2)])
    assert Q.apply("-", [sq, n(10)]).sign() == -1                   # pi^2 < 10
    assert Q.apply("-", [sq, n(Fraction(9869604, 10**6))]).sign() == 1
    lo_hi = Q.PI.iv()
    assert lo_hi.lo < Fraction(355, 113) and lo_hi.hi > Fraction(3141592, 10**6)
    with pytest.raises(Q.QPiError):
        Q.QPi.make((Fraction(1),), ())                              # division by zero
    with pytest.raises(Q.QPiError):
        Q.apply("+", [Q.PI, Str("x")])                              # not a number
    with pytest.raises(Q.QPiError):
        Q.apply("f.sqrt", [Q.PI])
    for bad in ((n(3), n(1)), (Str("x"),), (n(-1), n(1))):
        with pytest.raises(Q.QPiError):
            Q.from_term(bad)
    # A sign the enclosure cannot separate is refused, not guessed.
    tiny = Q.QPi.make((Fraction(-314159265358979323846264338327950288419716939937510582097494459,
                                10 ** 62), Fraction(1)), (Fraction(1),))
    with pytest.raises(Q.QPiError):
        tiny.sign()


def test_evaluator_decides_pi_exactly() -> None:
    h = op("/", op("*", op("*", n(2), PI), n(1)), n(3))            # 2 pi / 3
    props = {"h": Q.to_term(Q.apply("/", [Q.apply("*", [n(2), Q.PI]), n(3)])), "p": n(1)}
    assert holds(cmp("=", p("h"), h), props)
    assert not holds(cmp("=", p("h"), op("*", n(2), n(1))), props)
    assert holds(cmp("<", p("h"), n(3)), props) and holds(cmp(">", p("h"), n(2)), props)
    assert holds(cmp("!=", PI, n(3)), {})
    assert holds(cmp(">", op("f.exp", PI), n(23)), {})           # e^pi via the enclosure
    cls = ClassDef("C", ("h",), (("C.h", cmp("=", op("*", p("h"), n(3)), op("*", n(2), PI))),), ())
    assert failing(cls, {"h": props["h"]}) == ()
    with pytest.raises(Unsupported):
        holds(cmp("=", op("f.sqrt", n(2)), PI), {})                # surds and Q(pi) do not mix
    with pytest.raises(Unsupported):
        holds(cmp("=", op("f.qpi", n(5), n(1)), n(1)), {})         # malformed stored value


def test_exp_ring_and_pi_in_the_normal_form() -> None:
    t, k, n0 = p("t"), p("k"), p("N0")
    decay = op("*", n0, op("f.exp", op("*", op("-", k), t)))
    rate = cmp("=", op("f.deriv", decay, t, t), op("*", op("-", k), decay))
    assert check(rate, {}, Certificate())                           # dN/dt = -k N
    wrong = cmp("=", op("f.deriv", decay, t, t), op("*", k, decay))
    assert not check(wrong, {}, Certificate())
    nested = op("f.exp", op("*", t, t))                             # d e^(t^2) = 2t e^(t^2)
    assert check(cmp("=", op("f.deriv", nested, t, t), op("*", op("*", n(2), t), nested)),
                 {}, Certificate())
    const = op("f.exp", k)                                          # exp(k) is constant in t
    assert check(cmp("=", op("f.deriv", op("*", const, t), t, t), const), {}, Certificate())
    with pytest.raises(Unsupported):
        poly(op("f.integral", decay, t, t))                         # refused, not guessed
    at_two = op("f.deriv", op("f.exp", op("*", k, t)), t, n(2))    # evaluated at t = 2
    assert check(cmp("=", at_two, op("*", k, op("f.exp", op("*", k, n(2))))), {}, Certificate())
    area = cmp("=", op("*", PI, op("*", p("r"), p("r"))), op("*", op("*", p("r"), PI), p("r")))
    assert check(area, {}, Certificate())                           # pi is an indeterminate


def test_pi_models_are_lifted_and_rechecked(tmp_path: Path) -> None:
    f = tmp_path / "pi.ov"
    f.write_text("package probe.pi\nfact type Ring {\n  property r: Real\n  property c: Real\n"
                 "  property d: Real\n  invariant pos: r > 0\n  invariant unit: r = 1\n"
                 "  invariant circ: c = 2 * pi * r\n  invariant diam: d * pi = c\n}\n"
                 "scenario s uses probe.pi {\n  query FIND ?c WHERE Ring{ r = 1, c = ?c }\n"
                 "  query PROVE UNIQUE ?d WHERE Ring{ d = ?d }\n}\n")
    res = run_file(f, files={str(f)})
    find, unique = res.objects
    assert find.verdict == "PROVEN" and find.trust_base == {"kernel"}
    c = next(iter(find.bindings[0].values()))
    assert isinstance(c, Compound) and Q.from_term(c.args) == Q.apply("*", [n(2), Q.PI])
    assert unique.verdict == "PROVEN" and unique.trust_base == {"kernel"}   # certified: d = 2
    assert any("uniqueness certificate" in s for s in unique.steps)
    strict = run_file(f, files={str(f)}, settings=Settings(strict=True))
    assert [a.verdict for a in strict.objects] == ["PROVEN", "PROVEN"]
