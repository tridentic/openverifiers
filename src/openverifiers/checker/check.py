"""Independent re-verification of an OVTrace against its RawOV program.

The evaluator's trace is a *claim*. This module accepts it only if:

1. **Well-formed program, valid strata.** ``validate`` passes and the claimed
   strata satisfy >= for positive and > for closed-world negative edges.
2. **Every fired step is locally justified**, in trace order:
   * the fact or rule exists; the substitution binds exactly the rule's
     variables; head and body instantiate to the conclusion and to the
     premises' conclusions; ``is``/comparison builtins hold;
   * premises are earlier fired steps; ``prev`` is the atom's previous step;
   * ``label == minimize(label(prev) | combine(premise labels, negations))``
     (a subset of it, for atoms the trace declares truncated).
   Earlier-only references make every claimed label environment sound.
3. **Negation is justified by the final model:** each ``not p`` reference
   points at p's *final* step (or p is absent) in a stratum that is complete.
4. **Closure** for every stratum claimed complete: one pass over every rule
   match on the final model finds no environment the model is missing.
   With 2 this makes the model exactly the least labelled model, which is
   what closed-world negation and refutation rely on.

The checker does not import the evaluator. Trusted code.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from ..raw import labels as L
from ..raw.builtins import compare, evaluate
from ..raw.labels import Env, Label
from ..raw.program import (
    Assign,
    Atom,
    Fact,
    Literal,
    Naf,
    Pos,
    Program,
    Rule,
    effective_body,
    strata_violations,
    validate,
)
from ..raw.terms import Term, is_ground, match, substitute, variables
from ..raw.trace import STEP_KINDS, NafRef, Step, Trace


class TraceRejected(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__(f"trace rejected: {reasons[0]}" + (
            f" (+{len(reasons) - 1} more)" if len(reasons) > 1 else ""))
        self.reasons = reasons


@dataclass(frozen=True)
class CheckedModel:
    """A trace the checker accepted, with the facts derived from it."""

    program: Program
    steps: tuple[Step, ...]
    latest: dict[Atom, int]
    strata: dict[str, int]
    complete: tuple[bool, ...]          # verified completeness per stratum
    truncated: frozenset[Atom]
    nogoods: dict[Env, tuple[Atom, Env, Env]]   # minimal nogood -> (p, env of p, env of neg p)

    def label(self, a: Atom) -> Label:
        sid = self.latest.get(a)
        return L.FALSE if sid is None else self.steps[sid].label

    def stratum_complete(self, key: str) -> bool:
        s = self.strata.get(key, 0)
        return s < len(self.complete) and self.complete[s]

    def atoms(self) -> Iterator[Atom]:
        return iter(self.latest)


def _inst(a: Atom, s: dict[str, Term]) -> Atom:
    return Atom(a.pred, tuple(substitute(t, s) for t in a.args), a.neg)


def _rule_vars(r: Rule) -> set[str]:
    out = {v for t in r.head.args for v in variables(t)}
    for lit in r.body:
        if isinstance(lit, Pos | Naf):
            out |= {v for t in lit.atom.args for v in variables(t)}
        elif isinstance(lit, Assign):
            out |= {lit.var.name, *variables(lit.expr)}
        else:
            out |= {*variables(lit.left), *variables(lit.right)}
    return out


def check_trace(program: Program, trace: Trace) -> CheckedModel:
    """Return the checked model, or raise ``TraceRejected`` with every reason found."""
    errs: list[str] = list(validate(program))
    if errs:
        raise TraceRejected(errs)
    strata = dict(trace.strata)
    n = len(trace.complete)
    keys = {f.atom.key for f in program.all_facts()} | {r.head.key for r in program.rules}
    errs += [f"no stratum for {k!r}" for k in sorted(keys - strata.keys())]
    errs += [f"stratum of {k!r} out of range" for k, v in strata.items() if not 0 <= v < n]
    errs += strata_violations(program, strata)
    if errs:
        raise TraceRejected(errs)

    facts: dict[str, Fact] = {f.id: f for f in program.all_facts()}
    rules = {r.id: (r, effective_body(r, program)) for r in program.rules}
    latest: dict[Atom, int] = {}
    pending: list[tuple[int, NafRef]] = []
    steps = trace.steps

    for i, st in enumerate(steps):
        where = f"step {i}"
        if st.id != i:
            errs.append(f"{where}: id {st.id} out of sequence")
            break
        if st.kind not in STEP_KINDS:
            errs.append(f"{where}: unknown kind {st.kind!r}")
            continue
        if st.kind == "blocked":
            continue  # informational only; it claims nothing
        errs += [f"{where}: {e}" for e in _check_step(st, steps, facts, rules, strata, latest,
                                                      trace.truncated, pending)]
        latest[st.conclusion] = i

    eff = _effective_complete(trace, strata)
    for sid, ref in pending:
        final = latest.get(ref.atom)
        if final != ref.step:
            errs.append(f"step {sid}: 'not' uses step {ref.step} of {ref.atom.key}, "
                        f"but its final step is {final}")
        if not _complete(eff, strata, ref.atom.key) or ref.atom in trace.truncated:
            errs.append(f"step {sid}: 'not {ref.atom.key}' relies on an incomplete stratum")
    if not errs:
        errs += _closure(program, rules, steps, latest, strata, eff)
    if errs:
        raise TraceRejected(errs)
    return CheckedModel(program, steps, latest, strata, eff, trace.truncated,
                        _nogoods(steps, latest))


def _effective_complete(trace: Trace, strata: dict[str, int]) -> tuple[bool, ...]:
    """A stratum counts as complete only if it and every lower one are, untruncated."""
    trunc = {strata.get(a.key, 0) for a in trace.truncated}
    out: list[bool] = []
    for s, claimed in enumerate(trace.complete):
        out.append(claimed and s not in trunc and all(out))
    return tuple(out)


def _complete(eff: tuple[bool, ...], strata: dict[str, int], key: str) -> bool:
    s = strata.get(key, 0)
    return s < len(eff) and eff[s]


def _check_step(st: Step, steps: tuple[Step, ...], facts: dict[str, Fact],
                rules: dict[str, tuple[Rule, tuple[Literal, ...]]], strata: dict[str, int],
                latest: dict[Atom, int], truncated: frozenset[Atom],
                pending: list[tuple[int, NafRef]]) -> Iterator[str]:
    c = st.conclusion
    if not all(is_ground(t) for t in c.args):
        yield "conclusion is not ground"
        return
    if st.stratum != strata.get(c.key, 0):
        yield f"stratum {st.stratum} but {c.key!r} is in stratum {strata.get(c.key, 0)}"
    if st.prev != latest.get(c):
        yield f"prev is {st.prev}, expected {latest.get(c)}"
        return
    parts: list[Label] = []
    if st.rule_id in facts:
        f = facts[st.rule_id]
        if f.atom != c:
            yield f"fact {f.id!r} states {f.atom}, not the conclusion"
            return
        if st.premises or st.naf or st.subst:
            yield "a fact step has premises or a substitution"
            return
        a = f.assumption
        parts.append(L.assumption(a) if a else L.TRUE)
    elif st.rule_id in rules:
        rule, body = rules[st.rule_id]
        s = dict(st.subst)
        if len(s) != len(st.subst) or set(s) != _rule_vars(rule):
            yield f"substitution must bind exactly {sorted(_rule_vars(rule))}"
            return
        if not all(is_ground(v) for v in s.values()):
            yield "substitution is not ground"
            return
        if _inst(rule.head, s) != c:
            yield "head under the substitution is not the conclusion"
            return
        prem, nafs = list(st.premises), list(st.naf)
        for k, lit in enumerate(body, 1):
            if isinstance(lit, Pos):
                if not prem:
                    yield f"literal {k}: missing premise"
                    return
                pid = prem.pop(0)
                if not 0 <= pid < st.id or steps[pid].kind != "fired":
                    yield f"literal {k}: premise {pid} is not an earlier fired step"
                    return
                if steps[pid].conclusion != _inst(lit.atom, s):
                    yield f"literal {k}: premise {pid} proves a different atom"
                    return
                parts.append(steps[pid].label)
            elif isinstance(lit, Naf):
                if not nafs:
                    yield f"literal {k}: missing negation reference"
                    return
                ref = nafs.pop(0)
                if ref.atom != _inst(lit.atom, s):
                    yield f"literal {k}: negation reference is for a different atom"
                    return
                if ref.step is None:
                    parts.append(L.TRUE)
                else:
                    if not 0 <= ref.step < len(steps) or steps[ref.step].kind != "fired" \
                            or steps[ref.step].conclusion != ref.atom:
                        yield f"literal {k}: negation reference {ref.step} is not a step of it"
                        return
                    parts.append(L.negate(steps[ref.step].label))
                pending.append((st.id, ref))
            elif isinstance(lit, Assign):
                if evaluate(lit.expr, s) != s.get(lit.var.name):
                    yield f"literal {k}: {lit.var.name} is not the value of the expression"
                    return
            elif not compare(lit.op, lit.left, lit.right, s):
                yield f"literal {k}: comparison does not hold"
                return
        if prem or nafs:
            yield "more premises than the rule body has literals"
            return
    else:
        yield f"no fact or rule {st.rule_id!r}"
        return
    prev = L.FALSE if st.prev is None else steps[st.prev].label
    expected = L.minimize(prev | L.combine(parts))
    if c in truncated:
        if not st.label or not st.label <= expected:
            yield "truncated label is not a non-empty subset of the justified label"
    elif st.label != expected:
        yield "label does not follow from the premises"


Index = dict[str, dict[Term | None, list[Atom]]]


def _candidates(index: Index, pattern: Atom, s: dict[str, Term]) -> list[Atom]:
    """Atoms with the pattern's key; narrowed by the first argument when it is bound."""
    by_first = index.get(pattern.key, {})
    first = substitute(pattern.args[0], s) if pattern.args else None
    if first is not None and is_ground(first):
        return by_first.get(first, [])
    return [a for atoms in by_first.values() for a in atoms]


