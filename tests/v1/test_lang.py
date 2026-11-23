"""The OV front end: parsing, every error code with its exact span, lowering."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.checker import Refuted
from openverifiers.lang import ast as A
from openverifiers.lang.check import load
from openverifiers.lang.errors import OVError
from openverifiers.lang.parser import parse
from openverifiers.lang.units import parse_unit, show_quantity
from openverifiers.lower.lower import lower
from openverifiers.raw import Num
from openverifiers.rawtext import dump
from openverifiers.rawtext import parse as raw_parse
from openverifiers.runner import main, render, run_file

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "src" / "openverifiers" / "packages"

MECH = """package m @0.1
type Body { mass: Mass, accel: Accel }
type Cart extends Body { length: Length }
predicate net_force(b: Body, F: Force) world open
axiom newton2(b: Body, F: Force): net_force(b, F) -> F = b.mass * b.accel
"""


def run(src: str, tmp_path: Path, name: str = "t.ov"):  # type: ignore[no-untyped-def]
    p = tmp_path / name
    p.write_text(src)
    return run_file(p, files={str(p)})


def verdicts(src: str, tmp_path: Path) -> list[str]:
    return [a.verdict for a in run(src, tmp_path).answers]


def errors(src: str, tmp_path: Path) -> list[tuple[str, int, int]]:
    p = tmp_path / "e.ov"
    p.write_text(src)
    with pytest.raises(OVError) as e:
        lower(load(p), {str(p)})
    return [(d.code, d.span.line, d.span.col) for d in e.value.diagnostics if not d.warning]


# ---------------------------------------------------------------- parsing


def test_brief_examples_parse() -> None:
    for f in ("examples/physics/newton2.ov", "examples/chem/q11.ov"):
        mod = parse((ROOT / f).read_text(), f)
        assert mod.items


def test_tokens() -> None:
    m = parse("scenario s { fact p(2-chloropentane, 1,1-dimethylcyclopropane, pent-1-ene,"
              " 10 N, 2 m/s^2, 0.5 kg, x - y, \"text\") }")
    sc = m.items[0]
    assert isinstance(sc, A.Scenario)
    st = sc.stmts[0]
    assert isinstance(st, A.FactStmt) and isinstance(st.lit, A.Holds)
    call = st.lit.expr
    assert isinstance(call, A.Call)
    names = [a.name for a in call.args if isinstance(a, A.Name)]
    assert names == ["2-chloropentane", "1,1-dimethylcyclopropane", "pent-1-ene"]
    qs = [a for a in call.args if isinstance(a, A.Quantity)]
    assert [q.value for q in qs] == [10, 2, Fraction(1, 2)]
    assert isinstance(call.args[6], A.BinOp) and isinstance(call.args[7], A.StrLit)


def test_units() -> None:
    assert parse_unit("km/h") == (Fraction(1000, 3600), parse_unit("m/s")[1])  # type: ignore[index]
    assert parse_unit("furlong") is None
    assert show_quantity(Fraction(5), parse_unit("kg")[1]) == "5 kg"  # type: ignore[index]
    assert show_quantity(Fraction(1, 3), ()) == "1/3"


def test_query_text_and_expect() -> None:
    m = parse("scenario s { query FIND ?x WHERE p(?x) expect UNKNOWN assuming {} }")
    sc = m.items[0]
    assert isinstance(sc, A.Scenario)
    q, ex = sc.stmts
    assert isinstance(q, A.Query) and q.text == "FIND ?x WHERE p(?x)"
    assert isinstance(ex, A.Expect) and ex.assuming == ()


# ---------------------------------------------------------------- error codes and spans


@pytest.mark.parametrize("src, want", [
    ("scenario s { fact p(a) b }", [("E101", 1, 24)]),
    ("scenario s { fact p(a) $ }", [("E102", 1, 24)]),
    ("scenario s { fact p(3 furlong) }", [("E103", 1, 23)]),
    ("scenario s { fact frob(a) }", [("E201", 1, 19)]),
    ("scenario s { entity a: T  entity a: T }", [("E202", 1, 27)]),
    ("import nowhere.at_all", [("E203", 1, 1)]),
    (MECH + "test x { scenario s uses m { entity c: Body  fact c.colour = 2 } }",
     [("E204", 6, 51)]),
    (MECH + "test x { scenario s uses m { entity c: Body  fact net_force(c) } }",
     [("E205", 6, 51)]),
    (MECH + "test x { scenario s uses m { entity c: Body  fact c.mass = 2 kg + 1 m } }",
     [("E301", 6, 60)]),
    (MECH + "test x { scenario s uses m { entity c: Body  fact net_force(c, c) } }",
     [("E302", 6, 64)]),
    (MECH + "test x { scenario s uses m { entity c: Body  fact c < c } }",
     [("E303", 6, 51), ("E303", 6, 55)]),
    ("package p\npredicate q(x: Number) world open\naxiom a(x: Number): q(x) -> x = 1",
     [("E401", 3, 29)]),
    ("package p\ntype B { v: Number }\npredicate q(b: B) world open\n"
     "axiom a(b: B): q(b) -> b.v ^ 2 = 4", [("E402", 4, 24)]),
    ("package p\npredicate q(x: Number) world closed\npredicate r(x: Number) world open\n"
     "axiom a(x: Number): not q(x) -> r(x)", [("E403", 4, 1), ("E403", 4, 1)]),
    ("package p\npredicate q(x: Number) -> {Number} world open\n"
     "generator g(x: Number) yields Number from q(x)", [("E404", 3, 43)]),
    ("import state \"x.ovs\" as old", [("E203", 1, 1)]),
    ("scenario s {\n  tolerance 2\n}", [("E206", 2, 3)]),      # was E207: tolerance is real now
    ("predicate q(x: Number) world open\naxiom a(x: Number): q(x) -> q(x)", [("E206", 2, 1)]),
])
def test_error_codes_and_spans(src: str, want: list[tuple[str, int, int]],
                               tmp_path: Path) -> None:
    assert errors(src, tmp_path) == want


def test_error_rendering_has_caret_and_hint(tmp_path: Path) -> None:
    p = tmp_path / "e.ov"
    p.write_text(MECH + "test x { scenario s uses m { entity c: Body  fact c.mass = 2 kg + 1 m } }")
    with pytest.raises(OVError) as e:
        load(p)
    text = e.value.render()
    assert "e.ov:6:60: error[E301]: cannot add Mass and Length" in text
    assert "^^^^^^^^^^" in text and "hint:" in text


def test_hyphen_hint(tmp_path: Path) -> None:
    p = tmp_path / "e.ov"
    p.write_text("type T\npredicate p(x: T) world open\nscenario s { entity a, b: T  fact p(a-b) }")
    with pytest.raises(OVError) as e:
        load(p)
    assert "write `a - b`" in e.value.render()


def test_undeclared_type_is_a_warning(tmp_path: Path) -> None:
    res = run("package p\npredicate f(s: Surface) world open\n", tmp_path)
    assert [w.code for w in res.env.warnings] == ["W201"]


# ---------------------------------------------------------------- lowering


def test_lowering_is_deterministic_and_round_trips() -> None:
    for f in ("examples/chem/q11.ov", "examples/physics/newton2.ov"):
        a, b = lower(load(ROOT / f)), lower(load(ROOT / f))
        assert [x.program for x in a] == [x.program for x in b]
        for x in a:
            assert raw_parse(dump(x.program)) == x.program
            assert all(r.span is not None for r in x.program.rules)


def test_equation_solves_every_direction(tmp_path: Path) -> None:
    src = MECH + """test t {
  scenario s uses m {
    entity c: Body
    fact net_force(c, 10 N)
    fact c.mass = 4 kg
  }
  query FIND ?a WHERE s.c.accel = ?a
  expect PROVEN 2.5 m/s^2
}"""
    res = run(src, tmp_path)
    assert not res.failed and res.answers[0].verdict == "PROVEN"


def test_conflicting_values_are_inconsistent(tmp_path: Path) -> None:
    src = MECH + """scenario s uses m {
  entity c: Body
  fact net_force(c, 10 N)
  fact c.accel = 2 m/s^2
  fact c.mass = 4 kg
  query PROVE net_force(c, 10 N)
  expect INCONSISTENT
}"""
    res = run(src, tmp_path)
    assert not res.failed, render(res)


def test_inherited_fields(tmp_path: Path) -> None:
    src = MECH + """scenario s uses m {
  entity c: Cart
  fact net_force(c, 6 N)
  fact c.accel = 3 m/s^2
  fact c.length = 2 m
  query FIND ?m WHERE c.mass = ?m
  expect PROVEN 2 kg
}"""
    assert not run(src, tmp_path).failed


def test_open_and_closed_world(tmp_path: Path) -> None:
    src = """package w
