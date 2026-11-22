"""M-CAP library layer: calculus in the evaluator, units in classes, axiom kinds, audit."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.lang.errors import OVError
from openverifiers.raw.formula import ClassDef, Unsupported, _coefficients, _Eval, failing
from openverifiers.raw.terms import Compound, Num, Str
from openverifiers.runner import run_file

ROOT = Path(__file__).resolve().parents[2]


def p(name: str) -> Compound:
    return Compound("f.p", (Str(name),))


def n(x: int | Fraction) -> Num:
    return Num(Fraction(x))


def ev(term: Compound, **props: int) -> Num:
    v = _Eval({k: n(x) for k, x in props.items()}).expr(term)
    assert isinstance(v, Num)
    return v


# ---------------------------------------------------------------- exact calculus (trusted)


def test_integral_and_derivative_are_exact() -> None:
    t, a, u = p("t"), p("a"), p("u")
    # integral(a, t) at t = 3 with a = 2: 6
    assert ev(Compound("f.integral", (a, p("t"), p("t"))), a=2, t=3).value == 6
    # integral(u + integral(a, t), t) = u t + a t^2 / 2 = 4*3 + 9 = 21
    inner = Compound("f.integral", (a, p("t"), p("t")))
    outer = Compound("f.integral", (Compound("+", (u, inner)), p("t"), p("t")))
    assert ev(outer, a=2, t=3, u=4).value == 21
    # deriv(t^3, t) at t = 5: 75; deriv(7, t) = 0
    cube = Compound("*", (t, Compound("*", (t, t))))
    assert ev(Compound("f.deriv", (cube, p("t"), p("t"))), t=5).value == 75
    assert ev(Compound("f.deriv", (n(7), p("t"), p("t"))), t=5).value == 0
    # fractions stay exact: integral(t^2) at 1/2 = 1/24
    sq = Compound("*", (t, t))
    v = _Eval({"t": Num(Fraction(1, 2))}).expr(Compound("f.integral", (sq, p("t"), p("t"))))
    assert isinstance(v, Num) and v.value == Fraction(1, 24)


def test_calculus_rejects_what_is_not_a_polynomial_in_the_variable() -> None:
    t = p("t")
    for body in (Compound("/", (n(1), t)), Compound("abs", (t,)),
                 Compound("f.dist", (Compound("f.tuple", (t, t)), Compound("f.tuple", (t, t))))):
        with pytest.raises(Unsupported):
            ev(Compound("f.integral", (body, p("t"), p("t"))), t=2)


def test_coefficients_recover_the_polynomial() -> None:
    # y = 1 + 2 i - 3 i^2 + i^3 sampled at i = 0..3
    ys = [Fraction(1 + 2 * i - 3 * i * i + i ** 3) for i in range(4)]
    assert _coefficients(ys) == [1, 2, -3, 1]


def test_checker_rejects_a_wrong_displacement() -> None:
    a, u = p("a"), p("u")
    s = Compound("f.integral", (Compound("+", (u, Compound("f.integral", (a, p("t"), p("t"))))),
                                p("t"), p("t")))
    inv = Compound("f.cmp", (Str("="), p("s"), s))
    cls = ClassDef("K", ("u", "a", "t", "s"), (("K.disp", inv),), ())
    good = {"u": n(4), "a": n(2), "t": n(3), "s": n(21)}
    assert failing(cls, good) == ()
    assert failing(cls, {**good, "s": n(12)}) == ("K.disp",)


# ---------------------------------------------------------------- units in classes


def run(src: str, tmp_path: Path, name: str = "t.ov"):  # type: ignore[no-untyped-def]
    f = tmp_path / name
    f.write_text(src)
    return run_file(f, files={str(f)})


KIN = """package probe.kin
fact type K {
  property u: Velocity
  property a: Accel
  property t: Time
  property s: Length
  invariant elapsed: t >= 0
  invariant disp: s = u * t + a * t * t / 2
}
"""


def test_quantity_unknowns_solve_and_print_with_units(tmp_path: Path) -> None:
    res = run(KIN + "scenario k1 uses probe.kin {\n"
              "  query FIND ?s WHERE K{ u = 1 m/s, a = 2 m/s^2, t = 500 ms, s = ?s }\n"
              "  expect PROVEN 75 cm\n}\n", tmp_path)
    [a] = res.objects
    assert a.verdict == "PROVEN" and a.expect_ok, a.expect_msg
    from openverifiers.objects.engine import show
    assert show(a.bindings[0]["s"]) == "0.75 m"


@pytest.mark.parametrize("bad", [
    "  invariant wrong: s = u + a\n",                      # Length vs Velocity + Accel
    "  invariant wrong: u + t > 0\n",                      # Velocity + Time
])
def test_class_formulas_are_dimension_checked(tmp_path: Path, bad: str) -> None:
    src = KIN.replace("}\n", bad + "}\n")
    with pytest.raises(OVError) as e:
        run(src, tmp_path)
    assert "E301" in str(e.value.render())


def test_pattern_values_are_dimension_checked(tmp_path: Path) -> None:
    with pytest.raises(OVError) as e:
        run(KIN + "scenario k2 uses probe.kin {\n"
            "  query FIND ?s WHERE K{ u = 1 m/s^2, a = 2 m/s^2, t = 1 s, s = ?s }\n}\n",
            tmp_path)
    assert "E301" in str(e.value.render())


# ---------------------------------------------------------------- axiom kinds and audit


AUDITED = """package probe.audit
type Thing
predicate p(x: Thing) world open
predicate q(x: Thing) world open
law observed(x: Thing): p(x) -> q(x)
definition named(x: Thing): q(x) -> p(x)
fact type Pair {
  property a: Real
  property b: Real
  invariant pos: a > 0
  law link: b = 2 * a
  theorem b_pos: b > 0
  lemma b_big: b > a
  theorem false_one: b < a
}
"""


def test_kinds_parse_and_lower(tmp_path: Path) -> None:
    res = run(AUDITED, tmp_path, "audit.ov")
    env = res.env
    assert env.objects.kinds == {"Pair.pos": "invariant", "Pair.link": "law",
                                 "Pair.b_pos": "theorem", "Pair.b_big": "lemma",
                                 "Pair.false_one": "theorem"}
    verdicts = {a.title: a.verdict for a in res.classes}
    assert verdicts["theorem Pair.b_pos"] == "PROVEN"
    assert verdicts["theorem Pair.false_one"] == "REFUTED"


def test_audit_counts_kinds_and_ratio(tmp_path: Path) -> None:
    from openverifiers.audit import audit, render
    f = tmp_path / "audit.ov"
    f.write_text(AUDITED)
    rep = audit(f, dag=["Pair.b_big"])
    c = rep.counts()
    assert c == {"foundation": 1, "law": 2, "definition": 2}
    assert [(t.name, t.status) for t in rep.theorems] == [
        ("Pair.b_pos", "PROVEN"), ("Pair.b_big", "PROVEN"), ("Pair.false_one", "REFUTED")]
    assert rep.ratio == 5 / 8
    out = render(rep)
    assert "axiom ratio: 5 / (5 + 3) = 0.62" in out
    assert "REFUTED   Pair.false_one" in out and "not usable as a lemma" in out
    dag = rep.dags["Pair.b_big"]
    names = {k["name"] for k in dag["uses"]}
    assert dag["status"] == "PROVEN" and names <= {"Pair.pos", "Pair.link", "Pair.b_pos"}
    assert "Pair.pos" in names or "Pair.b_pos" in names


def test_audit_cli(capsys: pytest.CaptureFixture[str]) -> None:
    from openverifiers.cli import main as ov
    assert ov(["audit", "math.calculus"]) == 0
    out = capsys.readouterr().out
    assert "polynomial integral and derivative" in out and "UNPROVEN 0" in out
    assert ov(["audit", "no.such.package"]) == 2
    assert ov(["audit"]) == 2


# ---------------------------------------------------------------- the layered library


@pytest.mark.parametrize("pkg", ["math/core.ov", "math/calculus.ov", "physics/mechanics.ov"])
def test_library_packages_prove_every_theorem(pkg: str) -> None:
    f = ROOT / "src/openverifiers/packages" / pkg
    res = run_file(f, files={str(f)})
    assert not res.failed, [a.expect_msg for a in res.failed]
    theorems = [a for a in res.classes if a.kind == "theorem"]
    assert theorems and all(a.verdict == "PROVEN" for a in theorems), \
        [(a.title, a.verdict) for a in theorems if a.verdict != "PROVEN"]


def test_suvat_is_proven_from_the_integral_definitions() -> None:
    from openverifiers.audit import audit
    rep = audit(ROOT / "src/openverifiers/packages/physics/mechanics.ov",
                dag=["ConstantAcceleration.suvat_timeless"])
    d = rep.dags["ConstantAcceleration.suvat_timeless"]
    assert d["status"] == "PROVEN"

    def leaves(x: dict[str, object]) -> set[str]:
        kids = x.get("uses") or []
        assert isinstance(kids, list)
        return {str(x["name"])} if not kids else {n for k in kids for n in leaves(k)}
    assert leaves(d) <= {"ConstantAcceleration.velocity", "ConstantAcceleration.displacement",
                         "ConstantAcceleration.elapsed"}


# ---------------------------------------------------------------- class composition


def test_composition_in_three_domains() -> None:
    """A property typed by a class carries that class's invariants, per instance."""
    f = Path(__file__).parent / "composition.ov"
    res = run_file(f, files={str(f)})
    from openverifiers.objects.engine import show
    pair, mix, refund = res.objects
    assert pair.verdict == "PROVEN" and show(pair.bindings[0]["v"]) == "-4 m/s"     # physics
    assert mix.verdict == "PROVEN" and show(mix.bindings[0]["n"]) == "2 mol"        # chemistry
    assert refund.verdict == "REFUTED" and refund.names == ("Refund.within",)       # agentic
    proven = {a.title for a in res.classes if a.verdict == "PROVEN"}
    assert {"theorem Pair.momentum", "theorem Mixture.total_positive_if_masses",
            "theorem Refund.limit_positive"} <= proven
    # Component invariants are named after the component, so audit does not count
    # them as new definitions of the owner.
    names = [n for n, _ in res.env.objects.defs["Pair"].invariants]
    assert "ConstantAcceleration.velocity@Pair.b1" in names
    assert "ConstantForce.newton2@Pair.b2" in names


