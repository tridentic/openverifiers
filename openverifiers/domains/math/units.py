"""Unit strings -> (SI scale, dimension vector), for the math pack.

A unit string is a product of symbols with optional integer exponents,
read left to right: ``"kg*m/s^2"``, ``"km/h"``, ``"1"`` (dimensionless).
No parentheses. Dimension vectors are over the seven SI base dimensions,
in the order (L, M, T, I, Theta, N, J); the idea is ported from the legacy
``units.Dimension``.
"""

from __future__ import annotations

import re

Dim = tuple[int, int, int, int, int, int, int]
NONE: Dim = (0, 0, 0, 0, 0, 0, 0)
BASE_NAMES = ("m", "kg", "s", "A", "K", "mol", "cd")


def _d(**e: int) -> Dim:
    order = ("L", "M", "T", "I", "Th", "N", "J")
    return tuple(e.get(k, 0) for k in order)  # type: ignore[return-value]


# symbol -> (scale to SI, dimension)
UNITS: dict[str, tuple[float, Dim]] = {
    "1": (1.0, NONE),
    "m": (1.0, _d(L=1)), "km": (1000.0, _d(L=1)), "cm": (0.01, _d(L=1)),
    "mm": (0.001, _d(L=1)),
    "s": (1.0, _d(T=1)), "min": (60.0, _d(T=1)), "h": (3600.0, _d(T=1)),
    "kg": (1.0, _d(M=1)), "g": (0.001, _d(M=1)),
    "A": (1.0, _d(I=1)), "K": (1.0, _d(Th=1)), "mol": (1.0, _d(N=1)), "cd": (1.0, _d(J=1)),
    "N": (1.0, _d(M=1, L=1, T=-2)), "J": (1.0, _d(M=1, L=2, T=-2)),
    "W": (1.0, _d(M=1, L=2, T=-3)), "Pa": (1.0, _d(M=1, L=-1, T=-2)),
    "Hz": (1.0, _d(T=-1)), "C": (1.0, _d(I=1, T=1)),
    "V": (1.0, _d(M=1, L=2, T=-3, I=-1)), "ohm": (1.0, _d(M=1, L=2, T=-3, I=-2)),
}

_TOKEN = re.compile(r"([*/]?)\s*([A-Za-z]+|1)(?:\^(-?\d+))?\s*")


def parse(unit: str | None) -> tuple[float, Dim]:
    """Return (scale to SI, dimension). ``None`` and ``"1"`` are dimensionless."""
    if unit is None or unit.strip() in ("", "1"):
        return 1.0, NONE
    scale, dim, pos, text = 1.0, list(NONE), 0, unit.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or (pos == 0 and m.group(1)) or (pos > 0 and not m.group(1)):
            raise ValueError(f"cannot parse unit {unit!r} at {text[pos:]!r}")
        op, sym, exp = m.group(1), m.group(2), int(m.group(3) or 1)
        if sym not in UNITS:
            raise ValueError(f"unknown unit symbol {sym!r} in {unit!r}")
        if op == "/":
            exp = -exp
        s, d = UNITS[sym]
        scale *= s**exp
        dim = [a + b * exp for a, b in zip(dim, d, strict=True)]
        pos = m.end()
    return scale, tuple(dim)  # type: ignore[return-value]


def dimension(unit: str | None) -> Dim:
    return parse(unit)[1]


def to_si(value: float, unit: str | None) -> float:
    return value * parse(unit)[0]


def si_unit(dim: Dim) -> str:
    """Canonical SI spelling of a dimension, e.g. ``kg*m^2/s^2``."""
    num = [(n, e) for n, e in zip(BASE_NAMES, dim, strict=True) if e > 0]
    den = [(n, -e) for n, e in zip(BASE_NAMES, dim, strict=True) if e < 0]

    def part(xs: list[tuple[str, int]]) -> str:
        return "*".join(n if e == 1 else f"{n}^{e}" for n, e in xs)

    if not num and not den:
        return "1"
    return (part(num) or "1") + "".join(f"/{n}" if e == 1 else f"/{n}^{e}" for n, e in den)


def mul(a: Dim, b: Dim, sign: int = 1) -> Dim:
    return tuple(x + sign * y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]