type T
predicate seen(x: T) world closed
predicate rumour(x: T) world open
scenario s uses w {
  entity a, b: T
  fact seen(a)
  fact not rumour(b)
  query PROVE seen(b)
  expect REFUTED
  query PROVE rumour(a)
  expect UNKNOWN
  query PROVE rumour(b)
  expect REFUTED
}"""
    res = run(src, tmp_path)
    assert not res.failed, render(res)
    first = res.answers[0].detail
    assert isinstance(first, Refuted) and first.closed_world


def test_inequality_fact_is_a_check(tmp_path: Path) -> None:
    src = MECH + """scenario s uses m {
  entity c: Body
  fact c.mass = 2 kg
  fact c.mass > 3 kg
  query PROVE net_force(c, 1 N)
  expect INCONSISTENT
}"""
    assert not run(src, tmp_path).failed


def test_unknown_value_states_nothing(tmp_path: Path) -> None:
    src = MECH + """scenario s uses m {
  entity c: Body
  fact c.mass = unknown
  query FIND ?m WHERE c.mass = ?m
  expect UNKNOWN
}"""
    assert not run(src, tmp_path).failed


def test_intervals_and_metadata(tmp_path: Path) -> None:
    src = """package iv
type T
predicate ok(x: T) world open
predicate temp(x: T) -> Temperature world open
axiom in_range(x: T, k: Temperature): temp(x) = k, k in [270 K, 300 K] -> ok(x)
scenario s uses iv {
  entity a, b: T
  fact temp(a) = 280 K confidence 0.9 source "sensor 1"
  fact temp(b) = 350 K
  query PROVE ok(a)
  expect PROVEN
  query PROVE ok(b)
  expect UNKNOWN
}"""
    res = run(src, tmp_path)
    assert not res.failed, render(res)
    assert (Fraction(9, 10), "sensor 1") in res.lowered[0].meta.values()


def test_generators_and_candidates(tmp_path: Path) -> None:
    src = """package g
