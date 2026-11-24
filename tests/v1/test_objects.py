"""The object layer (brief §3.7): concept classes, invariants, theorems, object queries."""

from __future__ import annotations

import logging
from fractions import Fraction
from pathlib import Path

import pytest
from lark import logger as lark_logger

from openverifiers.lang.check import load
from openverifiers.lang.errors import OVError
from openverifiers.lang.parser import _GRAMMAR
from openverifiers.lower.lower import lower
from openverifiers.objects import engine
from openverifiers.objects.engine import Settings
from openverifiers.objects.solve import Result
from openverifiers.raw.formula import ClassDef, Unsupported, failing, holds
from openverifiers.raw.terms import Compound, Num, Str
from openverifiers.rawtext import dump_term, parse_term
from openverifiers.runner import render, run_file

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = ROOT / "src" / "openverifiers" / "packages" / "math" / "geometry.ov"
SQUARE = ROOT / "examples" / "geometry" / "square.ov"

POINT = "type Point { x: Real, y: Real }\n"


def run(src: str, tmp_path: Path, settings: Settings | None = None):  # type: ignore[no-untyped-def]
    p = tmp_path / "t.ov"
    p.write_text(src)
    return run_file(p, files={str(p)}, settings=settings)


def errors(src: str, tmp_path: Path) -> list[tuple[str, int, int]]:
    p = tmp_path / "e.ov"
    p.write_text(src)
    with pytest.raises(OVError) as e:
        lower(load(p), {str(p)})
    return [(d.code, d.span.line, d.span.col) for d in e.value.diagnostics if not d.warning]


@pytest.fixture(scope="module")
def geometry():  # type: ignore[no-untyped-def]
    return run_file(GEOMETRY, files={str(GEOMETRY)})


def pt(x: int, y: int) -> Compound:
    return Compound("f.tuple", (Num(Fraction(x)), Num(Fraction(y))))


# ---------------------------------------------------------------- the brief's square


def test_square_brief_example() -> None:
    res = run_file(SQUARE, files={str(SQUARE)})
    find, unique = res.objects
    assert find.verdict == "PROVEN" and find.bindings == [{"p": pt(3, 5)}]
    assert unique.verdict == "PROVEN"
    # The trace shows solve -> substitution re-check -> block -> uniqueness unsat (re-solved).
    kinds = [s.split(" ")[0] for s in unique.steps]
    assert kinds == ["solve", "re-check", "block", "solve", "re-solve"]
    assert "every invariant holds" in unique.steps[1]
    assert unique.steps[3].endswith("unsat") and unique.steps[4].endswith("unsat")
    assert not res.failed
    checks = {a.title: a.verdict for a in res.classes}
    assert checks == {"class Quadrilateral is consistent": "PROVEN",
                      "class Square is consistent": "PROVEN",
                      "theorem Square.diagonals_equal": "PROVEN"}
    out = render(res, verbose=True)
    assert "PROVEN  ?p = (3, 5)" in out and "re-solve [z3, fresh solver]" in out


def test_geometry_package_tests_and_theorems(geometry) -> None:  # type: ignore[no-untyped-def]
    res = geometry
    assert len(res.objects) >= 10 and not res.failed
    theorems = [a for a in res.classes if a.title.startswith("theorem")]
    assert len(theorems) >= 6 and all(a.verdict == "PROVEN" for a in theorems)
    assert all(a.verdict == "PROVEN" for a in res.classes if a.title.startswith("class"))
    assert not res.class_errors


