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
    "z3.sat": "z3.sat",  # populated lazily below so z3 import is optional
}


def get_solver(hook: str):
    if hook not in SOLVERS:
        raise ValueError(f"unknown solver hook {hook!r}; known: {sorted(SOLVERS)}")
    if hook == "z3.sat" and not isinstance(SOLVERS[hook], str):
        return SOLVERS[hook]
    if hook == "z3.sat":
        try:
            import z3 as _z3  # lazy; conversion referenced below  # noqa
            _ = _z3
        except ImportError:
            raise ImportError("z3-solver is required for the z3.sat hook; pip install z3-solver")
        SOLVERS[hook] = _build_z3_solver()
        return SOLVERS[hook]
    return SOLVERS[hook]


# ---------------------------------------------------------------------------
# typed quantity solve (built on the typed core: Unit/Dimension/Quantity)
# ---------------------------------------------------------------------------
from .units import to_canonical


def _scalar_value(q, axis):
    """Project a known quantity to a scalar, canonicalized to SI scale.

    A plain float passes through; a Vector3 must be projected along an
    explicit axis (never silently); the result is multiplied by the unit's
    `scale` so cross-unit arithmetic never mixes raw values."""
    v = getattr(q, "value", None)
    if isinstance(v, (int, float)):
        return to_canonical(float(v), q.unit)
    if hasattr(v, "component"):
        if axis is None:
            raise ValueError(
                "vector input requires an explicit axis= argument — no "
                "silent flattening")
        return to_canonical(float(v.component(axis)), q.unit)
    return v


def solve_quantity(relation: sp.Expr, target_var: str, target_unit,
                   knowns: dict[str, Any],
                   dimensions: dict[str, Any],
                   *, shared_owner: bool = False, axis: Optional[int] = None,
                   tolerance: Optional[float] = None,
                   derivation=None, result_id: Optional[str] = None):
    """Solve `relation == 0` for `target_var` given typed `knowns`.

    Checks, in order:
      1. every known Quantity's dimension matches its declared variable
         dimension (DimensionMismatchError on failure),
      2. if `shared_owner`, all owned knowns must share one owner
         (OwnerMismatchError on failure),
      3. the equation is actually solvable for `target_var`
         (SolveError otherwise).

    Returns a `Quantity` with the target variable's declared unit. No search,
    no registry, no alternate-path logic: exactly the one equation, exactly the
    one named target.
    """
    from .errors import DimensionMismatchError, OwnerMismatchError, SolveError

    for var, q in knowns.items():
        if q is None:
            continue
        if q.dimension != dimensions[var]:
            raise DimensionMismatchError(
                f"dimension mismatch: {var} has {q.unit.dimension}, declared "
                f"{dimensions[var]} (unit {q.unit!r})")
    if shared_owner:
        owners = {q.owner for q in knowns.values()
                  if q is not None and q.owner is not None}
        if len(owners) > 1:
            raise OwnerMismatchError(
                f"owner mismatch: inputs declare different owners "
                f"{sorted(str(o) for o in owners)} — they must share one "
                f"physical object")

    expr = sp.sympify(relation)
    subs = {sp.Symbol(var): sp.sympify(_scalar_value(q, axis))
            for var, q in knowns.items() if q is not None}
    expr_s = expr.subs(subs)
    target_sym = sp.Symbol(target_var)
    try:
        solutions = sp.solve(expr_s, target_sym)
    except Exception as exc:
        raise SolveError(f"solver error: {exc}") from exc
    if not solutions:
        raise SolveError(
            "no solution: equation is inconsistent with the known values")

    # physics-magnitude convention: prefer a positive real root (v^2 = ...
    # has two roots; textbook problems want the positive one)
    real = [float(s.evalf()) for s in solutions if s.is_real]
    if real:
        positives = [v for v in real if v > 0]
        val = min(positives) if positives else real[0]
    else:
        raise SolveError(
            f"no real solution for {target_var} from the known values")

    if tolerance is not None:
        val = round(val, int(abs(__import__("math").log10(tolerance))))
    # solve happened in canonical scale; express the answer in the target
    # unit's own scale
    val = val / target_unit.scale

    from .facts import Quantity
    # A single construction with provenance already attached: the post-init
    # recorder sees a derived fact, so controller outputs never trip the
    # freeze "no new given facts" guard.
    return Quantity(id=result_id or target_var, value=val, unit=target_unit,
                    status="derived", derivation=derivation)