def test_component_invariants_are_checked_by_the_evaluator(tmp_path: Path) -> None:
    """A wrong component value is rejected by the trusted evaluator, not the solver."""
    src = (Path(__file__).parent / "composition.ov").read_text()
    src = src.replace("  query FIND ?v WHERE Pair", "  query CHECK Pair{ b1 = ConstantForce{ "
                      "m = 2 kg, u = 0 m/s, v = 4 m/s, a = 2 m/s^2, t = 2 s, s = 4 m, F = 4 N },"
                      " b2 = ConstantForce{ m = 4 kg, u = 0 m/s, v = -2 m/s, a = -1 m/s^2, "
                      "t = 2 s, s = -3 m, F = -4 N } } IS Pair\n  query FIND ?v WHERE Pair", 1)
    res = run(src, tmp_path, "comp.ov")
    check = res.objects[0]
    # Everything holds except b2's displacement (-2 m, not -3 m): the component's own
    # definition, instantiated for b2, catches it.
    assert check.verdict == "REFUTED"
    assert check.names == ("ConstantAcceleration.displacement@Pair.b2",)


# ---------------------------------------------------------------- exact square roots


def test_surd_arithmetic_is_exact() -> None:
    from openverifiers.raw.surd import Surd, SurdError
    r2, r8 = Surd.sqrt(Fraction(2)), Surd.sqrt(Fraction(8))
    assert r8 == Surd.of(Fraction(2)) * r2                       # sqrt 8 = 2 sqrt 2
    assert (r2 * r2).rational() == 2
    assert Surd.sqrt(Fraction(9, 4)).rational() == Fraction(3, 2)
    assert (Surd.sqrt(Fraction(3)) + r2).sign() == 1
    assert (Surd.sqrt(Fraction(3)) - r2 - Surd.of(Fraction(1, 3))).sign() == -1  # -0.0155
    assert (r2 - Surd.of(Fraction(141421, 100000))).sign() == 1                # sqrt 2 > 1.41421
    assert (r2 - Surd.of(Fraction(141422, 100000))).sign() == -1
    assert (r2 - r2).sign() == 0
    with pytest.raises(SurdError):
        Surd.sqrt(Fraction(-1))
    with pytest.raises(SurdError):
        Surd.sqrt(Fraction(1_000_003 * 1_000_033))                # refuses, never guesses


