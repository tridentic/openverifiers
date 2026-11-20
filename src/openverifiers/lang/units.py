"""Units and quantity types: exact SI dimension vectors with rational factors.

A unit is a factor (to SI base units) and a dimension vector over the seven SI
base dimensions, plus ``USD`` for money. Quantities are stored in base units,
so ``500 g`` and ``0.5 kg`` are the same RawOV term.
"""

from __future__ import annotations

import re
from fractions import Fraction

from ..raw.terms import Dims, make_dims

BASE = ("kg", "m", "s", "A", "K", "mol", "cd", "USD", "deg")


def _d(**e: int) -> Dims:
    return make_dims({k: Fraction(v) for k, v in e.items()})


_F = Fraction
#: name -> (factor to base units, dims)
UNITS: dict[str, tuple[Fraction, Dims]] = {
    "kg": (_F(1), _d(kg=1)), "g": (_F(1, 1000), _d(kg=1)), "mg": (_F(1, 10**6), _d(kg=1)),
    "t": (_F(1000), _d(kg=1)),
    "m": (_F(1), _d(m=1)), "cm": (_F(1, 100), _d(m=1)), "mm": (_F(1, 1000), _d(m=1)),
    "km": (_F(1000), _d(m=1)),
    "s": (_F(1), _d(s=1)), "ms": (_F(1, 1000), _d(s=1)), "min": (_F(60), _d(s=1)),
    "h": (_F(3600), _d(s=1)),
    "A": (_F(1), _d(A=1)), "K": (_F(1), _d(K=1)), "mol": (_F(1), _d(mol=1)),
    "cd": (_F(1), _d(cd=1)),
    "N": (_F(1), _d(kg=1, m=1, s=-2)), "J": (_F(1), _d(kg=1, m=2, s=-2)),
    "kJ": (_F(1000), _d(kg=1, m=2, s=-2)),
    "W": (_F(1), _d(kg=1, m=2, s=-3)), "kW": (_F(1000), _d(kg=1, m=2, s=-3)),
    "Pa": (_F(1), _d(kg=1, m=-1, s=-2)), "kPa": (_F(1000), _d(kg=1, m=-1, s=-2)),
    "C": (_F(1), _d(A=1, s=1)), "V": (_F(1), _d(kg=1, m=2, s=-3, A=-1)),
    "Ω": (_F(1), _d(kg=1, m=2, s=-3, A=-2)), "ohm": (_F(1), _d(kg=1, m=2, s=-3, A=-2)),
    "Hz": (_F(1), _d(s=-1)),
    "L": (_F(1, 1000), _d(m=3)), "mL": (_F(1, 10**6), _d(m=3)),
    "USD": (_F(1), _d(USD=1)),
    # Angles are their own dimension, counted in degrees, so they stay exact
    # (a radian is an irrational number of degrees and has no unit here).
    "deg": (_F(1), _d(deg=1)),
}

#: Built-in quantity types (the type of a field or parameter) -> dims.
QUANTITY_TYPES: dict[str, Dims] = {
    "Number": (), "Mass": _d(kg=1), "Length": _d(m=1), "Time": _d(s=1),
    "Current": _d(A=1), "Temperature": _d(K=1), "Amount": _d(mol=1),
    "Luminosity": _d(cd=1), "Area": _d(m=2), "Volume": _d(m=3),
    "Velocity": _d(m=1, s=-1), "Accel": _d(m=1, s=-2), "Force": _d(kg=1, m=1, s=-2),
    "Momentum": _d(kg=1, m=1, s=-1), "Energy": _d(kg=1, m=2, s=-2),
    "Power": _d(kg=1, m=2, s=-3), "Pressure": _d(kg=1, m=-1, s=-2),
    "Charge": _d(A=1, s=1), "Voltage": _d(kg=1, m=2, s=-3, A=-1),
    "Resistance": _d(kg=1, m=2, s=-3, A=-2), "Frequency": _d(s=-1),
    "Molarity": _d(mol=1, m=-3), "MolarMass": _d(kg=1, mol=-1), "Money": _d(USD=1),
    "Real": (), "Angle": _d(deg=1),
}

_FACTOR = re.compile(r"([^\s*/·^]+)(?:\^(-?\d+))?")


def unit_regex() -> str:
    """Alternation of unit names, longest first, for the QUANTITY token."""
    return "(?:" + "|".join(re.escape(u) for u in sorted(UNITS, key=lambda u: (-len(u), u))) + ")"


def parse_unit(text: str) -> tuple[Fraction, Dims] | None:
    """``m/s^2`` -> (1, {m:1, s:-2}). None if a unit name is unknown."""
    factor, dims = Fraction(1), dict[str, Fraction]()
    sign = 1
    for part in re.split(r"([*/·])", text.strip()):
        if part in ("*", "·"):
            sign = 1
            continue
        if part == "/":
            sign = -1
            continue
        m = _FACTOR.fullmatch(part)
        if not m or m.group(1) not in UNITS:
            return None
        f, d = UNITS[m.group(1)]
        k = sign * int(m.group(2) or 1)
        factor *= f ** k
        for n, e in d:
            dims[n] = dims.get(n, Fraction(0)) + e * k
    return factor, make_dims(dims)


def dims_text(d: Dims) -> str:
    """{kg:1, m:1, s:-2} -> 'kg*m/s^2' (base units)."""
    if not d:
        return ""

    def part(n: str, e: Fraction) -> str:
        return n if e == 1 else f"{n}^{e}"
    num = [part(n, e) for n, e in d if e > 0]
    den = [part(n, -e) for n, e in d if e < 0]
    return ("*".join(num) or "1") + ("/" + "/".join(den) if den else "")


#: Preferred display unit per dims (derived units read better than base units).
_DISPLAY = {d: u for u, (f, d) in UNITS.items() if f == 1 and u not in ("ohm",)}


def show_quantity(value: Fraction, d: Dims) -> str:
    v = str(value.numerator) if value.denominator == 1 else (
        str(float(value)) if len(str(float(value))) < 12 else str(value))
    if not d:
        return v
    return f"{v} {_DISPLAY.get(d) or dims_text(d)}"
