"""Verdicts computed from a checked model. Exactly four outcomes, never a score.

For a ground query ``q`` in context C (the set of active assumptions):

* INCONSISTENT if C satisfies a nogood (an environment where some ``p`` and
  ``neg p`` both hold), or if both of the next two cases hold;
* PROVEN if some environment of label(q) is satisfied by C;
* REFUTED if some environment of label(neg q) is satisfied by C, or, for a
  closed-world predicate whose stratum is complete, if q is not PROVEN;
* UNKNOWN otherwise, with a reason: ``budget`` (an incomplete stratum or a
  truncated label is involved), ``missing_facts`` (q holds only under other
  assumptions; ``missing`` lists what would have to change), or
  ``open_world``.

Proofs are sets of trace step ids, extracted by walking justifications
backwards; they are well founded because premises always precede a step.

Trusted code.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..raw import labels as L
from ..raw.labels import Env, Label
from ..raw.program import Atom
from ..raw.terms import Sym, Term, is_ground, match
from .check import CheckedModel

UNKNOWN_REASONS = ("missing_facts", "budget", "plugin_unknown", "open_world")


@dataclass(frozen=True)
class Proven:
    atom: Atom
    proof: tuple[int, ...]
    assumptions: Env


@dataclass(frozen=True)
class Refuted:
    atom: Atom
    proof: tuple[int, ...]
    assumptions: Env
    closed_world: bool = False


@dataclass(frozen=True)
class Unknown:
    atom: Atom
    missing: tuple[tuple[Atom, ...], ...]
    reason: str


@dataclass(frozen=True)
class Inconsistent:
    atom: Atom
    conflict_set: tuple[str, ...]   # fact ids and assumption names
    nogood: Env


Verdict = Proven | Refuted | Unknown | Inconsistent


def _best(label: Label, context: frozenset[str]) -> Env | None:
    sat = [e for e in label if L.satisfied(e, context)]
    return min(sat, key=lambda e: (len(e), L.env_key(e))) if sat else None


def proof(m: CheckedModel, atom: Atom, env: Env) -> tuple[int, ...]:
    """Step ids of a derivation of ``atom`` valid in every context satisfying ``env``."""
    out: set[int] = set()
    todo = [m.latest[atom]]
    while todo:
        sid = todo.pop()
        while True:
            st = m.steps[sid]
            if st.prev is not None and L.subsumed(env, m.steps[st.prev].label):
                sid = st.prev
                continue
            break
        if sid in out:
            continue
        out.add(sid)
        todo.extend(st.premises)
    return tuple(sorted(out))


def leaves(m: CheckedModel, steps: tuple[int, ...]) -> tuple[str, ...]:
    """The facts (by id) a proof rests on."""
    ids = {f.id for f in m.program.all_facts()}
    return tuple(sorted({m.steps[i].rule_id for i in steps if m.steps[i].rule_id in ids}))


def _conflict(m: CheckedModel, nogood: Env) -> tuple[str, ...]:
    a, e1, e2 = m.nogoods[nogood]
    used = proof(m, a, e1) + proof(m, a.complement(), e2)
    names = {n for n, sign in nogood if sign}
    return tuple(sorted(set(leaves(m, used)) | names))


def default_context(m: CheckedModel) -> frozenset[str]:
    """All declared assumptions are active unless a query says otherwise."""
    return m.program.assumptions()


def verdict(m: CheckedModel, q: Atom, context: frozenset[str] | None = None) -> Verdict:
    if not all(is_ground(t) for t in q.args):
        raise ValueError("verdict needs a ground atom; use find() for patterns")
    c = default_context(m) if context is None else context
    for ng in m.nogoods:
        if L.satisfied(ng, c):
            return Inconsistent(q, _conflict(m, ng), ng)
    pos = _best(m.label(q), c)
    neg = _best(m.label(q.complement()), c)
    if pos is not None and neg is not None:   # only reachable with truncated labels
        return Inconsistent(q, (), pos | neg)
    if pos is not None:
        return Proven(q, proof(m, q, pos), pos)
    if neg is not None:
        return Refuted(q, proof(m, q.complement(), neg), neg)
    budget = (not m.stratum_complete(q.key) or not m.stratum_complete(q.complement().key)
              or q in m.truncated or q.complement() in m.truncated)
    if m.program.closed(q.pred) and not budget:
        env = _best(L.negate(m.label(q)), c)
        assert env is not None  # q is not proven in c, so its negation holds in c
        return Refuted(q, (), env, closed_world=True)
    if budget:
        return Unknown(q, (), "budget")
    elsewhere = sorted(m.label(q), key=lambda e: (len(e), L.env_key(e)))
    if elsewhere:
        return Unknown(q, tuple(_changes(e, c) for e in elsewhere), "missing_facts")
    return Unknown(q, (), "open_world")


def _changes(env: Env, c: frozenset[str]) -> tuple[Atom, ...]:
    """What would have to change in C for ``env`` to hold: assume / retract atoms."""
    out = [Atom("assume", (Sym(n),)) for n, s in sorted(env) if s and n not in c]
    out += [Atom("retract", (Sym(n),)) for n, s in sorted(env) if not s and n in c]
    return tuple(out)


def find(m: CheckedModel, pattern: Atom, context: frozenset[str] | None = None
         ) -> list[tuple[dict[str, Term], Verdict]]:
    """Every grounding of ``pattern`` the model knows (as q or neg q), with its verdict."""
    seen: dict[Atom, dict[str, Term]] = {}
    for a in sorted(m.atoms(), key=lambda a: m.latest[a]):
        cand = a.complement() if a.key != pattern.key else a
        if cand.key != pattern.key or cand in seen or len(cand.args) != len(pattern.args):
            continue
        s: dict[str, Term] = {}
        if all(match(p, g, s) for p, g in zip(pattern.args, cand.args, strict=True)):
            seen[cand] = s
    return [(s, verdict(m, a, context)) for a, s in seen.items()]
