"""Trace mutation operators for the checker soundness test.

Each operator corrupts one step of a real trace the way a buggy or lying
evaluator might. A mutant that the checker accepts is a *survivor* unless it
is *equivalent* (its final labelled model is identical to the original's),
which is the standard equivalent-mutant rule.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from dataclasses import replace

from openverifiers.raw import Atom, Step, Sym, Trace
from openverifiers.raw.trace import NafRef

Mutant = tuple[str, Trace]


def _with(trace: Trace, i: int, step: Step) -> Trace:
    steps = list(trace.steps)
    steps[i] = step
    return replace(trace, steps=tuple(steps))


def _consts(trace: Trace) -> list[Sym]:
    seen: set[Sym] = set()
    for s in trace.steps:
        for t in s.conclusion.args:
            if isinstance(t, Sym):
                seen.add(t)
    return [*sorted(seen, key=lambda x: x.name), Sym("zz_bogus")]


def wrong_substitution(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    if not s.subst:
        return
    k = rng.randrange(len(s.subst))
    name, val = s.subst[k]
    for c in _consts(trace):
        if c != val:
            sub = list(s.subst)
            sub[k] = (name, c)
            yield "wrong_substitution", _with(trace, i, replace(s, subst=tuple(sub)))
            return


def missing_premise(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    if s.premises:
        k = rng.randrange(len(s.premises))
        yield "missing_premise", _with(trace, i, replace(
            s, premises=s.premises[:k] + s.premises[k + 1:]))


def swapped_premise(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    if s.premises and i > 1:
        k = rng.randrange(len(s.premises))
        other = rng.randrange(i)
        if other != s.premises[k]:
            prem = list(s.premises)
            prem[k] = other
            yield "swapped_premise", _with(trace, i, replace(s, premises=tuple(prem)))


def swapped_label(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    others = [t.label for t in trace.steps if t.label != s.label]
    if others:
        yield "swapped_label", _with(trace, i, replace(s, label=rng.choice(others)))
    yield "weakened_label", _with(trace, i, replace(
        s, label=frozenset({frozenset({("zz_assumption", True)})} | {
            e for e in s.label if e})))


def wrong_conclusion(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    c = s.conclusion
    if c.args:
        k = rng.randrange(len(c.args))
        args = list(c.args)
        args[k] = Sym("zz_bogus")
        yield "wrong_conclusion", _with(trace, i, replace(s, conclusion=Atom(
            c.pred, tuple(args), c.neg)))
    yield "flipped_negation", _with(trace, i, replace(s, conclusion=c.complement()))


def wrong_prev(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    new = None if s.prev is not None else (rng.randrange(i) if i else None)
    if new != s.prev:
        yield "wrong_prev", _with(trace, i, replace(s, prev=new))


def wrong_negation_ref(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    if s.naf:
        k = rng.randrange(len(s.naf))
        ref = s.naf[k]
        cand = [None, *range(len(trace.steps))]
        new = rng.choice([x for x in cand if x != ref.step])
        naf = list(s.naf)
        naf[k] = NafRef(ref.atom, new)
        yield "wrong_negation_ref", _with(trace, i, replace(s, naf=tuple(naf)))


def dropped_step(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    def renum(x: int | None) -> int | None:
        return None if x is None else (x - 1 if x > i else x)
    steps = []
    for s in trace.steps[:i] + trace.steps[i + 1:]:
        steps.append(replace(s, id=renum(s.id) or 0, prev=renum(s.prev),
                             premises=tuple(renum(p) or 0 for p in s.premises),
                             naf=tuple(NafRef(n.atom, renum(n.step)) for n in s.naf)))
    yield "dropped_step", replace(trace, steps=tuple(steps))


def fabricated_fact(trace: Trace, i: int, rng: random.Random) -> Iterator[Mutant]:
    s = trace.steps[i]
    yield "fabricated_fact", _with(trace, i, replace(s, rule_id="zz_no_such_fact",
                                                      premises=(), subst=(), naf=()))


OPERATORS: list[Callable[[Trace, int, random.Random], Iterator[Mutant]]] = [
    wrong_substitution, missing_premise, swapped_premise, swapped_label, wrong_conclusion,
    wrong_prev, wrong_negation_ref, dropped_step, fabricated_fact,
]


def mutants(trace: Trace, seed: int = 0, per_step: int = 1) -> Iterator[Mutant]:
    rng = random.Random(seed)
    for i in range(len(trace.steps)):
        for op in OPERATORS:
            for _ in range(per_step):
                yield from op(trace, i, rng)