type Card
type Colour
entity red, black: Colour
entity ah, ks, qd: Card
predicate deck(x: Colour) -> {Card} world closed
predicate colour(c: Card) -> Colour world closed
predicate face(c: Card) world closed
axiom cards: deck(red) = {ah, qd}, deck(black) = {ks}
axiom colours: colour(ah) = red, colour(qd) = red, colour(ks) = black
axiom faces: face(ks), face(qd)
generator drawn(x: Colour) yields Card from deck(x)
scenario one uses g {
  generator X from drawn(red)
  fact face(X)
  query FIND ?X
  expect PROVEN qd
}
scenario two uses g {
  generator X from drawn(red)
  query FIND ?X
  expect UNKNOWN ah, qd
}
scenario none uses g {
  generator X from drawn(black)
  fact not face(X)
  query FIND ?X
  expect INCONSISTENT
}"""
    res = run(src, tmp_path)
    assert not res.failed, render(res)


def test_assumption_what_if_is_lookup(tmp_path: Path) -> None:
    src = """package a
type T
predicate warm(x: T) world open
predicate melts(x: T) world open
axiom m(x: T): warm(x) -> melts(x)
scenario s uses a {
  entity ice: T
  assume sunny: warm(ice)
  query PROVE melts(ice)
  expect PROVEN assuming {sunny}
  query WHAT IF RETRACT warm(ice) THEN PROVE melts(ice)
  expect UNKNOWN
}"""
    res = run(src, tmp_path)
    assert not res.failed, render(res)
    assert res.answers[1].plan.retract_assumptions == {"sunny"}
    assert not res.answers[1].plan.retract_items


def test_scenario_extends_and_controller_guard(tmp_path: Path) -> None:
    src = """package c
