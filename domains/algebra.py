"""Algebra grammar — generic symbolic composition primitives.

`equate` closes two expression facts (or an expression and a Quantity)
against a shared variable, producing the numeric Quantity — the ONE generic
"equate two expressions, solve for the common unknown" step the whole
trace-composition story uses. `add` sums expressions/quantities so net-work
style assimilations compose in the trace.

Not syllabus relations; they are the composition OPERATORS the agent authoring
a trace needs. They are still registered whitelist entries with declared
signatures, so the closed-registry discipline holds.
"""

from __future__ import annotations

import sympy as sp

from ..facts import Fact, Quantity, ExpressionFact, DIMENSIONLESS
from ..units import Unit
from ..model import Transformation, ParamTransformation, InputSpec
from ..v2 import Grammar


def _side(fact: Fact):
    if isinstance(fact, ExpressionFact):
        return sp.sympify(fact.expression)
    if isinstance(fact, Quantity) and fact.value is not None:
        return float(fact.value)
    raise ValueError(f"{fact.id}: can only equate ExpressionFact or "
                     f"Quantity sides, got {type(fact).__name__}")


class Equate(ParamTransformation):
    """a == b for a shared free variable -> the numeric Quantity.

    Invoked from the trace as:  x = algebra.equate(a=.., b=..) with variable=t
    (optional `root` = "positive" (default) | "any" | an index).
    """

    def __init__(self):
        super().__init__("equate",
                         doc="solve expression_a == expression_b for variable",
                         param_names=("variable", "root"),
                         inputs=(InputSpec("a"), InputSpec("b")))

    def apply(self, inputs: dict, params: dict | None = None) -> Quantity:
        params = params or {}
        var = sp.Symbol(params.get("variable", "t"))
        lhs, rhs = _side(inputs["a"]), _side(inputs["b"])
        roots = sp.solve(sp.Eq(lhs, rhs), var)
        roots = [r for r in roots if r.is_real]
        if not roots:
            raise ValueError(f"no real solution for {var} in "
                             f"{lhs} == {rhs}")
        mode = params.get("root", "positive")
        if mode == "any":
            val = float(sp.N(roots[0]))
        elif mode == "positive":
            pos = [float(r) for r in roots if float(sp.N(r)) > 0]
            val = pos[0] if pos else min(float(r) for r in roots)
        else:
            val = float(sp.N(roots[int(mode)]))
        unit = getattr(inputs["a"], "unit", None)
        if not isinstance(unit, Unit):
            unit = getattr(inputs["b"], "unit", None)
            if not isinstance(unit, Unit):
                unit = DIMENSIONLESS
        return Quantity(value=val, unit=unit,
                        source=f"equated {lhs} == {rhs} -> {var} = {val:g}")


class Add(Transformation):
    """a + b for ExpressionFacts and Quantities (symbol-aware)."""

    def __init__(self):
        super().__init__("add", doc="sum two sides (symbolic if either is)",
                         inputs=(InputSpec("a"), InputSpec("b")))

    def apply(self, inputs: dict) -> Fact:
        a, b = inputs["a"], inputs["b"]
        sa, sb = _side(a), _side(b)
        total = sp.simplify(sa + sb)
        ua, ub = getattr(a, "unit", None), getattr(b, "unit", None)
        unit = ua if isinstance(ua, Unit) else (ub if isinstance(ub, Unit)
                                                else DIMENSIONLESS)
        if isinstance(a, ExpressionFact) or isinstance(b, ExpressionFact):
            return ExpressionFact(expression=str(total),
                                  variables=tuple(sorted(
                                      {str(ss) for ss in total.free_symbols})),
                                  unit=unit)
        return Quantity(value=float(sp.N(total)), unit=unit)


ALGEBRA = Grammar(
    name="alg",
    doc="Generic symbolic composition operators for trace authoring.",
    transformations={
        "equate": Equate(),
        "add": Add(),
    },
)