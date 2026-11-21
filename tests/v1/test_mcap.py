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
    assert ev(Compound("f.integral", (a, Str("t"))), a=2, t=3).value == 6
    # integral(u + integral(a, t), t) = u t + a t^2 / 2 = 4*3 + 9 = 21
    inner = Compound("f.integral", (a, Str("t")))
    outer = Compound("f.integral", (Compound("+", (u, inner)), Str("t")))
    assert ev(outer, a=2, t=3, u=4).value == 21
    # deriv(t^3, t) at t = 5: 75; deriv(7, t) = 0
    cube = Compound("*", (t, Compound("*", (t, t))))
    assert ev(Compound("f.deriv", (cube, Str("t"))), t=5).value == 75
    assert ev(Compound("f.deriv", (n(7), Str("t"))), t=5).value == 0
    # fractions stay exact: integral(t^2) at 1/2 = 1/24
    sq = Compound("*", (t, t))
    v = _Eval({"t": Num(Fraction(1, 2))}).expr(Compound("f.integral", (sq, Str("t"))))
    assert isinstance(v, Num) and v.value == Fraction(1, 24)


def test_calculus_rejects_what_is_not_a_polynomial_in_the_variable() -> None:
    t = p("t")
    for body in (Compound("/", (n(1), t)), Compound("abs", (t,)),
                 Compound("f.dist", (Compound("f.tuple", (t, t)), Compound("f.tuple", (t, t))))):
        with pytest.raises(Unsupported):
            ev(Compound("f.integral", (body, Str("t"))), t=2)


def test_coefficients_recover_the_polynomial() -> None:
    # y = 1 + 2 i - 3 i^2 + i^3 sampled at i = 0..3
    ys = [Fraction(1 + 2 * i - 3 * i * i + i ** 3) for i in range(4)]
    assert _coefficients(ys) == [1, 2, -3, 1]


def test_checker_rejects_a_wrong_displacement() -> None:
    a, u = p("a"), p("u")
    s = Compound("f.integral", (Compound("+", (u, Compound("f.integral", (a, Str("t"))))),
                                Str("t")))
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