def _matches(body: tuple[Literal, ...], index: Index,
             label_of: dict[Atom, Label]) -> Iterator[tuple[dict[str, Term], list[Label]]]:
    def go(i: int, s: dict[str, Term], labs: list[Label]
           ) -> Iterator[tuple[dict[str, Term], list[Label]]]:
        if i == len(body):
            yield s, labs
            return
        lit = body[i]
        if isinstance(lit, Pos):
            for cand in _candidates(index, lit.atom, s):
                s2 = dict(s)
                if len(cand.args) == len(lit.atom.args) and all(
                        match(p, g, s2) for p, g in zip(lit.atom.args, cand.args, strict=True)):
                    yield from go(i + 1, s2, [*labs, label_of[cand]])
        elif isinstance(lit, Naf):
            lab = L.negate(label_of.get(_inst(lit.atom, s), L.FALSE))
            if lab:
                yield from go(i + 1, s, [*labs, lab])
        elif isinstance(lit, Assign):
            v = evaluate(lit.expr, s)
            if v is not None:
                yield from go(i + 1, {**s, lit.var.name: v}, labs)
        elif compare(lit.op, lit.left, lit.right, s):
            yield from go(i + 1, s, labs)

    yield from go(0, {}, [])


def _closure(program: Program, rules: dict[str, tuple[Rule, tuple[Literal, ...]]],
             steps: tuple[Step, ...], latest: dict[Atom, int], strata: dict[str, int],
             eff: tuple[bool, ...]) -> list[str]:
    label_of = {a: steps[i].label for a, i in latest.items()}
    index: Index = {}
    for a in latest:
        index.setdefault(a.key, {}).setdefault(a.args[0] if a.args else None, []).append(a)
    errs: list[str] = []
    for f in program.all_facts():
        if _complete(eff, strata, f.atom.key):
            name = f.assumption
            base = L.assumption(name) if name else L.TRUE
            if not L.covers(label_of.get(f.atom, L.FALSE), base):
                errs.append(f"closure: fact {f.id!r} is missing from the model")
    for rule, body in rules.values():
        if not _complete(eff, strata, rule.head.key):
            continue
        for s, labs in _matches(body, index, label_of):
            combo = L.combine(labs)
            head = _inst(rule.head, s)
            if combo and not L.covers(label_of.get(head, L.FALSE), combo):
                errs.append(f"closure: rule {rule.id!r} derives {head} in a context the "
                            "model does not record")
                if len(errs) > 20:
                    return errs
    return errs


def _nogoods(steps: tuple[Step, ...], latest: dict[Atom, int]) -> dict[Env, tuple[Atom, Env, Env]]:
    found: dict[Env, tuple[Atom, Env, Env]] = {}
    for a, i in latest.items():
        if a.neg or a.complement() not in latest:
            continue
        for e1 in sorted(steps[i].label, key=L.env_key):
            for e2 in sorted(steps[latest[a.complement()]].label, key=L.env_key):
                u = e1 | e2
                if L.consistent(u) and u not in found:
                    found[u] = (a, e1, e2)
    minimal = L.minimize(found)
    return {e: found[e] for e in sorted(minimal, key=lambda e: (len(e), L.env_key(e)))}
