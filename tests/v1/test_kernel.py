"""Evaluator + verdicts: world policies, labels, negation, inconsistency, budgets."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings

from openverifiers.checker import Inconsistent, Proven, Refuted, Unknown, verdict
from openverifiers.engine import Run, ask, run, without
from openverifiers.kernel import Budget, InvalidProgram, NotStratifiable, evaluate
from openverifiers.raw import Atom, Program, Sym
from openverifiers.rawtext import parse, parse_atom

from .programs import PENGUIN, REACH, programs


def v(r: Run, atom: str, context: frozenset[str] | None = None) -> object:
    return ask(r, parse_atom(atom), context)


def kind(x: object) -> str:
    return type(x).__name__


# ---------------------------------------------------------------- basics

def test_transitive_closure_with_assumption_labels() -> None:
    r = run(REACH)
    assert isinstance(p := v(r, "reach(a, c)"), Proven) and p.assumptions == frozenset()
    d = v(r, "reach(a, d)")
    assert isinstance(d, Proven) and d.assumptions == {("h", True)}
    # without h the edge c->d is gone; reach is closed-world, so REFUTED
    assert isinstance(v(r, "reach(a, d)", frozenset()), Refuted)


def test_closed_world_negation_gets_negative_label() -> None:
    r = run(REACH)
    un = v(r, "unreach(a, d)", frozenset())
    assert isinstance(un, Proven) and un.assumptions == {("h", False)}
    # unreach is open world: with h active nothing says either way
    assert kind(v(r, "unreach(a, d)")) == "Unknown"


def test_open_world_unknown_vs_closed_world_refuted() -> None:
    r = run(PENGUIN)
    assert isinstance(v(r, "flies(tweety)", frozenset()), Proven)
    assert kind(v(r, "flies(tweety)")) == "Unknown"         # abnormal under 'hurt'
    assert isinstance(v(r, "flies(pingu)"), Refuted)        # neg flies derived
    assert isinstance(v(r, "abnormal(tweety)", frozenset()), Refuted)  # closed world
    assert isinstance(v(r, "abnormal(tweety)"), Proven)


def test_open_world_not_requires_strong_negation() -> None:
    p = parse("""
        fact a: bird(x) @"fact:t".
        fact b: neg wet(y) @"fact:t".
        fact c: bird(y) @"fact:t".
        rule r: dry_bird(X) :- bird(X), not wet(X).
    """)
    r = run(p)
    assert isinstance(v(r, "dry_bird(y)"), Proven)
    u = v(r, "dry_bird(x)")
    assert isinstance(u, Unknown) and u.reason == "missing_facts"
    assert u.missing == ((parse_atom("neg wet(x)"),),)


def test_unknown_reasons() -> None:
    r = run(PENGUIN)
    u = v(r, "flies(tweety)")
    assert isinstance(u, Unknown) and u.reason == "missing_facts"
    assert u.missing == ((Atom("retract", (Sym("hurt"),)),),)
    u2 = v(r, "swims(tweety)")
    assert isinstance(u2, Unknown) and u2.reason == "open_world"


# ---------------------------------------------------------------- inconsistency

def test_inconsistent_base_theory_reports_conflict_set() -> None:
    p = parse("""
        fact a: penguin(p) @"fact:t".
        fact b: flies(p) @"fact:t".
        fact c: bird(p) @"fact:t".
        rule r: neg flies(X) :- penguin(X).
    """)
    res = v(run(p), "bird(p)")
    assert isinstance(res, Inconsistent)
    assert res.nogood == frozenset() and res.conflict_set == ("a", "b")


def test_assumption_nogood_only_when_assumed() -> None:
    p = parse("""
        fact a: penguin(p) @"fact:t".
        fact b: flies(p) @"assume:claim".
        rule r: neg flies(X) :- penguin(X).
    """)
    r = run(p)
    res = v(r, "penguin(p)")
    assert isinstance(res, Inconsistent) and res.conflict_set == ("a", "b", "claim")
    assert isinstance(v(r, "flies(p)", frozenset()), Refuted)


# ---------------------------------------------------------------- program errors

def test_non_stratifiable_program_is_rejected_with_cycle() -> None:
    p = parse("""
        world p closed. world q closed.
        fact f: d(a) @"fact:t".
        rule r1: p(X) :- d(X), not q(X).
        rule r2: q(X) :- d(X), not p(X).
    """)
    with pytest.raises(NotStratifiable) as e:
        evaluate(p)
    assert e.value.cycle[0] == e.value.cycle[-1] and {"p", "q"} <= set(e.value.cycle)
    assert "not stratifiable" in str(e.value)


def test_open_world_negation_cycle_is_fine() -> None:
    p = parse("""
        fact f: d(a) @"fact:t".
        rule r1: p(X) :- d(X), not q(X).
        rule r2: q(X) :- d(X), not p(X).
    """)
    assert kind(v(run(p), "p(a)")) == "Unknown"


def test_unsafe_program_rejected() -> None:
    with pytest.raises(InvalidProgram):
        evaluate(parse("rule r: p(X) :- not q(X)."))


# ---------------------------------------------------------------- budgets

NAT = parse("""
    fact z: nat(zero) @"fact:t".
    rule s: nat(s(X)) :- nat(X).