def test_surd_answers_and_distance_sums() -> None:
    f = Path(__file__).parent / "surds.ov"
    res = run_file(f, files={str(f)})
    from openverifiers.objects.engine import show
    count, diag, seg = res.objects
    assert count.count == 2 and sorted(show(b["x"]) for b in count.bindings) == ["-√2", "√2"]
    assert show(diag.bindings[0]["d"]) == "3√2"
    assert seg.verdict == "PROVEN"
    verdicts = {a.title: a.verdict for a in res.classes}
    assert verdicts["theorem Seg.on_segment"] == "PROVEN"


def test_evaluator_rejects_a_wrong_surd() -> None:
    from openverifiers.raw.formula import holds
    d = Compound("f.surd", (n(2), n(3)))                          # 3 sqrt 2
    inv = Compound("f.cmp", (Str("="), p("d"), Compound("*", (Compound("f.sqrt", (n(2),)),
                                                              p("s")))))
    assert holds(inv, {"d": d, "s": n(3)})
    assert not holds(inv, {"d": Compound("f.surd", (n(2), n(4))), "s": n(3)})


# ---------------------------------------------------------------- trigonometry (symbolic)


def test_trig_in_three_domains() -> None:
    """Angle = (cos, sin) with cos^2 + sin^2 = 1; exact at the special angles."""
    f = Path(__file__).parent / "trig.ov"
    res = run_file(f, files={str(f)})
    from openverifiers.objects.engine import show
    given, special, double = res.objects
    assert show(given.bindings[0]["N"]) == "16 N"          # physics, sin 37 = 3/5 given
    assert show(special.bindings[0]["N"]) == "10√3"        # physics, 30 deg exact
    assert show(double.bindings[0]["c"]) == "(-1/2, 1/2√3)"  # math: 2 x 60 deg = 120 deg
    proven = {a.title for a in res.classes if a.verdict == "PROVEN"}
    assert {"theorem Incline.pythagorean_forces", "theorem DoubleAngle.double_cos",
            "theorem DoubleAngle.double_sin", "theorem TriangleAngle.law_of_cosines"} <= proven
    names = [n for n, _ in res.env.objects.defs["Incline"].invariants]
    assert "Angle.unit@Incline.theta" in names              # the foundation axiom


