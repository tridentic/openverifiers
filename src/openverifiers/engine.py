"""Glue: evaluate (untrusted) -> check (trusted) -> verdicts (trusted).

Nothing reaches a caller unless the checker accepted the trace. The only
untrusted thing added afterwards is UNKNOWN's ``missing`` frontier (which
premises a derivation got stuck on), and each listed ground atom is
re-confirmed against the checked model before it is reported.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .checker import CheckedModel, Unknown, Verdict, check_trace, find, verdict
from .kernel.evaluate import Blocked, Budget, evaluate_full
from .raw import labels as L
from .raw.builtins import compare
from .raw.builtins import evaluate as eval_expr
from .raw.program import Assign, Atom, Compare, Naf, Pos, Program, effective_body
from .raw.terms import Term, is_ground, match, substitute
from .raw.trace import Trace


@dataclass(frozen=True)
class Run:
    trace: Trace
    model: CheckedModel
    blocked: tuple[Blocked, ...]


def run(program: Program, budget: Budget | None = None, *, naive: bool = False) -> Run:
    trace, blocked = evaluate_full(program, budget, naive=naive)
    return Run(trace, check_trace(program, trace), tuple(blocked))


def ask(r: Run, q: Atom, context: frozenset[str] | None = None) -> Verdict:
    v = verdict(r.model, q, context)
    if isinstance(v, Unknown) and v.reason == "open_world":
        frontier = missing_frontier(r.model, q, context)
        if frontier:
            return replace(v, missing=frontier, reason="missing_facts")
    return v


def find_all(r: Run, pattern: Atom, context: frozenset[str] | None = None
             ) -> list[tuple[dict[str, Term], Verdict]]:
    return find(r.model, pattern, context)


def without(program: Program, item_ids: set[str]) -> Program:
    """The program with some facts/rules/domains retracted (for WHAT IF RETRACT <fact>)."""
    return Program(program.worlds, tuple(f for f in program.facts if f.id not in item_ids),
                   tuple(x for x in program.rules if x.id not in item_ids),
                   tuple(d for d in program.domains if d.id not in item_ids))


def missing_frontier(m: CheckedModel, q: Atom, context: frozenset[str] | None = None
                     ) -> tuple[tuple[Atom, ...], ...]:
    """For each rule that could conclude q: the first body literal it cannot satisfy.

    Depth one, untrusted heuristic; every ground atom reported is re-checked
    to be not established in the context.
    """
    from .checker.verdict import default_context
    c = default_context(m) if context is None else context
    holds = {a for a in m.atoms() if L.holds(m.label(a), c)}
    out: list[tuple[Atom, ...]] = []
    for rule in m.program.rules:
        s0: dict[str, Term] = {}
        if rule.head.key != q.key or len(rule.head.args) != len(q.args) or not all(
                match(p, g, s0) for p, g in zip(rule.head.args, q.args, strict=True)):
            continue
        stuck = _stuck(effective_body(rule, m.program), s0, holds)
        if stuck is not None and stuck not in out:
            out.append(stuck)
    return tuple(a for a in out if all(not is_ground_atom(x) or x not in holds for x in a))


def is_ground_atom(a: Atom) -> bool:
    return all(is_ground(t) for t in a.args)


def _stuck(body: tuple[object, ...], s: dict[str, Term], holds: set[Atom]
           ) -> tuple[Atom, ...] | None:
    def inst(a: Atom, sub: dict[str, Term]) -> Atom:
        return Atom(a.pred, tuple(substitute(t, sub) for t in a.args), a.neg)

    frontier: list[tuple[int, dict[str, Term]]] = [(0, s)]
    deepest: tuple[int, Atom] | None = None
    while frontier:
        i, sub = frontier.pop()
        if i == len(body):
            return None  # satisfiable: not stuck
        lit = body[i]
        if isinstance(lit, Pos):
            pat = inst(lit.atom, sub)
            nxt = []
            for a in holds:
                s2 = dict(sub)
                if a.key == pat.key and len(a.args) == len(pat.args) and all(
                        match(p, g, s2) for p, g in zip(pat.args, a.args, strict=True)):
                    nxt.append((i + 1, s2))
            if not nxt and (deepest is None or i >= deepest[0]):
                deepest = (i, pat)
            frontier.extend(nxt)
        elif isinstance(lit, Naf):
            if inst(lit.atom, sub) not in holds:
                frontier.append((i + 1, sub))
        elif isinstance(lit, Assign):
            v = eval_expr(lit.expr, sub)
            if v is not None:
                frontier.append((i + 1, {**sub, lit.var.name: v}))
        elif isinstance(lit, Compare) and compare(lit.op, lit.left, lit.right, sub):
            frontier.append((i + 1, sub))
    return None if deepest is None else (deepest[1],)
