"""Semi-naive bottom-up evaluation with assumption labels and stratified negation.

This is the *untrusted* evaluator: it may be as clever as it likes, because
everything it produces is an ``OVTrace`` that ``openverifiers.checker``
re-verifies. It never decides a verdict.

Per stratum (lowest first) it runs rules to a fixpoint over labelled atoms.
A firing combines the premises' current labels (and, for closed-world
``not p``, the negation of p's final label); if that adds environments to
the head's label, a new cumulative step is recorded.

Budgets (steps, atoms, term depth, label size, wall time) never produce a
guess: exceeding one marks the stratum incomplete and stops evaluation there.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from ..raw import labels as L
from ..raw.builtins import compare
from ..raw.builtins import evaluate as eval_expr
from ..raw.labels import Label
from ..raw.program import (
    Assign,
    Atom,
    Compare,
    Literal,
    Naf,
    Pos,
    Program,
    Rule,
    Span,
    effective_body,
    validate,
)
from ..raw.terms import Term, depth, is_ground, match, substitute
from ..raw.trace import NafRef, Step, Trace
from .strata import stratify


class InvalidProgram(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Budget:
    max_steps: int = 200_000
    max_atoms: int = 200_000
    max_depth: int = 12
    max_label: int = 64
    timeout_s: float = 60.0


@dataclass
class Blocked:
    """A derivation the evaluator could not complete (informational, untrusted)."""

    rule_id: str
    reason: str
    atom: Atom
    detail: str = ""


class _Exhausted(Exception):
    pass


@dataclass
class _State:
    program: Program
    budget: Budget
    strata: dict[str, int]
    deadline: float
    steps: list[Step] = field(default_factory=list)
    latest: dict[Atom, int] = field(default_factory=dict)
    index: dict[str, dict[Term | None, list[Atom]]] = field(default_factory=dict)
    truncated: set[Atom] = field(default_factory=set)
    blocked: list[Blocked] = field(default_factory=list)
    incomplete: set[int] = field(default_factory=set)

    def label(self, a: Atom) -> Label:
        sid = self.latest.get(a)
        return L.FALSE if sid is None else self.steps[sid].label

    def add(self, head: Atom, combo: Label, stratum: int, *, rule_id: str,
            subst: tuple[tuple[str, Term], ...] = (), premises: tuple[int, ...] = (),
            naf: tuple[NafRef, ...] = (), span: Span | None = None, trunc: bool = False) -> bool:
        old = self.label(head)
        new = L.minimize(old | combo)
        if len(new) > self.budget.max_label:
            new = frozenset(sorted(new, key=lambda e: (len(e), L.env_key(e)))
                            [: self.budget.max_label])
            trunc = True
        if trunc:
            # A truncated label may be missing environments, so this stratum is not
            # the least model any more: stop before anything negates over it.
            self.truncated.add(head)
            self.incomplete.add(stratum)
        if new == old:
            return False
        if len(self.steps) >= self.budget.max_steps or (
                head not in self.latest and len(self.latest) >= self.budget.max_atoms):
            self.blocked.append(Blocked(rule_id, "budget", head, "step or atom budget"))
            raise _Exhausted
        if time.monotonic() > self.deadline:
            self.blocked.append(Blocked(rule_id, "budget", head, "time budget"))
            raise _Exhausted
        step = Step(id=len(self.steps), kind="fired", rule_id=rule_id, conclusion=head,
                    label=new, stratum=stratum, subst=subst, premises=premises, naf=naf,
                    prev=self.latest.get(head), span=span)
        if head not in self.latest:
            self.index.setdefault(head.key, {}).setdefault(_first(head), []).append(head)
        self.latest[head] = step.id
        self.steps.append(step)
        return True


def _first(a: Atom) -> Term | None:
    return a.args[0] if a.args else None


def _candidates(index: dict[str, dict[Term | None, list[Atom]]], pattern: Atom,
                s: dict[str, Term]) -> Iterator[Atom]:
    by_first = index.get(pattern.key)
    if not by_first:
        return
    if pattern.args:
        f = substitute(pattern.args[0], s)
        if is_ground(f):
            yield from list(by_first.get(f, ()))
            return
    for atoms in list(by_first.values()):
        yield from list(atoms)


@dataclass
class _Partial:
    subst: dict[str, Term]
    premises: list[int]
    naf: list[NafRef]
    labels: list[Label]
    trunc: bool


def _matches(st: _State, rule: Rule, body: tuple[Literal, ...], delta_pos: int | None,
             delta: dict[str, dict[Term | None, list[Atom]]]) -> Iterator[_Partial]:
    """All body matches; literal ``delta_pos`` (if given) ranges over ``delta`` only."""
    def go(i: int, p: _Partial) -> Iterator[_Partial]:
        if i == len(body):
            yield p
            return
        lit = body[i]
        if isinstance(lit, Pos):
            source = delta if i == delta_pos else st.index
            for cand in _candidates(source, lit.atom, p.subst):
                s2 = dict(p.subst)
                if len(cand.args) != len(lit.atom.args) or not all(
                        match(pa, ca, s2) for pa, ca in zip(lit.atom.args, cand.args, strict=True)):
                    continue
                sid = st.latest[cand]
                yield from go(i + 1, _Partial(s2, [*p.premises, sid], p.naf,
                                              [*p.labels, st.steps[sid].label],
                                              p.trunc or cand in st.truncated))
        elif isinstance(lit, Naf):
            target = Atom(lit.atom.pred, tuple(substitute(t, p.subst) for t in lit.atom.args),
                          lit.atom.neg)
            if target in st.truncated:
                st.blocked.append(Blocked(rule.id, "budget", target, "negation of truncated label"))
                st.incomplete.add(st.strata.get(rule.head.key, 0))
                return
            ref = st.latest.get(target)
            lab = L.TRUE if ref is None else L.negate(st.steps[ref].label)
            if not lab:
                return
            yield from go(i + 1, _Partial(p.subst, p.premises, [*p.naf, NafRef(target, ref)],
                                          [*p.labels, lab], p.trunc))
        elif isinstance(lit, Assign):
            v = eval_expr(lit.expr, p.subst)
            if v is None:
                return
            yield from go(i + 1, _Partial({**p.subst, lit.var.name: v}, p.premises, p.naf,
                                          p.labels, p.trunc))
        elif isinstance(lit, Compare) and compare(lit.op, lit.left, lit.right, p.subst):
            yield from go(i + 1, p)

    yield from go(0, _Partial({}, [], [], [], False))


def _fire(st: _State, rule: Rule, body: tuple[Literal, ...], stratum: int,
          delta_pos: int | None, delta: dict[str, dict[Term | None, list[Atom]]]) -> set[Atom]:
    changed: set[Atom] = set()
    for p in _matches(st, rule, body, delta_pos, delta):
        head = Atom(rule.head.pred, tuple(substitute(t, p.subst) for t in rule.head.args),
                    rule.head.neg)
        if any(depth(t) > st.budget.max_depth for t in head.args):
            st.blocked.append(Blocked(rule.id, "budget", head, "term depth budget"))
            st.incomplete.add(stratum)
            continue
        combo = L.combine(p.labels)
        if not combo:
            continue
        subst = tuple(sorted(p.subst.items()))
        if st.add(head, combo, stratum, rule_id=rule.id, subst=subst,
                  premises=tuple(p.premises), naf=tuple(p.naf), span=rule.span, trunc=p.trunc):
            changed.add(head)
    return changed


def evaluate(program: Program, budget: Budget | None = None, *, naive: bool = False) -> Trace:
    """Evaluate a RawOV program and return its (unchecked) trace."""
    return evaluate_full(program, budget, naive=naive)[0]


def evaluate_full(program: Program, budget: Budget | None = None, *,
                  naive: bool = False) -> tuple[Trace, list[Blocked]]:
    errors = validate(program)
    if errors:
        raise InvalidProgram(errors)
    budget = budget or Budget()
    strata = stratify(program)
    st = _State(program, budget, strata, time.monotonic() + budget.timeout_s)
    n_strata = max(strata.values(), default=0) + 1
    rules_by: dict[int, list[tuple[Rule, tuple[Literal, ...]]]] = {}
    for r in program.rules:
        rules_by.setdefault(strata[r.head.key], []).append((r, effective_body(r, program)))
    for pred in program.incomplete_preds():
        st.incomplete.add(strata.get(pred, 0))
        st.blocked.append(Blocked("", "budget", Atom(pred), "generator domain is partial"))

    evaluated = -1
    try:
        for f in program.all_facts():
            a = f.assumption
            st.add(f.atom, L.assumption(a) if a else L.TRUE, strata.get(f.atom.key, 0),
                   rule_id=f.id, span=f.span)
        for s in range(n_strata):
            if s in st.incomplete:
                break
            _run_stratum(st, s, rules_by.get(s, []), naive)
            evaluated = s
            if s in st.incomplete:
                break
    except _Exhausted:
        pass
    complete = tuple(i <= evaluated and i not in st.incomplete for i in range(n_strata))
    trace = Trace(tuple(st.steps), tuple(sorted(strata.items())), complete,
                  frozenset(st.truncated))
    return trace, st.blocked


def _run_stratum(st: _State, s: int, rules: list[tuple[Rule, tuple[Literal, ...]]],
                 naive: bool) -> None:
    heads = {r.head.key for r, _ in rules}
    changed: set[Atom] = set()
    for rule, body in rules:
        changed |= _fire(st, rule, body, s, None, st.index)
    while changed:
        delta: dict[str, dict[Term | None, list[Atom]]] = {}
        for a in changed:
            delta.setdefault(a.key, {}).setdefault(_first(a), []).append(a)
        changed = set()
        for rule, body in rules:
            if naive:
                changed |= _fire(st, rule, body, s, None, st.index)
                continue
            for i, lit in enumerate(body):
                if isinstance(lit, Pos) and lit.atom.key in heads and lit.atom.key in delta:
                    changed |= _fire(st, rule, body, s, i, delta)