def test_non_special_angles_need_given_values(tmp_path: Path) -> None:
    src = (Path(__file__).parent / "trig.ov").read_text().replace("theta = 30 deg",
                                                                  "theta = 37 deg")
    with pytest.raises(OVError) as e:
        run(src, tmp_path, "trig.ov")
    assert "E405" in e.value.render() and "Angle{ cos = 4/5, sin = 3/5 }" in e.value.render()


# ---------------------------------------------------------------- exp, ln, pi, intervals


def test_interval_functions_enclose_the_true_values() -> None:
    import math

    from openverifiers.raw import interval as I
    one = I.Iv.of(Fraction(1))
    for iv, true in ((I.exp(one), math.e), (I.ln(I.Iv.of(Fraction(2))), math.log(2)),
                     (I.pi(), math.pi),
                     (I.sqrt(I.Iv.of(Fraction(2))), math.sqrt(2)),
                     (I.exp(I.Iv.of(Fraction(-30))), math.exp(-30))):
        assert iv.lo <= Fraction(true) <= iv.hi or abs(float(iv.lo) - true) < 1e-15
        assert iv.hi - iv.lo < Fraction(1, 10**40)
    assert I.ln(I.exp(I.Iv.of(Fraction(3, 7)))).lo <= Fraction(3, 7) <= \
        I.ln(I.exp(I.Iv.of(Fraction(3, 7)))).hi
    with pytest.raises(I.IntervalError):
        I.ln(I.Iv.of(Fraction(0)))
    assert I.decide("<", I.Iv.of(Fraction(1)), I.Iv.of(Fraction(2))) is True
    assert I.decide("=", I.Iv(Fraction(1), Fraction(2)), I.Iv.of(Fraction(3, 2))) is None


def test_numeric_answers_in_three_domains() -> None:
    f = Path(__file__).parent / "transcendental.ov"
    res = run_file(f, files={str(f)})
    decay, half, circ = res.objects
    import math

    from openverifiers.raw.qpi import from_term
    c = next(iter(circ.bindings[0].values()))       # exact in Q(pi) (D-026): 2 pi
    assert circ.verdict == "PROVEN" and circ.trust_base == {"kernel"}
    assert isinstance(c, Compound) and from_term(c.args).num == (Fraction(0), Fraction(2))
    for a, true in ((decay, 1000 * math.exp(-0.5)), (half, math.log(2) / 0.05)):
        assert a.verdict == "PROVEN" and a.trust_base == {"kernel"}
        v = next(iter(a.bindings[0].values()))
        assert isinstance(v, Compound)
        lo, hi = (x.value for x in v.args if isinstance(x, Num))
        assert lo <= Fraction(true) <= hi or abs(float(lo) - true) < 1e-9
    theorems = {a.title: a.verdict for a in res.classes if a.kind == "theorem"}
    assert theorems["theorem Decay.rate_law"] == "PROVEN"      # by differentiating


