"""OpenVerifiers — solver hooks.

A rule's relation is resolved by a solver backend. This module owns the registry
and the symbolic (sympy) algebra backend used by the physics slice.

Design: a `solve(relation, given)` call receives a symbolic relation and a dict of
known values, and produces either a concrete value for the unknown, or a symbolic
fact if the target is a symbolic answer. Keep this layer backend-agnostic; the core
engine never imports sympy directly.
"""

from __future__ import annotations

import sympy as sp
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Dimensions — linear basis as dicts
#   L (length), M (mass), T (time)
# ADT: a dimension is a dict {symbol: exponent}
# ---------------------------------------------------------------------------
DIM = {"L": 0, "M": 0, "T": 0}
D_LENGTH = {"L": 1, "M": 0, "T": 0}
D_TIME = {"L": 0, "M": 0, "T": 1}
D_VELOCITY = {"L": 1, "M": 0, "T": -1}
D_ACCEL = {"L": 1, "M": 0, "T": -2}
D_FORCE = {"L": 1, "M": 1, "T": -2}
D_MASS = {"L": 0, "M": 1, "T": 0}
D_ENERGY = {"L": 2, "M": 1, "T": -2}


def dim_add(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v
    return {k: v for k, v in out.items() if v}


def dim_sub(a: dict, b: dict) -> dict:
    return dim_add(a, {k: -v for k, v in b.items()})


def dim_eq(a: dict, b: dict) -> bool:
    return {k: v for k, v in a.items() if v} == {k: v for k, v in b.items() if v}


# ---------------------------------------------------------------------------
# Sympy algebra backend
# ---------------------------------------------------------------------------
def solve_symbolic(relation: sp.Expr, given: dict[str, Any], target: str,
                   tolerance: Optional[float] = None) -> tuple[Any, str]:
    """Solve `relation == 0` for symbol `target` using known `given`.

    Returns (value, note). value may be a sympy expression (symbolic answer) or
    a Python float/int/str when numeric.
    """
    # relation: sympy expression set equal to zero (LHS - RHS)
    expr = sp.sympify(relation)
    # substitute knowns
    subs = {}
    for k, v in given.items():
        subs[k] = sp.sympify(v)
    expr_s = expr.subs(subs)
    sym = sp.Symbol(target)
    try:
        solutions = sp.solve(expr_s, sym)
    except Exception as exc:  # solver can raise for non-algebraic shapes
        return None, f"solver error: {exc}"
    if not solutions:
        return None, "no solution: relation unsatisfiable or inconsistent with givens"
    # physics magnitude convention: prefer a positive real root for velocity-like
    # targets (v^2 = ... has ± roots; textbook problems expect the positive one)
    real = [s for s in solutions if s.is_real]
    if real:
        pos = [float(s.evalf()) for s in real if float(s.evalf()) > 0]
        if pos:
            val = sp.sympify(min(pos))
        else:
            val = real[0]
    else:
        val = solutions[0]
    # prefer numeric
    if val.is_number:
        val_f = float(val.evalf())
        if tolerance is not None:
            rounded = round(val_f, int(abs(__import__("math").log10(tolerance))))
            return rounded, f"numeric {rounded}"
        return val_f, f"numeric {val_f}"
    # symbolic
    return sp.simplify(val), f"symbolic {sp.simplify(val)}"


# registry: solver_hook token -> callable(relation, given, target) -> (value,note)
SOLVERS = {
    "sympy.algebra": solve_symbolic,
}


def get_solver(hook: str):
    if hook not in SOLVERS:
        raise ValueError(f"unknown solver hook {hook!r}; known: {sorted(SOLVERS)}")
    return SOLVERS[hook]