def test_symmetry_pruning_never_changes_a_verdict() -> None:
    # Pruning merges the orderings of a cycle that give identical constraints. Without it
    # the solver sees every ordering; it may only run out of time, never disagree.
    env = load(GEOMETRY)
    plans = list(env.objects.plans.values())
    assert len(plans) >= 10
    for plan in plans:
        on = engine.answer(plan, Settings())
        off = engine.answer(plan, Settings(symmetry=False))
        assert (on.verdict, on.bindings, on.names) == (off.verdict, off.bindings, off.names), \
            plan.query.text
    # Class checks: without the symmetry reductions the solver may run out of time (the
    # Square theorem does, even at 60 s), but it must never reach a different verdict.
    on_c = run_file(SQUARE, files={str(SQUARE)}).classes
    off_c = run_file(SQUARE, files={str(SQUARE)},
                     settings=Settings(symmetry=False, timeout_ms=2000)).classes
    for a, b in zip(on_c, off_c, strict=True):
        assert a.title == b.title
        assert a.verdict == b.verdict or (b.verdict, b.reason) == ("UNKNOWN", "budget"), a.title


def test_diamond_includes_shared_invariants_once() -> None:
    env = load(GEOMETRY)
    names = [n for n, _ in env.objects.defs["Square"].invariants]
    assert names == ["Quadrilateral.four", "Quadrilateral.proper", "Parallelogram.bisect",
                     "Rectangle.right", "Rhombus.sides"]      # M078 (packet 4): once each


# ---------------------------------------------------------------- honest outcomes

FALSE_THEOREM = POINT + """
fact type Quadrilateral { property vertices: Set<Point>  invariant four: count(vertices) = 4 }
fact type Parallelogram extends Quadrilateral {
  invariant bisect: exists v in cycles(vertices):
    v[0].x + v[2].x = v[1].x + v[3].x
    v[0].y + v[2].y = v[1].y + v[3].y
  # False: only rectangles have equal diagonals.
  theorem diagonals_equal: none v in cycles(vertices):
    v[0].x + v[2].x = v[1].x + v[3].x
    v[0].y + v[2].y = v[1].y + v[3].y
    dist(v[0], v[2]) != dist(v[1], v[3])
}
scenario s {
  query COUNTEREXAMPLE Parallelogram.diagonals_equal
  expect REFUTED
}
"""


def test_false_theorem_is_refuted_with_a_checked_counterexample(tmp_path: Path) -> None:
    res = run(FALSE_THEOREM, tmp_path)
    (th,) = [a for a in res.classes if a.title.startswith("theorem")]
    assert th.verdict == "REFUTED" and th.witness is not None
    cls = load(tmp_path / "t.ov").objects.defs["Parallelogram"]
    # Independent of the engine: the counterexample is a rhombus and violates the theorem.
    assert failing(cls, th.witness) == ()
    assert not holds(cls.theorems[0][1], th.witness)
    assert res.class_errors == [th]
    ce = res.objects[0]
    assert ce.verdict == "REFUTED" and ce.witness is not None and not res.failed
    assert ce.trust_base == {"kernel"} and th.trust_base == {"kernel"}


def test_inconsistent_class_names_the_conflicting_invariants(tmp_path: Path) -> None:
    src = POINT + """
fact type Odd {
  property vertices: Set<Point>
  invariant three: count(vertices) = 3
  invariant big: exists v in cycles(vertices): dist(v[0], v[1]) > 2
  invariant four: count(vertices) = 4
}
"""
    res = run(src, tmp_path)
    (a,) = res.classes
    assert a.verdict == "INCONSISTENT" and set(a.names) == {"Odd.three", "Odd.four"}


def test_impossible_points_are_refuted_naming_the_invariant(tmp_path: Path) -> None:
    res = run_file(GEOMETRY, files={str(GEOMETRY)})
    a = next(x for x in res.objects if "(2,0), ?p" in x.title)
    assert a.verdict == "REFUTED" and a.names == ("Rhombus.sides",)


def test_under_determined_unique_is_refuted_with_two_witnesses(geometry) -> None:  # type: ignore[no-untyped-def]
    res = geometry
    a = next(x for x in res.objects if "PROVE UNIQUE ?p WHERE Parallelogram" in x.title)
    assert a.verdict == "REFUTED" and len(a.bindings) == 2


