"""Assumption labels over signed environments (ATMS-style).

A *literal* is ``(name, True)`` (assumption ``name`` is active) or
``(name, False)`` (it is not). An *environment* is a consistent frozenset of
literals. A *label* is an antichain of environments: the atom holds in every
context that satisfies at least one of them.

Facts and axioms have the label ``TRUE = {{}}``; ``assume a`` has ``{{a}}``.
``FALSE = {}`` means "holds in no context". Negative literals come only from
closed-world negation (``negate``), which is what keeps labels exact, and so
counterfactuals a pure lookup, under stratified negation.

Trusted code.
"""

from __future__ import annotations

from collections.abc import Iterable

Lit = tuple[str, bool]
Env = frozenset[Lit]
Label = frozenset[Env]

EMPTY_ENV: Env = frozenset()
TRUE: Label = frozenset({EMPTY_ENV})
FALSE: Label = frozenset()


def assumption(name: str) -> Label:
    return frozenset({frozenset({(name, True)})})


def consistent(env: Env) -> bool:
    return not any((name, not sign) in env for name, sign in env)


def minimize(envs: Iterable[Env]) -> Label:
    """Drop inconsistent environments and every proper superset of another one."""
    kept: list[Env] = []
    for env in sorted({e for e in envs if consistent(e)}, key=len):
        if not any(k <= env for k in kept):
            kept.append(env)
    return frozenset(kept)


def disjoin(a: Label, b: Label) -> Label:
    return minimize(a | b)


def conjoin(a: Label, b: Label) -> Label:
    return minimize(x | y for x in a for y in b)


def combine(labels: Iterable[Label]) -> Label:
    """Label of a conjunction: minimised unions over the cross product."""
    out = TRUE
    for lab in labels:
        out = conjoin(out, lab)
        if not out:
            break
    return out


def negate(label: Label) -> Label:
    """Label of ``not p`` given the complete label of ``p``.

    ``not p`` holds in C iff no environment of ``p`` is satisfied by C, i.e.
    one literal from each environment is false in C: the minimal hitting
    sets of the label with every literal flipped.
    """
    out = TRUE
    for env in label:
        out = conjoin(out, frozenset(frozenset({(n, not s)}) for n, s in env))
        if not out:
            break
    return out


def satisfied(env: Env, context: frozenset[str]) -> bool:
    """Does the context (set of active assumptions) satisfy the environment?"""
    return all((name in context) == sign for name, sign in env)


def holds(label: Label, context: frozenset[str]) -> bool:
    return any(satisfied(e, context) for e in label)


def subsumed(env: Env, label: Label) -> bool:
    """Is ``env`` implied by the label (some environment of it is a subset)?"""
    return any(e <= env for e in label)


def covers(big: Label, small: Label) -> bool:
    """Does ``big`` hold wherever ``small`` holds (every env of small subsumed)?"""
    return all(subsumed(e, big) for e in small)


def prune(label: Label, nogoods: Label) -> Label:
    """Remove environments that contain a nogood."""
    return frozenset(e for e in label if not subsumed(e, nogoods))


def env_key(env: Env) -> tuple[tuple[str, bool], ...]:
    return tuple(sorted(env))


def label_key(label: Label) -> tuple[tuple[int, tuple[tuple[str, bool], ...]], ...]:
    """Deterministic order: by size, then literals."""
    return tuple(sorted((len(e), env_key(e)) for e in label))