def test_numeric_check_refuses_unsound_shapes() -> None:
    from openverifiers.raw.numeric import failing_numeric
    iv = Compound("f.iv", (n(1), n(2)))

    def eq(a: Compound | Num, b: Compound | Num) -> Compound:
        return Compound("f.cmp", (Str("="), a, b))
    exp1 = Compound("f.exp", (n(1),))
    one_def = ClassDef("C", ("x",), (("C.d", eq(p("x"), exp1)),), ())
    assert failing_numeric(one_def, {"x": Compound("f.iv", (n(2), n(3)))}) == ()     # e in [2,3]
    assert failing_numeric(one_def, {"x": iv}) == ("C.d",)                         # e not in [1,2]
    two_defs = ClassDef("C", ("x",), (("C.a", eq(p("x"), exp1)), ("C.b", eq(p("x"), n(3)))), ())
    with pytest.raises(Unsupported):            # a second equation on x is not a definition
        failing_numeric(two_defs, {"x": Compound("f.iv", (n(2), n(3)))})
    cyc = ClassDef("C", ("x", "y"), (("C.a", eq(p("x"), p("y"))), ("C.b", eq(p("y"), exp1))), ())
    with pytest.raises(Unsupported):            # x defined from y before y is defined
        failing_numeric(cyc, {"x": iv, "y": iv})


def test_calculus_never_treats_a_non_polynomial_as_constant(tmp_path: Path) -> None:
    """integral(sqrt(t)) treated as sqrt(t) * t would prove a false theorem."""
    res = run("""package probe.bad
fact type Bad {
  property t: Real
  invariant pos: t > 0
  theorem wrong_integral: integral(sqrt(t), t) = sqrt(t) * t
  theorem wrong_derivative: deriv(exp(2 * t), t) = exp(2 * t)
}
""", tmp_path, "bad.ov")
    verdicts = {a.title: a.verdict for a in res.classes if a.kind == "theorem"}
    assert verdicts["theorem Bad.wrong_integral"] != "PROVEN"
    assert verdicts["theorem Bad.wrong_derivative"] != "PROVEN"


def test_tolerance_is_a_real_statement(tmp_path: Path) -> None:
    src = (Path(__file__).parent / "transcendental.ov").read_text().replace(
        "scenario e1 uses probe.exp {", "scenario e1 uses probe.exp {\n  tolerance 0.000001")
    res = run(src, tmp_path, "t.ov")
    assert all(a.verdict == "PROVEN" for a in res.objects)
    assert all(a.plan is not None and a.plan.tolerance == Fraction(1, 10**6)
               for a in res.objects)


def test_audit_checks_definitions_are_conservative(tmp_path: Path) -> None:
    from openverifiers.audit import audit
    f = tmp_path / "defs.ov"
    f.write_text("""package probe.defs
type Thing
predicate p(x: Thing) world closed
predicate q(x: Thing) world closed
predicate r(x: Thing) world closed
definition good(x: Thing): p(x) -> q(x)
definition loop(x: Thing): r(x), p(x) -> r(x)
fact type K {
  property a: Real
  property b: Real
  property c: Real
  invariant pos: a > 0
  invariant b_def: b = 2 * a
  invariant c_one: c = a + 1
  invariant c_two: c = b - 1
  theorem t: b > a
}
""")
    rep = audit(f)
    kinds = {a.name: (a.kind, a.note) for a in rep.axioms}
    assert kinds["good"] == ("definition", "")
    assert kinds["loop"][0] == "axiom" and "recursive" in kinds["loop"][1]
    assert kinds["K.b_def"] == ("definition", "")
    assert "constrains existing symbols" in kinds["K.pos"][1]          # strict reading only
    assert "defined more than once" in kinds["K.c_one"][1]
    # claim ratio: foundation 1 + axiom 1 (loop) over those + 1 theorem
    assert rep.claim_ratio == 2 / 3
    assert rep.strict_claim_ratio > rep.claim_ratio