""")


def test_depth_budget_gives_unknown_budget_never_a_guess() -> None:
    r = run(NAT, Budget(max_depth=5))
    assert isinstance(v(r, "nat(s(s(zero)))"), Proven)           # sound positives survive
    deep = "nat(" + "s(" * 9 + "zero" + ")" * 9 + ")"
    u = v(r, deep)
    assert isinstance(u, Unknown) and u.reason == "budget"
    assert any(b.reason == "budget" for b in r.blocked)
    assert r.trace.complete == (False,)


def test_step_budget_marks_incomplete_and_blocks_closed_world_refutation() -> None:
    p = parse("world nat closed.\n" + "\n".join(
        f'fact f{i}: nat(n{i}) @"fact:t".' for i in range(50)))
    r = run(p, Budget(max_steps=10))
    u = v(r, "nat(n49)")
    assert isinstance(u, Unknown) and u.reason == "budget"
    full = run(p)
    assert isinstance(v(full, "nat(zz)"), Refuted)


def test_partial_domain_blocks_conclusions_that_need_exhaustiveness() -> None:
    p = parse("""
        world cand closed.
        domain d: cand() = {a, b} partial.
        rule r: none_left :- not cand(c).
    """)
    r = run(p)
    assert isinstance(v(r, "cand(a)"), Proven)
    u = v(r, "cand(c)")
    assert isinstance(u, Unknown) and u.reason == "budget"


def test_label_budget_truncates_soundly() -> None:
    src = "\n".join(f'fact f{i}: p(a) @"assume:x{i}".' for i in range(6))
    r = run(parse(src + "\nworld p closed."), Budget(max_label=3))
    assert parse_atom("p(a)") in r.trace.truncated
    assert isinstance(v(r, "p(a)", frozenset({"x0"})), Proven)
    u = v(r, "p(a)", frozenset({"x5"}))
    assert isinstance(u, Unknown) and u.reason == "budget"   # not a closed-world REFUTED


# ---------------------------------------------------------------- properties

def model_labels(r: Run) -> dict[Atom, object]:
    return {a: r.model.label(a) for a in r.model.atoms()}


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(programs())
def test_semi_naive_equals_naive(p: Program) -> None:
    assert model_labels(run(p)) == model_labels(run(p, naive=True))


@settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(programs())
def test_what_if_by_label_lookup_equals_rerun(p: Program) -> None:
    """Changing the active assumptions is a label lookup: it matches re-evaluating
    the program with the inactive assumptions' facts removed."""
    full = run(p)
    for ctx in [frozenset(), frozenset({"x"}), frozenset({"y"}), frozenset({"x", "y"})]:
        drop = {f.id for f in p.facts if f.assumption and f.assumption not in ctx}
        again = run(without(p, drop))
        atoms = set(full.model.atoms()) | set(again.model.atoms())
        for a in atoms:
            assert kind(verdict(full.model, a, ctx)) == kind(verdict(again.model, a, ctx)), a


@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(programs())
def test_metamorphic_reordering_and_irrelevant_facts(p: Program) -> None:
    base = run(p)
    shuffled = Program(p.worlds, tuple(reversed(p.facts)), tuple(reversed(p.rules)))
    extra = Program(p.worlds, (*p.facts, *parse('fact zz: unrelated(q) @"fact:t".').facts),
                    p.rules)
    for other in (run(shuffled), run(extra)):
        for a in base.model.atoms():
            assert kind(verdict(base.model, a)) == kind(verdict(other.model, a))


@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(programs(allow_neg=False))
def test_adding_an_assumption_keeps_empty_environment_proofs(p: Program) -> None:
    base = run(p)
    more = run(Program(p.worlds, (*p.facts, *parse('fact zz: p(c) @"assume:z".').facts),
                       p.rules))
    for a in base.model.atoms():
        b = verdict(base.model, a)
        if isinstance(b, Proven) and not b.assumptions:
            assert kind(verdict(more.model, a)) in ("Proven", "Inconsistent")


def test_ten_thousand_fact_program_runs_and_checks() -> None:
    """10k-fact program: correct answers. Its 5 s limit is in test_bench_timing."""
    facts = "\n".join(f'fact e{i}: edge(n{i}, n{i + 1}) @"fact:t".' for i in range(10_000))
    p = parse(facts + """
        world red closed.
        rule r1: two(X, Z) :- edge(X, Y), edge(Y, Z).
        rule r2: red(X) :- edge(X, Y), Y = n5.
        rule r3: pair(X, Z) :- two(X, Z), not red(X).
    """)
    r = run(p)
    assert isinstance(v(r, "pair(n0, n2)"), Proven)
    assert isinstance(v(r, "red(n3)"), Refuted)