def test_unbounded_collection_leaves_theorems_unproven(tmp_path: Path) -> None:
    src = POINT + """
fact type Cloud {
  property points: Set<Point>
  invariant some: count(points) > 0
  theorem nonempty: count(points) >= 1
}
"""
    res = run(src, tmp_path)
    th = next(a for a in res.classes if a.title.startswith("theorem"))
    assert th.verdict == "UNKNOWN" and th.reason == "budget"
    assert "UNPROVEN" in render(res)


def test_irrational_models_are_exact_never_rounded(tmp_path: Path) -> None:
    # No equilateral triangle has rational vertices: z3's model is algebraic. It used to
    # be UNKNOWN; a degree-2 algebraic number is now an exact surd that the evaluator
    # re-checks, so the answer is the exact point, never a rounded one.
    src = POINT + """
fact type Equilateral {
  property vertices: Set<Point>
  invariant three: count(vertices) = 3
  invariant sides: exists v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0
}
scenario s {
  query FIND ?p: Point WHERE Equilateral{ vertices = {(0,0), (2,0), ?p} }
}
"""
    res = run(src, tmp_path)
    from openverifiers.objects.engine import show
    a = res.objects[0]
    assert a.verdict == "PROVEN" and a.complete
    assert sorted(show(b["p"]) for b in a.bindings) == ["(1, -√3)", "(1, √3)"]


def test_buggy_plugin_model_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def wrong(constraints: object, names: list[str], timeout_ms: int = 0,
              seek: bool = False) -> Result:
        return Result("sat", {n: Fraction(7) for n in names})   # (7, 7): not a square vertex
    monkeypatch.setattr(engine, "solve", wrong)
    res = run_file(SQUARE, files={str(SQUARE)})
    find = res.objects[0]
    assert find.verdict == "UNKNOWN" and find.reason == "plugin_unknown" and not find.bindings
    assert any("fails Square.shape" in s for s in find.steps)
    assert all(a.verdict != "PROVEN" for a in res.classes if a.title.startswith("class"))


def test_check_is(geometry) -> None:  # type: ignore[no-untyped-def]
    res = geometry
    checks = {a.title: (a.verdict, a.names) for a in res.objects if "CHECK" in a.title}
    assert ("REFUTED", ("Rhombus.sides",)) in checks.values()
    assert sum(v == "PROVEN" for v, _ in checks.values()) == 3


# ---------------------------------------------------------------- the exact evaluator


def test_evaluator_is_exact() -> None:
    sq = {"vertices": Compound("f.set", (pt(0, 0), pt(1, 0), pt(1, 1), pt(0, 1)))}
    dist = Compound("f.dist", (pt(0, 0), pt(1, 1)))
    def cmp(op: str, a: object, b: object) -> Compound:
        return Compound("f.cmp", (Str(op), a, b))  # type: ignore[arg-type]
    two = Num(Fraction(2))
    # Roots are exact surds now: sqrt 2 * sqrt 2 = 2, exactly (it used to be refused).
    assert holds(cmp("=", Compound("*", (dist, dist)), two), {})
    with pytest.raises(Unsupported):                            # a nested root is refused
        holds(cmp("=", Compound("f.sqrt", (Compound("f.sqrt", (two,)),)), two), {})
    assert holds(cmp(">", dist, Num(Fraction(-1))), {})
    assert holds(cmp("<", dist, Num(Fraction(3, 2))), {})       # sqrt 2 < 1.5
    assert not holds(cmp("<", dist, Num(Fraction(7, 5))), {})    # sqrt 2 > 1.4
    deg = (("deg", Fraction(1)),)
    ang = Compound("f.angle", (pt(1, 0), pt(0, 0), pt(1, 1)))
    assert holds(cmp("=", ang, Num(Fraction(45), deg)), {})
    assert not holds(cmp("=", ang, Num(Fraction(135), deg)), {})
    degenerate = Compound("f.angle", (pt(0, 0), pt(0, 0), pt(1, 1)))
    assert not holds(cmp("=", degenerate, Num(Fraction(90), deg)), {})
    with pytest.raises(Unsupported):
        holds(cmp("=", ang, Num(Fraction(37), deg)), {})
    four = cmp("=", Compound("f.count", (Compound("f.p", (Str("vertices"),)),)),
               Num(Fraction(4)))
    assert failing(ClassDef("Q", ("vertices",), (("Q.four", four),), ()), sq) == ()
    dup = {"vertices": Compound("f.set", (pt(0, 0), pt(0, 0), pt(1, 1), pt(0, 1)))}
    assert failing(ClassDef("Q", ("vertices",), (("Q.four", four),), ()), dup) == ("Q.four",)


