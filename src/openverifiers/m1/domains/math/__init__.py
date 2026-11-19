"""Math domain pack: arithmetic and algebra with unit/dimension checking.

Fact types
  quantity   number ``value`` + ``unit`` string (see ``units.py``); optional
             ``attributes.symbol`` names the variable it stands for.
  equation   ``value`` is ``"lhs = rhs"`` over numbers and variable names.

Transformations (all hard except ``constant.lookup``)
  arith.add / arith.sub        same dimension required; result in a's unit
  arith.mul / arith.div        dimensions compose; result in SI units
  <formula>.solve_<var>        one per variable of each registered formula
                               (``d = v*t`` gives solve_d, solve_v, solve_t);
                               inputs must have the formula's dimensions;
                               sympy solves, a residual check re-verifies
  algebra.solve_linear         one-variable linear equation; sympy solves,
                               z3 proves the solution exists and is unique
  constant.lookup  (grounded)  a constant read from a cited source; the
                               source line must state exactly that value

Quantities compare equal when owners match, dimensions match and SI values
agree to rel 1e-9, so ``1 km`` equals ``1000 m``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import sympy
import z3

from openverifiers.m1.kernel import DomainPack, Fact, FactType, Precondition, Transformation
from openverifiers.m1.kernel.model import Inputs, Params

from . import units

# ---- fact types ---------------------------------------------------------------


def _is_number(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def _validate_quantity(f: Fact) -> str | None:
    if not _is_number(f.value):
        return f"value {f.value!r} is not a finite number"
    try:
        units.parse(f.unit)
    except ValueError as exc:
        return str(exc)
    return None


def _quantity_equal(a: Fact, b: Fact) -> bool:
    if a.type != b.type or a.owner != b.owner:
        return False
    if not (_is_number(a.value) and _is_number(b.value)):
        return False
    try:
        (sa, da), (sb, db) = units.parse(a.unit), units.parse(b.unit)
    except ValueError:
        return False
    return da == db and math.isclose(a.value * sa, b.value * sb, rel_tol=1e-9, abs_tol=1e-12)


_SAFE = re.compile(r"^[0-9A-Za-z_ .+\-*/()^]+$")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_GLOBALS: dict[str, Any] = {"__builtins__": {}, "Integer": sympy.Integer,
                            "Float": sympy.Float, "Rational": sympy.Rational,
                            "Symbol": sympy.Symbol}


def parse_side(text: str) -> sympy.Expr:
    """Parse untrusted arithmetic text. Character allowlist, no dunders, every
    identifier becomes a plain real Symbol (so ``E``/``I`` are not constants),
    and evaluation sees no builtins."""
    if not _SAFE.match(text) or "__" in text:
        raise ValueError(f"expression {text!r} has characters outside [0-9A-Za-z_.+-*/()^ ]")
    local = {n: sympy.Symbol(n, real=True) for n in _IDENT.findall(text)}
    expr = sympy.parse_expr(text.replace("^", "**"), local_dict=local, global_dict=_GLOBALS)
    if not isinstance(expr, sympy.Expr):
        raise ValueError(f"{text!r} is not an arithmetic expression")
    return expr


def parse_equation(text: Any) -> tuple[sympy.Expr, sympy.Expr]:
    if not isinstance(text, str) or text.count("=") != 1:
        raise ValueError(f"equation {text!r} must be a string with exactly one '='")
    lhs, rhs = text.split("=")
    return parse_side(lhs), parse_side(rhs)


def _validate_equation(f: Fact) -> str | None:
    try:
        parse_equation(f.value)
    except (ValueError, SyntaxError, TypeError) as exc:
        return str(exc)
    return None


def quantity(fid: str, value: float, unit: str | None, symbol: str | None = None,
             **kw: Any) -> Fact:
    attrs = {"symbol": symbol} if symbol else {}
    return Fact(id=fid, type="quantity", value=value, unit=unit, attributes=attrs, **kw)


def _exact(x: float) -> sympy.Rational:
    return sympy.Rational(repr(float(x)))


# ---- arithmetic -------------------------------------------------------------------


def _same_dimension(i: Inputs, p: Params) -> str | None:
    da, db = units.dimension(i["a"].unit), units.dimension(i["b"].unit)
    if da != db:
        return (f"{i['a'].id} is {i['a'].unit!r} ({units.si_unit(da)}) but {i['b'].id} is "
                f"{i['b'].unit!r} ({units.si_unit(db)})")
    return None


def _nonzero_divisor(i: Inputs, p: Params) -> str | None:
    return None if i["b"].value != 0 else f"divisor {i['b'].id} is zero"


def _addsub(sign: int) -> Any:
    def effect(i: Inputs, p: Params) -> Mapping[str, Fact]:
        a, b = i["a"], i["b"]
        sa, sb = units.parse(a.unit)[0], units.parse(b.unit)[0]
        value = a.value + sign * b.value * sb / sa
        return {"result": quantity("_", value, a.unit, owner=a.owner)}
    return effect


def _muldiv(sign: int) -> Any:
    def effect(i: Inputs, p: Params) -> Mapping[str, Fact]:
        (sa, da), (sb, db) = units.parse(i["a"].unit), units.parse(i["b"].unit)
        va, vb = i["a"].value * sa, i["b"].value * sb
        value = va * vb if sign > 0 else va / vb
        return {"result": quantity("_", value, units.si_unit(units.mul(da, db, sign)))}
    return effect


# ---- formulas -------------------------------------------------------------------


@dataclass(frozen=True)
class Formula:
    """A trusted relation. ``dims`` gives each variable's unit (for its
    dimension); ``nonnegative`` variables reject negative inputs and select
    the non-negative root when solving (e.g. speed from kinetic energy)."""

    name: str
    equation: str
    dims: Mapping[str, str]
    nonnegative: frozenset[str] = frozenset()


FORMULAS: tuple[Formula, ...] = (
    Formula("kinematics.distance", "d = v*t", {"d": "m", "v": "m/s", "t": "s"},
            frozenset({"t"})),
    Formula("kinematics.velocity", "v = u + a*t", {"v": "m/s", "u": "m/s", "a": "m/s^2",
                                                    "t": "s"}, frozenset({"t"})),
    Formula("kinematics.displacement", "s = u*t + a*t^2/2",
            {"s": "m", "u": "m/s", "a": "m/s^2", "t": "s"}, frozenset({"t"})),
    Formula("dynamics.newton2", "F = m*a", {"F": "N", "m": "kg", "a": "m/s^2"},
            frozenset({"m"})),
    Formula("energy.kinetic", "E = m*v^2/2", {"E": "J", "m": "kg", "v": "m/s"},
            frozenset({"m", "v", "E"})),
    Formula("energy.potential", "E = m*g*h", {"E": "J", "m": "kg", "g": "m/s^2", "h": "m"},
            frozenset({"m"})),
    Formula("electric.ohm", "V = I*R", {"V": "V", "I": "A", "R": "ohm"}, frozenset({"R"})),
)


def _formula_transformations(fm: Formula) -> list[Transformation]:
    lhs, rhs = parse_equation(fm.equation)
    sym = {n: sympy.Symbol(n, real=True) for n in fm.dims}
    out: list[Transformation] = []

    for target in fm.dims:
        roles = [v for v in fm.dims if v != target]

        def dims_ok(i: Inputs, p: Params, roles: list[str] = roles) -> str | None:
            bad = [f"{r}={i[r].id} has unit {i[r].unit!r}, needs dimension of {fm.dims[r]!r}"
                   for r in roles
                   if units.dimension(i[r].unit) != units.dimension(fm.dims[r])]
            return "; ".join(bad) or None

        def domain_ok(i: Inputs, p: Params, roles: list[str] = roles) -> str | None:
            neg = [r for r in roles if r in fm.nonnegative and i[r].value < 0]
            return f"{neg} must be non-negative" if neg else None

        def effect(i: Inputs, p: Params, target: str = target,
                   roles: list[str] = roles) -> Mapping[str, Fact]:
            subs = {sym[r]: _exact(units.to_si(i[r].value, i[r].unit)) for r in roles}
            roots = [s for s in sympy.solve(sympy.Eq(lhs.subs(subs), rhs.subs(subs)), sym[target])
                     if s.is_real]
            if target in fm.nonnegative:
                roots = [s for s in roots if s >= 0]
            if len(roots) != 1:
                raise ValueError(f"{fm.equation} has {len(roots)} admissible solutions for "
                                 f"{target} with these inputs")
            unit = units.si_unit(units.dimension(fm.dims[target]))
            return {target: quantity("_", float(roots[0]), unit, symbol=target)}

        def residual(i: Inputs, p: Params, o: Mapping[str, Fact],
                     target: str = target, roles: list[str] = roles) -> str | None:
            vals = {sym[r]: _exact(units.to_si(i[r].value, i[r].unit)) for r in roles}
            res = o[target]
            vals[sym[target]] = _exact(units.to_si(res.value, res.unit))
            left, right = float(lhs.subs(vals)), float(rhs.subs(vals))
            if math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12):
                return None
            return f"substituting back: {lhs} = {left} but {rhs} = {right}"

        out.append(Transformation(
            f"{fm.name}.solve_{target}", "hard",
            inputs=dict.fromkeys(roles, "quantity"), outputs={target: "quantity"},
            preconditions=(Precondition("dimensions", dims_ok),
                           Precondition("domain", domain_ok)),
            effect=effect, checker=residual,
            doc=f"{fm.equation}, solved for {target}"))
    return out


# ---- linear algebra with z3 -----------------------------------------------------------


def _linear(i: Inputs) -> tuple[sympy.Symbol, sympy.Expr, sympy.Expr]:
    lhs, rhs = parse_equation(i["equation"].value)
    expr = sympy.expand(lhs - rhs)
    free = sorted(expr.free_symbols, key=str)
    if len(free) != 1:
        raise ValueError(f"needs exactly one unknown, found {[str(s) for s in free]}")
    x = free[0]
    poly = sympy.Poly(expr, x)
    if poly.degree() != 1:
        raise ValueError(f"not linear in {x} (degree {poly.degree()})")
    a, b = poly.all_coeffs()
    return x, a, b


def _linear_ok(i: Inputs, p: Params) -> str | None:
    try:
        _linear(i)
    except (ValueError, SyntaxError, TypeError, sympy.PolynomialError) as exc:
        return str(exc)
    return None


def _solve_linear(i: Inputs, p: Params) -> Mapping[str, Fact]:
    x, a, b = _linear(i)
    return {"solution": quantity("_", float(-b / a), "1", symbol=str(x))}


def _z3_unique(i: Inputs, p: Params, o: Mapping[str, Fact]) -> str | None:
    x, a, b = _linear(i)
    z = z3.Real(str(x))
    s = z3.Solver()
    s.add(z3.RealVal(str(a)) * z + z3.RealVal(str(b)) == 0)
    if s.check() != z3.sat:
        return "z3: equation has no solution"
    root = s.model()[z]
    s.add(z != root)
    if s.check() != z3.unsat:
        return "z3: solution is not unique"
    exact = root.as_fraction()
    claimed = o["solution"].value
    if not math.isclose(float(exact), claimed, rel_tol=1e-9, abs_tol=1e-12):
        return f"z3: unique solution is {exact}, claimed {claimed}"
    return None


# ---- grounded constants -------------------------------------------------------------------

SOURCES: dict[str, str] = {
    "codata:g_n": "standard acceleration of gravity: g = 9.80665 m/s^2",
    "codata:c": "speed of light in vacuum: c = 299792458 m/s",
    "codata:e": "elementary charge: e = 1.602176634e-19 C",
}
_STATED = re.compile(r"(\w+)\s*=\s*([-+0-9.eE]+)\s+(\S+)\s*$")


def _source_states(i: Inputs, p: Params, o: Mapping[str, Fact]) -> str | None:
    f = o["value"]
    cite = f.provenance.citation if f.provenance else None
    m = _STATED.search(SOURCES.get(cite or "", ""))
    if m is None:
        return f"source {cite!r} states no value"
    stated = quantity("_", float(m.group(2)), m.group(3), owner=f.owner)
    if f.attributes.get("symbol") not in (None, m.group(1)):
        return f"source {cite!r} defines {m.group(1)}, not {f.attributes['symbol']}"
    if not _quantity_equal(stated, f):
        return f"source {cite!r} states {m.group(2)} {m.group(3)}, claimed {f.value} {f.unit}"
    return None


# ---- predicates ---------------------------------------------------------------------------


def _has_dimension(f: Fact, args: Params) -> str | None:
    want = units.dimension(args["unit"])
    got = units.dimension(f.unit)
    return None if got == want else (f"dimension {units.si_unit(got)}, expected "
                                     f"{units.si_unit(want)}")


def _approx(f: Fact, args: Params) -> str | None:
    want = quantity("_", args["value"], args.get("unit", f.unit), owner=f.owner)
    tol = float(args.get("rel_tol", 1e-6))
    if units.dimension(want.unit) != units.dimension(f.unit):
        return f"unit {f.unit!r} is not comparable with {want.unit!r}"
    got_si, want_si = units.to_si(f.value, f.unit), units.to_si(want.value, want.unit)
    ok = math.isclose(got_si, want_si, rel_tol=tol, abs_tol=1e-12)
    return None if ok else f"{f.value} {f.unit} is not within {tol} of {want.value} {want.unit}"


# ---- the pack -------------------------------------------------------------------------------

_Q2 = {"a": "quantity", "b": "quantity"}
_TRANSFORMATIONS: list[Transformation] = [
    Transformation("arith.add", "hard", _Q2, {"result": "quantity"},
                   preconditions=(Precondition("same_dimension", _same_dimension),),
                   effect=_addsub(+1), doc="a + b, in a's unit"),
    Transformation("arith.sub", "hard", _Q2, {"result": "quantity"},
                   preconditions=(Precondition("same_dimension", _same_dimension),),
                   effect=_addsub(-1), doc="a - b, in a's unit"),
    Transformation("arith.mul", "hard", _Q2, {"result": "quantity"},
                   effect=_muldiv(+1), doc="a * b, in SI units"),
    Transformation("arith.div", "hard", _Q2, {"result": "quantity"},
                   preconditions=(Precondition("nonzero_divisor", _nonzero_divisor),),
                   effect=_muldiv(-1), doc="a / b, in SI units"),
    Transformation("algebra.solve_linear", "hard", {"equation": "equation"},
                   {"solution": "quantity"},
                   preconditions=(Precondition("linear_in_one_unknown", _linear_ok),),
                   effect=_solve_linear, checker=_z3_unique,
                   doc="solve a*x + b = 0; z3 proves existence and uniqueness"),
    Transformation("constant.lookup", "grounded", {}, {"value": "quantity"},
                   checker=_source_states, doc="a constant stated by a cited source"),
]
for _fm in FORMULAS:
    _TRANSFORMATIONS.extend(_formula_transformations(_fm))

PACK = DomainPack(
    name="math",
    fact_types={
        "quantity": FactType("quantity", validate=_validate_quantity, equal=_quantity_equal),
        "equation": FactType("equation", validate=_validate_equation),
    },
    transformations={t.id: t for t in _TRANSFORMATIONS},
    predicates={"has_dimension": _has_dimension, "approx": _approx},
    sources=SOURCES,
)
