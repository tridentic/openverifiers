"""Small-scope search: try every integer value in [-k, k] before asking z3.

Alloy-style bounded instance finding. Nonlinear solvers find rational points
on curves badly (z3 tends to return algebraic numbers), while many
counterexamples and witnesses have small integer coordinates. A depth-first
search assigns variables one at a time, smallest values first, and checks
each constraint as soon as all its variables are set.

Untrusted, like z3: it only proposes models, which the engine re-checks. It
never claims unsat (finding nothing proves nothing), and it stops at a node
budget.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from fractions import Fraction

from .expand import CF, Poly

BOUND = 4
MAX_NODES = 200_000


def _vars(f: CF, out: set[str]) -> set[str]:
    if f[0] == "atom":
        p = f[2]
        assert isinstance(p, Poly)
        out.update(v for m, _ in p.terms for v, _ in m)
    elif f[0] in ("and", "or"):
        parts = f[1]
        assert isinstance(parts, (frozenset, tuple))
        for x in parts:
            _vars(x, out)
    return out


def _value(p: Poly, a: dict[str, int]) -> Fraction:
    total = Fraction(0)
    for mono, c in p.terms:
        t = c
        for v, k in mono:
            t *= a[v] ** k
        total += t
    return total


def holds(f: CF, a: dict[str, int]) -> bool:
    tag = f[0]
    if tag == "true":
        return True
    if tag == "false":
        return False
    if tag == "atom":
        op, p = f[1], f[2]
        assert isinstance(p, Poly)
        x = _value(p, a)
        if op in ("int", "nint"):
            return (x.denominator == 1) == (op == "int")
        return {"=": x == 0, "!=": x != 0, ">": x > 0, ">=": x >= 0}[str(op)]
    parts = f[1]
    assert isinstance(parts, (frozenset, tuple))
    return (all if tag == "and" else any)(holds(x, a) for x in parts)


def search(constraints: Sequence[CF], variables: Sequence[str], bound: int = BOUND,
           max_nodes: int = MAX_NODES, seconds: float = 2.0) -> dict[str, Fraction] | None:
    """A model with every variable an integer in [-bound, bound], or None."""
    cs: list[CF] = []
    for c in constraints:          # flatten top-level conjunctions
        if c[0] == "and":
            parts = c[1]
            assert isinstance(parts, (frozenset, tuple))
            cs.extend(parts)
        else:
            cs.append(c)
    if any(c[0] == "false" for c in cs):
        return None
    need = [_vars(c, set()) for c in cs]
    names = sorted(set(variables).union(*need)) if need else sorted(variables)
    # Order variables so constraints become checkable as early as possible.
    order: list[str] = []
    left = set(names)
    while left:
        def score(v: str) -> tuple[int, str]:
            done = set(order) | {v}
            return (-sum(1 for n in need if n and n <= done and not n <= set(order)), v)
        best = min(left, key=score)
        order.append(best)
        left.remove(best)
    ready: list[list[CF]] = [[] for _ in order]
    pos = {v: i for i, v in enumerate(order)}
    for c, n in zip(cs, need, strict=True):
        if n:
            ready[max(pos[v] for v in n)].append(c)
        elif not holds(c, {}):
            return None
    values = sorted(range(-bound, bound + 1), key=lambda x: (abs(x), x < 0))
    a: dict[str, int] = {}
    nodes = 0
    stop = time.monotonic() + seconds

    def go(i: int) -> bool:
        nonlocal nodes
        if i == len(order):
            return True
        for x in values:
            nodes += 1
            if nodes > max_nodes or (nodes & 1023 == 0 and time.monotonic() > stop):
                raise _Stop
            a[order[i]] = x
            if all(holds(c, a) for c in ready[i]) and go(i + 1):
                return True
        del a[order[i]]
        return False
    try:
        found = go(0)
    except _Stop:
        return None
    return {v: Fraction(a[v]) for v in names} if found else None


class _Stop(Exception):
    pass