type T
predicate raw(x: T) world open
predicate cooked(x: T) world open
predicate allowed(x: T) world open
transformation cook(x: T) requires raw(x) ensures cooked(x)
controller kitchen(x: T) { pipe cook guard allowed(x) }
scenario base uses c {
  entity egg, ham: T
  fact raw(egg)
  fact raw(ham)
}
scenario more extends base {
  fact allowed(egg)
  query PROVE cooked(egg)
  expect PROVEN
  query PROVE cooked(ham)
  expect UNKNOWN
}"""
    res = run(src, tmp_path)
    assert not res.failed, render(res)


def test_failed_expectation_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]
                                        ) -> None:
    p = tmp_path / "f.ov"
    p.write_text(MECH + """test t { scenario s uses m { entity c: Body
      fact net_force(c, 10 N)  fact c.accel = 2 m/s^2 }
  query FIND ?m WHERE s.c.mass = ?m
  expect PROVEN 6 kg }""")
    assert main([str(p)]) == 1
    assert "FAILED (got values 5 kg)" in capsys.readouterr().out


def test_metamorphic_renaming_and_reordering(tmp_path: Path) -> None:
    base = (ROOT / "examples/chem/q11.ov").read_text()
    lines = base.splitlines()
    facts = [i for i, ln in enumerate(lines) if ln.strip().startswith("fact")]
    swapped = list(lines)
    swapped[facts[1]], swapped[facts[2]] = lines[facts[2]], lines[facts[1]]
    renamed = base.replace("q11", "renamed")
    want = verdicts(base, tmp_path)
    assert verdicts("\n".join(swapped), tmp_path) == want
    assert verdicts(renamed, tmp_path) == want
    extra = base.replace("  query FIND ?A, ?C, ?D",
                         "  fact markov(HBr, none)\n  query FIND ?A, ?C, ?D")
    assert verdicts(extra, tmp_path) == want


# ---------------------------------------------------------------- the brief's examples


def test_physics_example_runs_exactly() -> None:
    res = run_file(ROOT / "examples/physics/newton2.ov",
                   files={str(ROOT / "examples/physics/newton2.ov")})
    (a,) = res.answers
    assert a.verdict == "PROVEN" and a.expect_ok
    assert a.bindings[0][0]["m"] == Num(Fraction(5), parse_unit("kg")[1])  # type: ignore[index]


def test_q11_example_answers() -> None:
    res = run_file(ROOT / "examples/chem/q11.ov")
    lw = res.lowered[0]

    def show(t: object) -> str:
        return str(lw.names.get(t, t))  # type: ignore[call-overload]

    a1, a2, a3, a4 = res.answers
    ((b1, _),) = a1.bindings
    assert (show(b1["A"]), show(b1["C"]), show(b1["D"])) == (
        "2-methylbut-1-ene", "butanone", "methanal")
    assert a1.assumptions == frozenset()
    ((b2, _),) = a2.bindings
    assert show(b2["p"]) == "1-bromopentane"
    assert a2.assumptions == frozenset({("single_major", True)})
    assert a3.verdict == "REFUTED"
    assert a4.verdict == "UNKNOWN" and a4.detail.reason == "missing_facts"  # type: ignore[union-attr]
    assert sorted(show(t) for t in a4.candidates["A"]) == ["2-methylbut-1-ene",
                                                           "2-methylbut-2-ene"]


@pytest.mark.parametrize("pkg", sorted(str(p.relative_to(PKG)) for p in PKG.rglob("*.ov")))
def test_package_tests_pass(pkg: str) -> None:
    path = PKG / pkg
    res = run_file(path, files={str(path)})
    assert not res.failed, render(res)


def test_strict_makes_undeclared_types_errors(tmp_path: Path) -> None:
    from openverifiers.objects.engine import Settings
    p = tmp_path / "t.ov"
    p.write_text("package p\npredicate f(s: Surface) world open\n")
    with pytest.raises(OVError) as e:
        run_file(p, files={str(p)}, settings=Settings(strict=True))
    assert [d.code for d in e.value.diagnostics] == ["E208"]


def test_ov_cli(capsys: pytest.CaptureFixture[str]) -> None:
    from openverifiers.cli import main as ov
    assert ov(["run", str(ROOT / "examples/physics/newton2.ov")]) == 0
    out = capsys.readouterr().out
    assert "PROVEN  m = 5 kg  assumptions {}  trust {kernel}" in out
    assert ov(["check", str(ROOT / "examples/physics/newton2.ov")]) == 0
    assert "newton2.ov: ok (1 scenario(s), 1 queries, 1/1 expectations" in capsys.readouterr().out
    bad = ROOT / "tests/v1/_bad_expect.ov"
    src = (ROOT / "examples/physics/newton2.ov").read_text()
    src = src.replace("expect", "expect REFUTED #", 1)
    bad.write_text(src)
    try:
        assert ov(["check", str(bad)]) == 1
        assert ": FAIL (" in capsys.readouterr().out
    finally:
        bad.unlink()
    assert ov(["frobnicate"]) == 2
    assert ov([]) == 2
    assert ov(["--help"]) == 0


def test_what_if_retract_uses_labels_not_a_rerun() -> None:
    """A retracted fact is lowered as a hidden, default-active assumption, so WHAT IF
    RETRACT is a context change (no second evaluation), and the hidden name is never
    shown as an assumption of an answer."""
    from openverifiers.runner import render, run_file
    res = run_file(ROOT / "examples/chem/q11.ov")
    plans = [q for lw in res.lowered for q in lw.queries]
    assert all(not q.retract_items for q in plans)
    [hidden] = [n for q in plans for n in q.retract_assumptions]
    assert hidden.startswith("fact#")
    out = render(res)
    assert "fact#" not in out
    assert "A in {2-methylbut-1-ene, 2-methylbut-2-ene}" in out
    assert "PROVEN  p = 1-bromopentane  assumptions {single_major}" in out


def test_missing_assumption_is_shown_as_its_statement() -> None:
    from openverifiers.runner import render, run_file
    p = ROOT / "benchmarks/agentic/deploy_checklist/case.ov"
    out = render(run_file(p, files={str(p)}))
    assert "missing: assume reviewed_ok" not in out
    assert "missing: assume review_signed: reviewed(v2)" in out
