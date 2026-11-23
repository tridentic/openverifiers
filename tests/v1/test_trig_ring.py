"""D-033: sin and cos of a variable in the certificate normal form, the evaluator
and the language, in three domains (tests/v1/trig_ring.ov)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.lang.errors import OVError
from openverifiers.raw import interval as I
from openverifiers.raw.certificate import poly
from openverifiers.raw.terms import Compound, Num, Str
from openverifiers.runner import run_file

FIX = Path(__file__).parent / "trig_ring.ov"
X = Compound("f.p", (Str("x"),))
SIN, COS = Compound("f.sin", (X,)), Compound("f.cos", (X,))


def sq(a: Compound) -> Compound:
    return Compound("*", (a, a))


def test_normal_form_rules() -> None:
    assert poly(Compound("+", (sq(SIN), sq(COS)))) == {(): Fraction(1)}
    assert poly(Compound("f.deriv", (SIN, X, X))) == poly(COS)
    assert poly(Compound("f.deriv", (COS, X, X))) == poly(Compound("-", (SIN,)))
    assert poly(sq(sq(COS))) == poly(sq(Compound("-", (Num(Fraction(1)), sq(SIN)))))
    assert poly(Compound("f.sin", (Num(Fraction(0)),))) == {}
    assert poly(Compound("f.cos", (Num(Fraction(0)),))) == {(): Fraction(1)}


def test_interval_sin_cos_are_rigorous() -> None:
    s, c = I.trig(I.Iv.of(Fraction(1)), False), I.trig(I.Iv.of(Fraction(1)), True)
    # sin 1 and cos 1 to 80 digits; the enclosures must meet [v - 1e-80, v + 1e-80]
    sin1 = Fraction("0.8414709848078965066525023216302989996225"
                    "6306079837106567275170999191040439123967")
    cos1 = Fraction("0.5403023058681397174009366074429766037323"
                    "1042061792222767009725538110039477447176")
    eps = Fraction(1, 10**80)
    assert s.lo <= sin1 + eps and sin1 - eps <= s.hi and s.hi - s.lo < Fraction(1, 10**50)
    assert c.lo <= cos1 + eps and cos1 - eps <= c.hi and c.hi - c.lo < Fraction(1, 10**50)
    with pytest.raises(I.IntervalError):
        I.trig(I.Iv.of(Fraction(9)), False)


def test_three_domains_reach_the_kernel() -> None:
    res = run_file(FIX, files={str(FIX)})
    assert {(a.title, a.verdict, tuple(sorted(a.trust_base))) for a in res.classes
            if a.kind == "theorem"} == {
        ("theorem SpringMass.energy", "PROVEN", ("kernel",)),
        ("theorem Inductor.phasor_circle", "PROVEN", ("kernel",)),
        ("theorem TrigIdentities.product_rule", "PROVEN", ("kernel",)),
        ("theorem TrigIdentities.square_of_sum", "PROVEN", ("kernel",))}


def test_false_trig_claims_are_not_proven(tmp_path: Path) -> None:
    f = tmp_path / "t.ov"
    f.write_text(FIX.read_text().replace("= 1 + 2 * sin(x) * cos(x)", "= 1")
                 .replace("= k * A * A", "= 2 * k * A * A"))
    res = run_file(f, files={str(f)})
    bad = {a.title: a.verdict for a in res.classes if a.kind == "theorem"}
    assert bad["theorem TrigIdentities.square_of_sum"] != "PROVEN"
    assert bad["theorem SpringMass.energy"] != "PROVEN"


def test_sin_of_a_dimensioned_argument_is_refused(tmp_path: Path) -> None:
    f = tmp_path / "d.ov"
    f.write_text("package probe.d\nfact type W {\n  property t: Time\n  property y: Real\n"
                 "  invariant wave: y = sin(t)\n}\n")
    with pytest.raises(OVError) as e:
        run_file(f, files={str(f)})
    assert "E302" in str(e.value) and "got Time" in str(e.value)    # radians only


def test_evaluator_differentiates_trig_bodies_and_decides_points() -> None:
    from openverifiers.raw.formula import _Eval, holds
    d = _Eval({"x": Num(Fraction(1))}).expr(Compound("f.deriv", (SIN, X, X)))
    c = I.trig(I.Iv.of(Fraction(1)), True)
    assert isinstance(d, I.Iv) and d.lo <= c.hi and c.lo <= d.hi        # d sin = cos at 1
    zero = {"x": Num(Fraction(0))}                                      # cos 0 = 1 exactly
    assert holds(Compound("f.cmp", (Str("="), Compound("f.deriv", (SIN, X, X)),
                                    Num(Fraction(1)))), zero)
    assert I.decide("=", I.Iv.of(Fraction(1)), I.Iv.of(Fraction(1))) is True
    assert I.decide("=", I.Iv(Fraction(0), Fraction(1)), I.Iv.of(Fraction(1))) is None


def test_n043_is_a_kernel_theorem_in_the_draft() -> None:
    from openverifiers.objects.engine import Settings
    f = Path(__file__).resolve().parents[2] / "drafts/packages/physics/rotation.ov"
    res = run_file(f, files={str(f)}, settings=Settings(drafts=True))
    got = {a.title: (a.verdict, tuple(sorted(a.trust_base))) for a in res.classes}
    assert got["theorem TorsionMotion.small_oscillation"] == ("PROVEN", ("kernel",))
    assert got["class TorsionMotion is consistent"] == ("PROVEN", ("kernel",))