def test_class_formulas_round_trip_through_rawov_text() -> None:
    env = load(GEOMETRY)
    for cls in env.objects.defs.values():
        for _, f in (*cls.invariants, *cls.theorems):
            assert parse_term(dump_term(f)) == f


def test_lowering_classes_is_deterministic() -> None:
    a = load(GEOMETRY).objects.defs
    b = load(GEOMETRY).objects.defs
    assert a == b


# ---------------------------------------------------------------- errors


@pytest.mark.parametrize("src, want", [
    (POINT + "fact type T { property v: Set<Point> invariant a: exists w in cycles(v): "
     "angle(w[0], w[1], w[2]) = 37 deg }", [("E405", 2, 74)]),
    (POINT + "fact type T { property v: Set<Point> invariant a: exists w in cycles(v): "
     "dist(w[0], w[1]) = 2 m }", [("E301", 2, 74)]),    # was E405; dist is arithmetic now
    ("fact type A extends B { }\nfact type B extends A { }", [("E406", 2, 1)]),
    ("fact type A extends Nope { }", [("E201", 1, 1)]),
    (POINT + "fact type T { property v: Set<Point> invariant a: exists w in cycles(v): "
     "w[0].z = 1 }", [("E204", 2, 74)]),
    (POINT + "fact type T { property v: Set<Point> invariant a: count(v) = 4 }\n"
     "scenario s { query FIND ?p WHERE Nope{ v = {?p} } }", [("E201", 3, 34)]),
    (POINT + "fact type T { property v: Set<Point> invariant a: count(v) = 4 }\n"
     "scenario s { query PROVE UNIQUE ?p }", [("E206", 3, 20)]),
    (POINT + "fact type T { property v: Set<Point> invariant a: count(v) = 4 }\n"
     "scenario s { query CHECK T{ v = {?p} } IS T }", [("E206", 3, 26)]),
    (POINT + "fact type T { property v: Set<Point> invariant a: foo(v) = 4 }",
     [("E201", 2, 51)]),
])
def test_object_error_codes_and_spans(src: str, want: list[tuple[str, int, int]],
                                      tmp_path: Path) -> None:
    assert errors(src, tmp_path) == want


def test_grammar_conflicts_are_the_documented_ones(caplog: pytest.LogCaptureFixture) -> None:
    # Juxtaposed conditions in a class body make four shift/reduce conflicts, and `->`
    # inside a quantifier a fifth; all resolve as shift (a condition extends as far as it
    # can; an implication binds to the innermost quantifier). docs/LANGUAGE.md lists them.
    from lark import Lark

    from openverifiers.lang.units import unit_regex
    lark_logger.setLevel(logging.DEBUG)
    try:
        with caplog.at_level(logging.DEBUG, logger="lark"):
            Lark(_GRAMMAR.read_text().replace("@UNIT@", unit_regex()), parser="lalr")
    finally:
        lark_logger.setLevel(logging.WARNING)
    found = sorted(r.getMessage().split("terminal ")[1].split(":")[0]
                   for r in caplog.records if "Shift/Reduce" in r.getMessage())
    assert found == ["LBRACE", "LPAR", "LSQB", "MINUS", "__ANON_0"]   # __ANON_0 is "->"
    assert not any("Reduce/Reduce" in r.getMessage() for r in caplog.records)


