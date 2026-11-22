"""One test per checker rejection rule, plus format and builtin edge cases."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from openverifiers.checker import TraceRejected, check_trace, verdict
from openverifiers.kernel import evaluate
from openverifiers.raw import (
    Atom,
    Compare,
    Num,
    Program,
    Rule,
    Span,
    Step,
    Sym,
    Trace,
    Var,
    strata_violations,
    validate,
)
from openverifiers.raw import labels as L
from openverifiers.raw import trace as T
from openverifiers.raw.builtins import compare
from openverifiers.raw.builtins import evaluate as ev
from openverifiers.rawtext import RawSyntaxError, dump, parse, parse_atom, parse_term

PROG = parse("""
world q closed.
fact f1: n(a, 2) @"fact:t".
fact f2: m(b) @"fact:t".
rule s: q(X) :- m(X).
rule r: p(X, Y) :- n(X, V), Y is V * 3, Y > 1, not q(X).
""")
TR = evaluate(PROG)
P_STEP = next(s for s in TR.steps if s.rule_id == "r")


def with_step(tr: Trace, step: Step, at: int | None = None) -> Trace:
    steps = list(tr.steps)
    steps[step.id if at is None else at] = step
    return replace(tr, steps=tuple(steps))


def rejected(tr: Trace, match: str, prog: Program = PROG) -> None:
    with pytest.raises(TraceRejected) as e:
        check_trace(prog, tr)
    assert any(match in r for r in e.value.reasons), e.value.reasons


def test_honest_trace_ok() -> None:
    m = check_trace(PROG, TR)
    assert m.label(parse_atom("p(a, 6)")) == L.TRUE


@pytest.mark.parametrize("change, match", [
    ({"id": 99}, "out of sequence"),
    ({"kind": "guessed"}, "unknown kind"),
    ({"conclusion": Atom("p", (Sym("a"), Var("Y")))}, "not ground"),
    ({"subst": (("V", Num(Fraction(2))), ("X", Sym("a")), ("Y", Num(Fraction(6))),
                ("Z", Sym("a")))}, "bind exactly"),
    ({"subst": (("V", Num(Fraction(2))), ("X", Sym("a")), ("Y", Var("Q")))}, "not ground"),
    ({"naf": ()}, "missing negation reference"),
    ({"naf": (T.NafRef(parse_atom("q(b)"), None),)}, "different atom"),
    ({"naf": (T.NafRef(parse_atom("q(a)"), 0),)}, "not a step of it"),
    ({"subst": (("V", Num(Fraction(2))), ("X", Sym("a")), ("Y", Num(Fraction(7))))},
     "head under"),
    ({"premises": (0, 1)}, "more premises"),
    ({"premises": ()}, "missing premise"),
    ({"premises": (P_STEP.id,)}, "earlier fired step"),
    ({"premises": (1,)}, "different atom"),
    ({"stratum": 0}, "stratum 0"),
])
def test_step_rejections(change: dict[str, object], match: str) -> None:
    rejected(with_step(TR, replace(P_STEP, **change), P_STEP.id), match)  # type: ignore[arg-type]


def test_assign_and_comparison_failures() -> None:
    wrong_assign = replace(PROG, rules=(PROG.rules[0], replace(
        PROG.rules[1], body=(*PROG.rules[1].body[:1],
                             parse("rule z: x :- Y is V * 4.").rules[0].body[0],
                             *PROG.rules[1].body[2:]))))
    rejected(TR, "not the value", wrong_assign)
    wrong_cmp = replace(PROG, rules=(PROG.rules[0], replace(
        PROG.rules[1], body=(*PROG.rules[1].body[:2], Compare(">", Var("Y"), Num(Fraction(9))),
                             PROG.rules[1].body[3]))))
    rejected(TR, "comparison does not hold", wrong_cmp)


def test_fact_step_rejections() -> None:
    f = TR.steps[0]
    rejected(with_step(TR, replace(f, premises=(1,))), "fact step has premises")
    rejected(with_step(TR, replace(f, conclusion=parse_atom("n(a, 3)"))), "not the conclusion")


def test_negation_must_use_final_step_and_complete_stratum() -> None:
    p = parse("""
        world q closed.
        fact a1: q(a) @"assume:x".
        fact a2: q(a) @"assume:y".
        fact d: d(a) @"fact:t".
        rule r: p(X) :- d(X), not q(X).
    """)
    tr = evaluate(p)
    st = next(s for s in tr.steps if s.rule_id == "r")
    first = next(s.id for s in tr.steps if s.rule_id == "a1")
    bad = with_step(tr, replace(st, naf=(T.NafRef(parse_atom("q(a)"), first),),
                                label=L.negate(tr.steps[first].label)))
    rejected(bad, "final step", p)
    rejected(replace(tr, complete=(False, True)), "incomplete stratum", p)


def test_blocked_steps_claim_nothing() -> None:
    blocked = Step(len(TR.steps), "blocked", "r", parse_atom("p(z, 1)"), L.FALSE, 1,
                   reason="missing")
    m = check_trace(PROG, replace(TR, steps=(*TR.steps, blocked)))
    assert parse_atom("p(z, 1)") not in set(m.atoms())


def test_truncated_label_must_be_a_justified_subset() -> None:
    a = parse_atom("p(a, 6)")
    bad = with_step(TR, replace(P_STEP, label=frozenset({frozenset({("zz", True)})})))
    rejected(replace(bad, truncated=frozenset({a})), "truncated label")


def test_strata_claims() -> None:
    rejected(replace(TR, strata=(("m", 0), ("n", 0), ("p", 1))), "no stratum for 'q'")
    rejected(replace(TR, strata=(*[x for x in TR.strata if x[0] != "q"], ("q", 7))),
             "out of range")
    rejected(replace(TR, strata=(*[x for x in TR.strata if x[0] != "q"], ("q", 1))),
             "lower stratum")
    assert strata_violations(PROG, {"p": 0, "n": 1, "q": 0}) != []


def test_invalid_program_is_rejected_by_checker() -> None:
    bad = replace(PROG, rules=(*PROG.rules, Rule("u", parse_atom("w(X)"))))
    rejected(TR, "head variable", bad)


def test_closure_detects_missing_derivation() -> None:
    steps = tuple(s for s in TR.steps if s.rule_id != "r")
    rejected(replace(TR, steps=steps), "closure")


def test_verdict_needs_ground_atom() -> None:
    with pytest.raises(ValueError):
        verdict(check_trace(PROG, TR), parse_atom("p(X, Y)"))


# ---------------------------------------------------------------- trace JSON

def test_trace_json_with_spans_and_errors() -> None:
    p = Program(PROG.worlds, PROG.facts,
                tuple(replace(r, span=Span("x.ov", 3, 1, 3, 9)) for r in PROG.rules))
    tr = evaluate(p)
    blocked = Step(len(tr.steps), "blocked", "r", parse_atom("p(z, 1)"), L.FALSE, 1,
                   reason="missing")
    tr = replace(tr, steps=(*tr.steps, blocked))
    assert T.loads(T.dumps(tr)) == tr
    with pytest.raises(ValueError, match="header"):
        T.loads('{"kind": "step"}')
    with pytest.raises(ValueError):
        T.label_from_json("nope")
    with pytest.raises(ValueError):
        T.label_from_json([[1]])
    for bad in ({"id": True, "stratum": 0}, {"id": 0}, {"id": 0, "stratum": 0, "subst": []},
                {"id": 0, "stratum": 0, "naf": ["x"]}):
        with pytest.raises((ValueError, KeyError)):
            T.step_from_json({"kind": "fired", "rule_id": "r", "conclusion": "p",
                              "label": [], **bad})


# ---------------------------------------------------------------- text

@pytest.mark.parametrize("src, match", [
    ("fact f: p(a) @\"fact:t\" $.", "unexpected character"),
    ("domain d: c(a) = {b} maybe.", "'complete' or 'partial'"),
    ("frob x.", "expected 'world'"),
    ("rule r: p :- 3.", "atom or a comparison"),
    ("rule r: p :- ).", "expected a term"),
    ("fact 3: p @\"fact:t\".", "expected a name"),
    ("fact f: p @\"fact:t\" span(\"f\", 1, 2.5, 3, 4).", "integer"),
    ("fact f: p @fact.", "expected str"),
])
def test_text_errors(src: str, match: str) -> None:
    with pytest.raises(RawSyntaxError, match=match):
        parse(src)


def test_text_misc() -> None:
    p = parse("fact f: p(\"a\\\"b\", 'x y', q) @\"fact:t\" span(\"f.ov\", 1, 2, 3, 4).\n"
              "rule r: z :- p(A, B, C), A != B.")
    assert parse(dump(p)) == p
    with pytest.raises(RawSyntaxError, match="trailing"):
        parse_term("a b")
    with pytest.raises(RawSyntaxError, match="trailing"):
        parse_atom("p(a) q")


def test_validate_more() -> None:
    errs = validate(Program(
        worlds=parse("world p open. world p closed.").worlds,
        facts=parse('fact f: p(a) @"rumour:x".').facts,
        domains=(replace(parse("domain d: c(a) = {a} complete.").domains[0],
                         args=(Var("X"),)),),
        rules=(parse("rule r: p(X) :- p(X), X is 3.").rules[0],
               Rule("s", parse_atom("p(X)"), (parse("rule s: p(X) :- p(X).").rules[0].body[0],
                                              Compare("~", Var("X"), Num(Fraction(3))))))))
    joined = " | ".join(errs)
    for frag in ("more than once", "bad origin", "domain 'd' is not ground",
                 "already bound", "unknown comparison"):
        assert frag in joined


# ---------------------------------------------------------------- builtins

def n(x: str) -> Num:
    return Num(Fraction(x))


@pytest.mark.parametrize("expr, want", [
    ("min(3, 2)", n("2")), ("max(3, 2)", n("3")), ("abs(-4)", n("4")), ("- 4", n("-4")),
    ("2 ^ -1", n("1/2")), ("0 ^ -1", None), ("2 ^ (1/2)", None), ("1{m^1} ^ 1{m^1}", None),
    ("sort_args(a)", None), ("f(1 / 0)", None), ("a + 1", None), ("1{m^1} + 1", None),
    ("min(1{m^1}, 1)", None), ("f(1 + 1, b)", parse_term("f(2, b)")),
])
def test_builtin_eval(expr: str, want: object) -> None:
    assert ev(parse_term(expr), {}) == want


def test_builtin_compare() -> None:
    def c(op: str, a: str, b: str) -> bool:
        return compare(op, parse_term(a), parse_term(b), {})
    assert c("<=", "2", "2") and c(">=", "3", "2") and c(">", "3", "2") and not c(">", "a", "2")
    assert c("=", "f(1+1)", "f(2)") and c("!=", "a", "b") and not c("<", "X", "1")
    assert not c("<", "1 / 0", "1")
