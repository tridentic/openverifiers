"""OpenVerifiers — physics domain grammar (kinematics + basic mechanics).

Manual grammar per ARCHITECTURE.md §5 (manual specification preferred/default).

Fact kinds (id → symbol, dimension):
    initial_velocity u  [L T^-1]
    final_velocity   v  [L T^-1]
    time             t  [T]
    acceleration     a  [L T^-2]
    displacement     s  [L]
    mass             m  [M]
    force            F  [L M T^-2]
    kinetic_energy   K  [L^2 M T^-2]
    work             W  [L^2 M T^-2]

Rules (output kind → relation, input kinds, solver):
    v = u + a t
    v^2 = u^2 + 2 a s
    s = u t + (1/2) a t^2
    s = (u + v)/2 * t
    F = m a
    a = F / m
    m = F / a
    K = (1/2) m v^2
    W = F s

Dimension checking is enforced in every rule precondition: each input fact must
carry the expected dimension; otherwise the rule is rejected with a recorded reason.
"""

from __future__ import annotations

from typing import Any, Optional

import sympy as sp

from ..model import Fact, Transformation, UNVERIFIED_TRUTH, TARGET
from ..solvers import DIM, D_LENGTH, D_TIME, D_VELOCITY, D_ACCEL, D_FORCE, D_MASS, D_ENERGY, dim_eq, get_solver


# ---------------------------------------------------------------------------
# Fact-kind registry
# ---------------------------------------------------------------------------
KIND_META: dict[str, dict] = {
    "initial_velocity": {"symbol": "u", "dim": D_VELOCITY,   "unit": "m/s"},
    "final_velocity":   {"symbol": "v", "dim": D_VELOCITY,   "unit": "m/s"},
    "time":             {"symbol": "t", "dim": D_TIME,       "unit": "s"},
    "acceleration":     {"symbol": "a", "dim": D_ACCEL,      "unit": "m/s^2"},
    "displacement":     {"symbol": "s", "dim": D_LENGTH,     "unit": "m"},
    "mass":             {"symbol": "m", "dim": D_MASS,       "unit": "kg"},
    "force":            {"symbol": "F", "dim": D_FORCE,      "unit": "N"},
    "kinetic_energy":   {"symbol": "K", "dim": D_ENERGY,     "unit": "J"},
    "work":             {"symbol": "W", "dim": D_ENERGY,     "unit": "J"},
}

DEFAULT_ID = {
    "initial_velocity": "u", "final_velocity": "v", "time": "t",
    "acceleration": "a", "displacement": "s", "mass": "m", "force": "F",
    "kinetic_energy": "K", "work": "W",
}


def symbol_for(kind: str) -> str:
    return KIND_META[kind]["symbol"]


def dimension_for(kind: str) -> dict:
    return KIND_META[kind]["dim"]


# ---------------------------------------------------------------------------
# rule builders
# ---------------------------------------------------------------------------
def make_fact(kind: str, value: Any, status: str = UNVERIFIED_TRUTH,
              note: str = "") -> Fact:
    meta = KIND_META[kind]
    return Fact(
        id=DEFAULT_ID[kind],
        value=value,
        status=status,
        attributes={
            "fact_kind": kind,
            "symbol": meta["symbol"],
            "dimension": meta["dim"],
            "unit": meta["unit"],
        },
        source=note or f"given {kind}",
    )


def make_rule(name: str, output_kind: str, input_kinds: list[str],
              relation_expr: sp.Expr | str, *, doc: str = "") -> Transformation:
    """Build a Transformation with dimension-enforcing precondition and a
    solver-backed relation.

    relation_expr: sympy expression equal to zero, e.g. sp.Eq(v, u + a*t).lhs - rhs.
    """

    out_meta = KIND_META[output_kind]
    out_dim = out_meta["dim"]

    def precondition(inputs: list[Fact]) -> Optional[str]:
        if len(inputs) != len(input_kinds):
            return f"arity: expected {len(input_kinds)} inputs, got {len(inputs)}"
        for fact, expected_kind in zip(inputs, input_kinds):
            got_dim = fact.attributes.get("dimension")
            expected_dim = dimension_for(expected_kind)
            if not dim_eq(got_dim, expected_dim):
                return (f"dimension mismatch: {fact.id} ({fact.attributes.get('fact_kind')}) "
                        f"is {got_dim}, expected {expected_dim}")
        return None

    def relation(inputs: list[Fact]) -> tuple[Fact, str]:
        # map input facts to their symbols, gather solver givens
        given: dict[str, Any] = {}
        for fact, kind in zip(inputs, input_kinds):
            given[symbol_for(kind)] = fact.value
        solver = get_solver("sympy.algebra")
        target_sym = symbol_for(output_kind)
        value, note = solver(relation_expr, given, target_sym)
        out = make_fact(output_kind, value, status="derived",
                        note=f"via {name}")
        return out, note

    t = Transformation(name, output_kind=output_kind, input_kinds=input_kinds,
                       precondition=precondition, relation=relation,
                       solver_hook="sympy.algebra", doc=doc)
    return t


# ---------------------------------------------------------------------------
# the rule library
# ---------------------------------------------------------------------------


def build_physics_rules() -> list[Transformation]:
    v, u, a, t, s, m, F, K, W = sp.symbols("v u a t s m F K W")
    rules = [
        make_rule("kinematics.v_u_at", "final_velocity", ["initial_velocity", "acceleration", "time"],
                                    v - (u + a*t),
                  doc="v = u + a t"),
        make_rule("kinematics.v2_u2_2as", "final_velocity", ["initial_velocity", "acceleration", "displacement"],
                                    v**2 - (u**2 + 2*a*s),
                  doc="v^2 = u^2 + 2 a s"),
        make_rule("kinematics.s_ut_half_at2", "displacement", ["initial_velocity", "time", "acceleration"],
                                    s - (u*t + sp.Rational(1, 2)*a*t**2),
                  doc="s = u t + (1/2) a t^2"),
        make_rule("kinematics.s_avg_v_t", "displacement", ["initial_velocity", "final_velocity", "time"],
                                    s - ((u + v)/2 * t),
                  doc="s = (u+v)/2 * t"),
        make_rule("kinematics.t_v_u_over_a", "time", ["initial_velocity", "final_velocity", "acceleration"],
                                    t - (v - u)/a,
                  doc="t = (v-u)/a"),
        make_rule("dynamics.F_ma", "force", ["mass", "acceleration"],
                                    F - m*a,
                  doc="F = m a"),
        make_rule("dynamics.a_F_over_m", "acceleration", ["force", "mass"],
                                    a - F/m,
                  doc="a = F / m"),
        make_rule("dynamics.m_F_over_a", "mass", ["force", "acceleration"],
                                    m - F/a,
                  doc="m = F / a"),
        make_rule("energy.KE_half_mv2", "kinetic_energy", ["mass", "final_velocity"],
                                    K - sp.Rational(1, 2)*m*v**2,
                  doc="K = (1/2) m v^2"),
        make_rule("energy.W_Fs", "work", ["force", "displacement"],
                                    W - F*s,
                  doc="W = F s"),
    ]
    return rules