def test_evaluator_generators_and_rejections() -> None:
    def c(f: str, *a: object) -> Compound:
        return Compound(f, a)  # type: ignore[arg-type]

    def n(x: int) -> Num:
        return Num(Fraction(x))
    s = c("f.set", pt(0, 0), pt(1, 0), pt(0, 1))
    p = c("f.p", Str("s"))
    props = {"s": s}
    v = c("f.v", Str("v"))
    # orderings, subsets, pairs, plain collections, or/not/forall
    assert holds(c("f.exists", Str("v"), c("f.orderings", p),
                   c("f.cmp", Str("="), c("f.idx", v, n(0)), pt(1, 0))), props)
    assert holds(c("f.forall", Str("v"), c("f.subsets", p, n(2)),
                   c("f.cmp", Str("="), c("f.count", v), n(2))), props)
    assert holds(c("f.forall", Str("v"), c("f.pairs", p),
                   c("f.cmp", Str(">"), c("f.dist", c("f.at", v, n(0)), c("f.at", v, n(1))),
                     n(0))), props)
    assert holds(c("f.or", c("f.not", c("f.cmp", Str("="), n(1), n(1))),
                   c("f.forall", Str("v"), p, c("f.cmp", Str(">="), c("f.at", v, n(0)), n(0)))),
                 props)
    assert holds(c("f.cmp", Str("!="), c("f.list", n(1)), c("f.list", n(2))), {})
    assert holds(c("f.cmp", Str("="), c("abs", n(-2)), n(2)), {})
    assert holds(c("f.cmp", Str("<"), n(1), c("f.dist", pt(0, 0), pt(3, 4))), {})
    assert holds(c("f.cmp", Str("="), c("f.dist2", pt(0, 0), pt(3, 4)), n(25)), {})
    assert holds(c("f.cmp", Str("<"), c("f.dist", pt(0, 0), pt(1, 0)),
                   c("f.dist", pt(0, 0), pt(2, 0))), {})
    assert not holds(c("f.cmp", Str("="), c("f.dist", pt(0, 0), pt(1, 0)), n(-1)), {})
    deg = (("deg", Fraction(1)),)
    ang = c("f.angle", pt(1, 0), pt(0, 0), pt(-1, 0))
    assert holds(c("f.cmp", Str("!="), ang, Num(Fraction(90), deg)), {})
    assert holds(c("f.cmp", Str("="), Num(Fraction(180), deg), ang), {})
    bad = [
        c("f.cmp", Str("="), c("f.v", Str("nope")), n(1)),               # unbound
        c("f.cmp", Str("="), c("f.at", pt(0, 0), n(5)), n(1)),            # component index
        c("f.cmp", Str("="), c("f.idx", c("f.list"), n(0)), n(1)),        # empty list
        c("f.cmp", Str("="), c("f.idx", c("f.list", n(1)), Str("x")), n(1)),
        c("f.cmp", Str("="), c("f.count", n(1)), n(1)),                   # not a collection
        c("f.cmp", Str("="), c("f.dist", n(1), pt(0, 0)), n(1)),          # not a point
        c("f.cmp", Str("="), c("f.dist", pt(0, 0), c("f.tuple", n(1), n(2), n(3))), n(1)),
        c("f.cmp", Str("="), c("f.set", c("f.angle", pt(0, 0), pt(1, 1), pt(1, 0))), n(1)),
        c("f.cmp", Str("="), c("+", n(1), Num(Fraction(1), deg)), n(1)),  # arithmetic fails
        c("f.cmp", Str("="), c("foo", n(1)), n(1)),
        c("f.cmp", Str("<"), c("f.dist", pt(0, 0), pt(1, 0)), Num(Fraction(1), deg)),
        c("f.cmp", Str("<"), ang, Num(Fraction(90), deg)),
        c("f.cmp", Str("="), n(1), Num(Fraction(1), deg)),
        c("f.cmp", Str("<"), pt(0, 0), pt(1, 1)),
        c("f.cmp", Str("~"), n(1), n(1)),
        c("f.exists", Str("v"), c("f.subsets", p, Str("k")), c("f.cmp", Str("="), n(1), n(1))),
        c("f.exists", Str("v"), c("f.nope", p), c("f.cmp", Str("="), n(1), n(1))),
        c("f.what"), Str("x"), Str("y"),
    ]
    for f in bad:
        with pytest.raises(Unsupported):
            holds(f, props)   # type: ignore[arg-type]
    with pytest.raises(Unsupported):
        failing(ClassDef("C", ("a",), (), ()), props)
    from openverifiers.raw.formula import generate
    with pytest.raises(Unsupported):
        list(generate("f.nope", ()))
    # a bound variable shadowing an outer one is restored afterwards
    inner = c("f.exists", Str("v"), p, c("f.cmp", Str("="), v, v))
    assert holds(c("f.exists", Str("v"), p, c("f.and", inner, c("f.cmp", Str("="), v, v))),
                 props)