# ---------------------------------------------------------------------------
# Z3 SAT backend — discrete satisifiability + unsat-core extraction
# ---------------------------------------------------------------------------
# domain_spec: {"var": {"type": "enum", "domain": {...}}, ...}
#   "var" can be enum, int, real, bool; enums map to an ordered int encoding.
# constraints: iterable of (name, z3_expr_fn) or (name, sql_like_predicate).
#   We accept either a z3 expression object directly or a callable that, given
#   the z3 variable map, returns a z3 BoolRef.
#
# Returns a structured SAT/UNSAT verdict with the minimal-U Snat core on UNSAT
# (the minimal subset of constraint names that jointly block a model).

def _build_z3_solver():
    import z3

    def _mk_vars(domain_spec):
        """Create z3 variables for each declared var, returning {name: z3 expr}."""
        z3vars = {}
        enc = {}  # for enums: var -> {label: int}
        for name, spec in domain_spec.items():
            t = spec.get("type", "int")
            if t == "bool":
                z3vars[name] = z3.Bool(name)
            elif t == "real":
                z3vars[name] = z3.Real(name)
            elif t == "enum":
                domain = spec["domain"]
                ordered = list(domain)
                _map = {label: i for i, label in enumerate(ordered)}
                enc[name] = _map
                enc[f"{name}__rev"] = {i: label for label, i in _map.items()}
                z3vars[name] = z3.Int(name)
            else:  # int
                z3vars[name] = z3.Int(name)
        return z3vars, enc

    def solve_sat(domain_spec, constraints, candidate=None, target=None,
                  minimize=None):
        """Resolve a discrete satisfiability problem.

        domain_spec: {var: {type, ...}} (see above)
        constraints: list of (name, z3_expr) where z3_expr may be a z3 BoolRef or
          a callable(accessor) -> BoolRef; accessor maps var name to the z3 value,
          plus a method `.at(var)` for enum lookup (returns the int encoding or a
          z3 expr over it).
        candidate: optional {var: value} partial/nominal assignment to assert.
        target: optional var name whose value the solver should ground.
        minimize: optional var name to minimize.

        Returns dict: {status, model, unsat_core(list of names)}.
        """
        z3vars, enc = _mk_vars(domain_spec)

        class Accessor:
            """Readable view of variables for authoring constraints."""
            def at(self, var):
                return z3vars[var]
            def label(self, var):
                # for enums, an int-encoded z3 expr; use with .label() reserved
                return z3vars[var]
            def __getattr__(self, k):
                if k in z3vars:
                    return z3vars[k]
                raise AttributeError(k)

        s = z3.Solver()
        # domain bounds for enums / ints
        for name, spec in domain_spec.items():
            d = z3vars[name]
            if spec.get("type") == "enum":
                n = len(spec["domain"])
                lo, hi = 0, n - 1
                s.add(d >= lo, d <= hi)
            elif spec.get("type") == "int":
                if "min" in spec: s.add(d >= spec["min"])
                if "max" in spec: s.add(d <= spec["max"])

        named = []
        for name, expr in constraints:
            e = expr(z3vars, Accessor()) if callable(expr) else expr
            if e is None:
                continue
            s.assert_and_track(e, name)
            named.append(name)

        if candidate:
            for var, val in candidate.items():
                if var in enc:  # enum: val is label
                    s.add(z3vars[var] == enc[var][val])
                else:
                    s.add(z3vars[var] == val)

        res = {}
        check = s.check()
        res["status"] = "SAT" if check == z3.sat else ("UNSAT" if check == z3.unsat else "UNKNOWN")
        if check == z3.sat:
            m = s.model()
            model = {}
            for name, d in z3vars.items():
                val = m.eval(d)
                if name in enc:  # enum
                    model[name] = enc[f"{name}__rev"][val.as_long()]
                else:
                    try:
                        if z3.is_bool(d): model[name] = bool(val)
                        elif z3.is_real(d): model[name] = float(val.as_fraction())
                        elif z3.is_int(d): model[name] = val.as_long()
                        else: model[name] = str(val)
                    except Exception:
                        model[name] = str(val)
            res["model"] = model
            if target:
                try:
                    res["target_value"] = model[target]
                except KeyError:
                    res["target_value"] = None
        elif check == z3.unsat:
            # extract unsat core (z3 tracks asserted names already)
            core = [str(c) for c in s.unsat_core()]
            res["unsat_core"] = core
        return res

    return solve_sat