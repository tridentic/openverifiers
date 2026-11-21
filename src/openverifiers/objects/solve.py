"""The z3 side of the object layer: constraint formulas in, models or unsat out.

Untrusted. A model is only a proposal; the engine re-checks it with the exact
evaluator. An unsat answer cannot be checked by substitution, so the engine
re-solves it in a fresh solver, as the brief allows for unsat cores.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction

import z3

from ..raw.surd import Surd, SurdError
from . import smallscope
from .expand import CF, Poly, root_definitions

SEEDS = (0, 1, 2, 3)
#: Added to every z3 random seed. ``ov bench --seeds N`` runs each case under
#: N bases to measure solver variance; the default 0 keeps runs reproducible.
SEED_BASE = 0


@contextmanager
def seed_base(base: int) -> Iterator[None]:
    global SEED_BASE
    old, SEED_BASE = SEED_BASE, base
    try:
        yield
    finally:
        SEED_BASE = old


@dataclass(frozen=True)
class Result:
    status: str                                  # sat | unsat | unknown
    model: dict[str, Fraction | Surd] | None = None
    reason: str = ""                             # for unknown: budget | plugin_unknown
    via: str = "z3"                              # z3 | small-scope


def _poly(p: Poly, vs: dict[str, z3.ArithRef]) -> z3.ArithRef:
    terms = []
    for mono, c in p.terms:
        t: z3.ArithRef = z3.RealVal(f"{c.numerator}/{c.denominator}")
        for v, k in mono:
            if v not in vs:
                vs[v] = z3.Real(v)
            for _ in range(k):
                t = t * vs[v]
        terms.append(t)
    return z3.Sum(terms) if len(terms) > 1 else terms[0] if terms else z3.RealVal(0)


def canon(f: CF) -> str:
    """A text key that does not depend on set iteration order (so runs are reproducible)."""
    if f[0] in ("and", "or"):
        parts = f[1]
        assert isinstance(parts, (frozenset, tuple))
        keys = [canon(x) for x in parts]
        return f"{f[0]}(" + ",".join(sorted(keys) if isinstance(parts, frozenset) else keys) + ")"
    return repr(f)


def to_z3(f: CF, vs: dict[str, z3.ArithRef]) -> z3.BoolRef:
    tag = f[0]
    if tag == "true":
        return z3.BoolVal(True)
    if tag == "false":
        return z3.BoolVal(False)
    if tag == "atom":
        op, p = f[1], f[2]
        assert isinstance(p, Poly)
        e = _poly(p, vs)
        return {"=": e == 0, "!=": e != 0, ">": e > 0, ">=": e >= 0}[str(op)]
    parts = f[1]
    assert isinstance(parts, (frozenset, tuple))
    zs = [to_z3(x, vs) for x in sorted(parts, key=canon)]
    return z3.And(zs) if tag == "and" else z3.Or(zs)


def _conjuncts(cs: Sequence[CF]) -> list[CF]:
    out: list[CF] = []
    for c in cs:
        if c[0] == "and":
            parts = c[1]
            assert isinstance(parts, (frozenset, tuple))
            out += _conjuncts(sorted(parts, key=canon))
        else:
            out.append(c)
    return out


def _split(cs: list[CF]) -> tuple[list[CF], list[CF]] | None:
    """The disjunction of conjunctions with the most branches, and the other conjuncts."""
    best = None
    for c in cs:
        if c[0] == "or":
            parts = c[1]
            assert isinstance(parts, (frozenset, tuple))
            n = sum(1 for x in parts if x[0] == "and")
            if n >= 2 and (best is None or n > best[0]):
                best = (n, c)
    if best is None:
        return None
    parts = best[1][1]
    assert isinstance(parts, (frozenset, tuple))
    return sorted(parts, key=canon), [c for c in cs if c is not best[1]]


#: The small-scope budget is a node count, so its answer does not depend on the
#: machine: about 200 ms here (8k-130k nodes/s depending on the constraints). The
#: wall-clock cap is only a backstop for pathological constraint sets.
SMALL_SCOPE_NODES = 10_000
SMALL_SCOPE_CAP_SECONDS = 2.0


def small_scope(constraints: Sequence[CF], variables: Sequence[str] = ()) -> Result:
    """Integer points in [-4, 4] only (Alloy-style). It never claims unsat: a miss is
    UNKNOWN(budget)."""
    found = smallscope.search(_conjuncts(constraints), variables,
                              max_nodes=SMALL_SCOPE_NODES, seconds=SMALL_SCOPE_CAP_SECONDS)
    via = f"small-scope [-{smallscope.BOUND}, {smallscope.BOUND}]"
    return Result("sat", dict(found), via=via) if found is not None else Result(
        "unknown", None, "budget", via=via)


def _vars_of(f: CF, out: set[str]) -> None:
    if f[0] == "atom":
        p = f[2]
        assert isinstance(p, Poly)
        out.update(v for m, _ in p.terms for v, _ in m)
    elif f[0] in ("and", "or"):
        parts = f[1]
        assert isinstance(parts, (frozenset, tuple))
        for x in parts:
            _vars_of(x, out)


def solve(constraints: Sequence[CF], variables: Sequence[str] = (),
          timeout_ms: int = 20_000, *, seek: bool = False) -> Result:
    """Solve the conjunction. Exists-disjunctions (one branch per ordering of a cycle,
    say) are split into separate, conjunctive problems: nonlinear search is far easier
    on each branch than on the disjunction, and unsat needs every branch unsat.

    ``seek``: the caller is looking for something that may exist (FIND, consistency,
    COUNTEREXAMPLE), so try small integer points first. It is off for proofs, where
    the expected answer is unsat and the search could only waste time."""
    cs = _conjuncts(constraints)
    used: set[str] = set()
    for c in cs:
        _vars_of(c, used)
    roots = root_definitions(sorted(used))
    if roots:
        cs = _conjuncts([*cs, *roots])
        extra: set[str] = set()
        for c in roots:
            _vars_of(c, extra)
        variables = [*variables, *(n for n in sorted(used | extra)
                                   if n == "PI" or n.startswith(("ROOT_", "EXP_", "LN_")))]
    if seek:
        r0 = small_scope(cs, variables)
        if r0.status == "sat":
            return r0
    deadline = time.monotonic() + 3 * timeout_ms / 1000
    # A quick pass over every branch first: a sat branch late in the order is found
    # without waiting for hard unsat branches before it to time out.
    r = _solve(cs, list(variables), max(1, timeout_ms // 20), deadline, 2)
    if r.status != "unknown" or time.monotonic() > deadline:
        return r
    return _solve(cs, list(variables), timeout_ms, deadline, 2)


def _solve(cs: list[CF], variables: list[str], timeout_ms: int, deadline: float,
           depth: int) -> Result:
    split = _split(cs) if depth > 0 else None
    if split is not None:
        branches, rest = split
        status = "unsat"
        for b in branches:
            if time.monotonic() > deadline:
                return Result("unknown", reason="budget")
            r = _solve(_conjuncts([*rest, b]), variables, timeout_ms, deadline, depth - 1)
            if r.status == "sat":
                return r
            if r.status == "unknown":
                status, why = "unknown", r.reason
        return Result("unsat") if status == "unsat" else Result("unknown", reason=why)
    vs: dict[str, z3.ArithRef] = {v: z3.Real(v) for v in variables}
    goal = [to_z3(c, vs) for c in cs]
    # Nonlinear search is sensitive to the random seed: try a few fixed seeds, each with
    # a share of the time. Fixed seeds keep runs reproducible; any model is re-checked.
    for i, seed in enumerate(SEEDS):
        left = int((deadline - time.monotonic()) * 1000)
        s = z3.SolverFor("QF_NRA")
        s.set("timeout", max(1, min(timeout_ms // len(SEEDS), left)))
        s.set("random_seed", SEED_BASE + seed)
        s.add(*goal)
        r = s.check()
        if r != z3.unknown or i == len(SEEDS) - 1 or left <= 0:
            break
    if r == z3.unsat:
        return Result("unsat")
    if r == z3.unknown:
        why = s.reason_unknown()
        return Result("unknown", reason="budget" if "timeout" in why or "canceled" in why
                      else "plugin_unknown")
    m = s.model()
    out: dict[str, Fraction | Surd] = {}
    for name, v in vs.items():
        val = m.eval(v, model_completion=True)
        if z3.is_rational_value(val):
            out[name] = Fraction(val.numerator_as_long(), val.denominator_as_long())
            continue
        q = _quadratic_surd(val) if z3.is_algebraic_value(val) else None
        if q is None:
            return Result("unknown", reason="plugin_unknown")   # not exact in our fragment
        out[name] = q
    return Result("sat", out)


def _quadratic_surd(val: z3.AlgebraicNumRef) -> Surd | None:
    """An algebraic number of degree 2 as an exact surd (the evaluator re-checks it)."""
    coeffs = [z3.simplify(c) for c in val.poly()]
    if len(coeffs) != 3 or not all(z3.is_rational_value(c) for c in coeffs):
        return None
    c0, c1, c2 = (Fraction(c.numerator_as_long(), c.denominator_as_long()) for c in coeffs)
    disc = c1 * c1 - 4 * c2 * c0
    if c2 == 0 or disc < 0:
        return None
    try:
        root = Surd.sqrt(disc)
    except SurdError:
        return None
    lo, hi = (Surd.of(-c1) - root) * Surd.of(1 / (2 * c2)), \
        (Surd.of(-c1) + root) * Surd.of(1 / (2 * c2))
    if c2 < 0:
        lo, hi = hi, lo
    return lo if val.index() == 1 else hi


def variables(f: CF, out: set[str] | None = None) -> set[str]:
    out = set() if out is None else out
    if f[0] == "atom":
        p = f[2]
        assert isinstance(p, Poly)
        out.update(v for m, _ in p.terms for v, _ in m)
    elif f[0] in ("and", "or"):
        parts = f[1]
        assert isinstance(parts, (frozenset, tuple))
        for x in parts:
            variables(x, out)
    return out