RHOMBUS_FALSE = POINT + """
fact type Quadrilateral { property vertices: Set<Point>  invariant four: count(vertices) = 4 }
fact type Rhombus extends Quadrilateral {
  invariant sides: exists v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0
  # False: only squares have equal diagonals. (0,0), (2,1), (3,3), (1,2) is a rational
  # counterexample (sides sqrt 5, diagonals sqrt 18 and sqrt 2).
  theorem diagonals_equal: none v in cycles(vertices):
    all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0
    dist(v[0], v[2]) != dist(v[1], v[3])
}
"""


def test_rhombus_false_theorem(tmp_path: Path) -> None:
    # History: z3 alone gave UNKNOWN(budget), then (with translation pinning) irrational
    # models, UNKNOWN(plugin_unknown). The small-scope pass finds an integer
    # counterexample, so the theorem is now REFUTED, and the trusted evaluator agrees.
    res = run(RHOMBUS_FALSE, tmp_path, Settings(timeout_ms=3000))
    (th,) = [a for a in res.classes if a.title.startswith("theorem")]
    assert th.verdict == "REFUTED" and th.witness is not None
    cls = load(tmp_path / "t.ov").objects.defs["Rhombus"]
    assert failing(cls, th.witness) == () and not holds(cls.theorems[0][1], th.witness)



def test_derived_is_rejected_until_supported(tmp_path: Path) -> None:
    src = POINT + "fact type T { property a: Real  derived b: Real = a * 2 }"
    assert errors(src, tmp_path) == [("E207", 2, 33)]


def test_vacuous_theorem_warning(tmp_path: Path) -> None:
    src = POINT + """
fact type Q { property vertices: Set<Point>  invariant four: count(vertices) = 4 }
fact type S extends Q {
  invariant shape: exists v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0
  theorem t: exists v in cycles(vertices): dist(v[0], v[2]) = dist(v[1], v[3])
}
"""
    p = tmp_path / "t.ov"
    p.write_text(src)
    assert [(w.code, w.span.line) for w in load(p).warnings] == [("W202", 6)]
    assert not load(SQUARE).warnings      # the rewritten brief theorem is not vacuous


def test_implication_compiles_to_or_not() -> None:
    env = load(SQUARE)
    th = env.objects.defs["Square"].theorems[0][1]
    assert isinstance(th, Compound) and th.functor == "f.forall"
    body = th.args[2]
    assert isinstance(body, Compound) and body.functor == "f.or"
    assert isinstance(body.args[0], Compound) and body.args[0].functor == "f.not"


