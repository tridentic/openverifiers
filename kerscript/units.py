"""KDScript unit table + dimension algebra — portable unit references.

Units are referenced by TOKEN in KDScript documents. This table maps tokens
to SI dimension vectors + scales; it mirrors `domains/units_si.py` plus the
composite constants the physics grammar uses. The IR stores only the
dimension/scale record, never a Python class.

Composites are written as expressions over tokens:
    "N*m^2/C^2"  ->  Newton * Meter^2 / Coulomb^2
"""
from __future__ import annotations

import re
from typing import Optional

from openverifiers.units import Dimension, Unit

_FIELDS = ("length", "mass", "time", "current", "temperature", "amount",
           "luminous")

_BASE_DIMS = ("length", "mass", "time", "current", "temperature", "amount",
              "luminous")


def base_unit(dim: str) -> Unit:
    """`base(length)` — the defining SI base dimension."""
    if dim not in _BASE_DIMS:
        raise KeyError(f"unknown SI base dimension {dim!r}")
    return Unit(dimension=dimension(_d(**{dim: 1})))


def derive_unit(name: str, expr: str) -> tuple[dict, float]:
    """Parse `kg * m / s^2` (and `base(length)`) over the token table.

    Returns the (dimension fields, scale) record for `name`. Scale composes
    through multiplication/division, so `km / s` keeps the 1000 scale.
    """
    expr = expr.strip()
    m = re.match(r"^base\((\w+)\)$", expr)
    if m:
        u = base_unit(m.group(1))
        return ({f: getattr(u.dimension, f) for f in _FIELDS}, u.scale)
    fields: dict[str, int] = {f: 0 for f in _FIELDS}
    scale = 1.0
    for term in expr.split("/"):
        for factor in term.split("*"):
            factor = factor.strip()
            p = factor.split("^")
            tok = p[0].strip()
            if tok not in _TABLE:
                raise KeyError(
                    f"deriving {name!r}: unknown unit factor {tok!r}")
            tf, ts = _TABLE[tok]
            exp = int(p[1]) if len(p) > 1 else 1
            for f in _FIELDS:
                fields[f] += tf.get(f, 0) * exp
            scale *= ts ** exp
    return fields, scale


def _d(**kw) -> dict:
    return {f: kw.get(f, 0) for f in _FIELDS}


# -- token -> (dimension fields, scale) -------------------------------------
_TABLE: dict[str, tuple[dict, float]] = {
    "dimless": (_d(), 1.0),
    "m": (_d(length=1), 1.0),
    "kg": (_d(mass=1), 1.0),
    "s": (_d(time=1), 1.0),
    "A": (_d(current=1), 1.0),
    "K": (_d(temperature=1), 1.0),
    "mol": (_d(amount=1), 1.0),
    "cd": (_d(luminous=1), 1.0),
    "km": (_d(length=1), 1000.0),
    "USD": (_d(), 1.0),
    "m/s": (_d(length=1, time=-1), 1.0),
    "m/s^2": (_d(length=1, time=-2), 1.0),
    "kg m/s": (_d(mass=1, length=1, time=-1), 1.0),
    "N": (_d(mass=1, length=1, time=-2), 1.0),
    "J": (_d(mass=1, length=2, time=-2), 1.0),
    "W": (_d(mass=1, length=2, time=-3), 1.0),
    "Hz": (_d(time=-1), 1.0),
    "C": (_d(current=1, time=1), 1.0),
    "V": (_d(mass=1, length=2, time=-3, current=-1), 1.0),
    "ohm": (_d(mass=1, length=2, time=-3, current=-2), 1.0),
    "T": (_d(mass=1, time=-2, current=-1), 1.0),
    "Wb": (_d(mass=1, length=2, time=-2, current=-1), 1.0),
    "F": (_d(mass=-1, length=-2, time=4, current=2), 1.0),
    "Pa": (_d(mass=1, length=-1, time=-2), 1.0),
    # composites used by the physics grammar
    "angle": (_d(), 1.0),           # degrees convention
    "count": (_d(), 1.0),
    "r_index": (_d(), 1.0),
    "mu_coef": (_d(), 1.0),
    "k_coulomb": (_d(mass=1, length=3, time=-4, current=-2), 1.0),
    "g_newton": (_d(mass=-1, length=3, time=-2), 1.0),
    "rho_res": (_d(mass=1, length=3, time=-3, current=-2), 1.0),
    "area": (_d(length=2), 1.0),
    "volume": (_d(length=3), 1.0),
    "specific_heat": (_d(length=2, time=-2, temperature=-1), 1.0),
    "gas_r": (_d(mass=1, length=2, time=-2, temperature=-1, amount=-1), 1.0),
    "per_kelvin": (_d(temperature=-1), 1.0),
    "heat_cap": (_d(length=2, time=-2), 1.0),
    "photon_h": (_d(mass=1, length=2, time=-1), 1.0),
    "el_field": (_d(mass=1, length=1, time=-3, current=-1), 1.0),
    "diopter": (_d(length=-1), 1.0),
    "N/m": (_d(mass=1, time=-2), 1.0),
    "kg/m": (_d(mass=1, length=-1), 1.0),
}

_dim_cache: dict[tuple, Dimension] = {}
_reverse: Optional[dict] = None


def dimension(d: dict) -> Dimension:
    key = tuple(d.get(f, 0) for f in _FIELDS)
    if key not in _dim_cache:
        _dim_cache[key] = Dimension(**{f: d.get(f, 0) for f in _FIELDS})
    return _dim_cache[key]


def to_ir(unit: Unit) -> dict:
    """Unit -> IR unit record {dimension, scale}."""
    return {
        "dimension": {f: getattr(unit.dimension, f) for f in _FIELDS},
        "scale": unit.scale,
    }


def from_record(rec: dict) -> Unit:
    return Unit(dimension=dimension(rec["dimension"]), scale=rec.get(
        "scale", 1.0))


def resolve_token(token: str) -> Unit:
    """Token -> Unit, building composites from the expression grammar."""
    if token not in _TABLE:
        raise KeyError(f"unknown unit token {token!r}")
    fields, scale = _TABLE[token]
    return Unit(dimension=dimension(fields), scale=scale)


def token_of(unit: Unit) -> str:
    """Unit -> token (reverse lookup; synthesizes U(dimstr) if unnamed)."""
    global _reverse
    if _reverse is None:
        _reverse = {}
        for tok, (fields, scale) in _TABLE.items():
            _reverse[(tuple(fields.get(f, 0) for f in _FIELDS), scale)] = tok
    key = (tuple(getattr(unit.dimension, f) for f in _FIELDS), unit.scale)
    if unit.dimension.is_dimensionless:
        return "dimless"
    return _reverse.get(key, f"U({unit.dimension})")