def test_trust_base_and_strict() -> None:
    res = run_file(SQUARE, files={str(SQUARE)})
    find, unique = res.objects
    assert find.trust_base == {"kernel"} and find.complete
    assert unique.trust_base == {"kernel", "z3_unsat"}
    th = res.classes[-1]
    # Condition A: the reductions the unsat was computed under are listed too.
    assert th.verdict == "PROVEN" and th.trust_base == {
        "z3_unsat", "red:fix_order", "red:no_invariants", "red:translate"}
    strict = run_file(SQUARE, files={str(SQUARE)}, settings=Settings(strict=True))
    s_find, s_unique = strict.objects
    assert s_find.verdict == "PROVEN" and not s_find.complete     # bindings are kernel-checked
    assert (s_unique.verdict, s_unique.reason) == ("UNKNOWN", "plugin_unknown")
    s_th = strict.classes[-1]
    assert (s_th.verdict, s_th.reason, s_th.trust_base) == ("UNKNOWN", "plugin_unknown",
                                                             frozenset())
    assert strict.classes[1].verdict == "PROVEN"                  # a re-checked witness


def test_small_scope_never_runs_on_a_successful_proof(geometry) -> None:  # type: ignore[no-untyped-def]
    """Small-scope search is for things that may exist (FIND, consistency,
    COUNTEREXAMPLE). A theorem check tries z3 first and falls back to it only when
    z3 neither proves nor refutes."""
    proven = [a for a in geometry.classes if a.kind == "theorem" and a.verdict == "PROVEN"]
    assert proven
    for a in proven:
        assert not any("small-scope" in s for s in a.steps), a.title
    finds = [a for a in geometry.objects if a.kind == "find" and a.bindings]
    assert any(any("small-scope" in s for s in a.steps) for a in finds)


def test_trust_base_lists_the_reductions() -> None:
    on = run_file(SQUARE, files={str(SQUARE)}).classes
    th = next(a for a in on if a.kind == "theorem")
    assert th.verdict == "PROVEN"
    assert {"z3_unsat", "red:fix_order", "red:translate"} <= th.trust_base
    # Kernel-checked answers (consistency witnesses) list no reductions.
    assert all(not any(t.startswith("red:") for t in a.trust_base)
               for a in on if a.kind == "consistency")
    strict = run_file(SQUARE, files={str(SQUARE)}, settings=Settings(strict=True)).classes
    assert next(a for a in strict if a.kind == "theorem").verdict == "UNKNOWN"


def test_inherited_theorem_lists_inherit_and_the_ancestor_reductions(geometry) -> None:  # type: ignore[no-untyped-def]
    inherited = [a for a in geometry.classes if any(s.startswith("inherited") for s in a.steps)]
    assert inherited
    for a in inherited:
        assert "red:inherit" in a.trust_base and "z3_unsat" in a.trust_base


def test_no_reductions_flag_turns_every_reduction_off(tmp_path: Path) -> None:
    from openverifiers.bench.reductions import case
    for seed in range(4):
        p = tmp_path / f"c{seed}.ov"
        p.write_text(case(seed))
        res = run_file(p, files={str(p)}, settings=Settings(reductions=False))
        for a in res.classes:
            assert not a.reductions and not any(t.startswith("red:") for t in a.trust_base)
            assert not any(s.startswith(("symmetry:", "implied", "inherited")) for s in a.steps)


def test_reductions_never_change_a_definite_verdict(tmp_path: Path) -> None:
    """Condition A, a fixed-seed sample. The full run is
    `python -m openverifiers.bench.reductions` (reported in the step-2 report)."""
    from openverifiers.bench.reductions import run_case
    checks = 0
    for seed in range(10):
        out = run_case(seed, on_ms=3_000, off_ms=10_000, workdir=tmp_path)
        assert not isinstance(out, str), out
        checks += len(out)
        assert not [o for o in out if o.conflict], out
    assert checks >= 30
