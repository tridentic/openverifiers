"""Rigorous interval arithmetic with rational endpoints.

An :class:`Iv` [lo, hi] contains the true real value. Every operation returns an
interval that contains every result of the operation on members of its inputs.
Endpoints are rounded outward to a binary grid (2^-PREC), so sizes stay bounded,
and transcendental functions use Taylor series with explicit remainder bounds.
Nothing is rounded inward, so enclosure is never lost.

exp, ln, sin, cos, pi and sqrt are provided. They serve exponential decay,
logarithms, general angles and `tolerance`.

Trusted code.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import isqrt

PREC = 200                                   # bits of the rounding grid


class IntervalError(ValueError):
    """Outside the domain (division by an interval containing 0, ln of a non-positive)."""


def _down(x: Fraction) -> Fraction:
    s = 1 << PREC
    return Fraction((x.numerator * s) // x.denominator, s)


def _up(x: Fraction) -> Fraction:
    s = 1 << PREC
    return Fraction(-((-x.numerator * s) // x.denominator), s)


@dataclass(frozen=True, slots=True)
class Iv:
    lo: Fraction
    hi: Fraction

    @staticmethod
    def of(x: Fraction) -> Iv:
        return Iv(x, x)

    @staticmethod
    def make(lo: Fraction, hi: Fraction) -> Iv:
        return Iv(_down(lo), _up(hi))

    def __add__(self, o: Iv) -> Iv:
        return Iv.make(self.lo + o.lo, self.hi + o.hi)

    def __neg__(self) -> Iv:
        return Iv(-self.hi, -self.lo)

    def __sub__(self, o: Iv) -> Iv:
        return self + (-o)

    def __mul__(self, o: Iv) -> Iv:
        ps = (self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi)
        return Iv.make(min(ps), max(ps))

    def inverse(self) -> Iv:
        if self.lo <= 0 <= self.hi:
            raise IntervalError("division by an interval containing 0")
        return Iv.make(1 / self.hi, 1 / self.lo)

    def __truediv__(self, o: Iv) -> Iv:
        return self * o.inverse()

    def power(self, k: int) -> Iv:
        out = Iv.of(Fraction(1))
        for _ in range(k):
            out = out * self
        return out

    def width(self) -> Fraction:
        return self.hi - self.lo

    def within(self, o: Iv) -> bool:
        return o.lo <= self.lo and self.hi <= o.hi


def _taylor(terms: list[Fraction], x: Iv, rem: Fraction) -> Iv:
    """sum terms[k] * x^k, widened by +-rem (the series remainder bound)."""
    out, p = Iv.of(Fraction(0)), Iv.of(Fraction(1))
    for c in terms:
        out = out + p * Iv.of(c)
        p = p * x
    return out + Iv(-rem, rem)


def _mag(x: Iv) -> Fraction:
    return max(abs(x.lo), abs(x.hi))


def exp(x: Iv) -> Iv:
    """e^x: halve x until |x| <= 1/2, sum the series, then square back."""
    if _mag(x) > 4096:
        raise IntervalError("exp of an argument above 4096 in magnitude")
    m = 0
    while _mag(x) > Fraction(1, 2):
        x = x * Iv.of(Fraction(1, 2))
        m += 1
    n = 60
    fact, coeffs = 1, []
    for k in range(n):
        coeffs.append(Fraction(1, fact))
        fact *= k + 1
    rem = 2 * _mag(x) ** n / fact                # e^|y| <= 2 for |y| <= 1/2
    y = _taylor(coeffs, x, rem)
    for _ in range(m):
        y = y * y
    return Iv.make(max(y.lo, Fraction(0)), y.hi)


def _atanh_series(z: Iv, n: int = 80) -> Iv:
    """artanh(z) for |z| <= 1/3: sum z^(2k+1) / (2k+1)."""
    coeffs = [Fraction(0) if k % 2 == 0 else Fraction(1, k) for k in range(2 * n)]
    m = _mag(z)
    rem = m ** (2 * n + 1) / ((2 * n + 1) * (1 - m * m))
    return _taylor(coeffs, z, rem)


def _ln2() -> Iv:
    return Iv.of(Fraction(2)) * _atanh_series(Iv.of(Fraction(1, 3)))


def ln(x: Iv) -> Iv:
    """ln x for x > 0: x = m 2^e with m in [1/2, 2), ln m = 2 artanh((m-1)/(m+1))."""
    if x.lo <= 0:
        raise IntervalError("ln of a value that may be <= 0")
    e = 0
    while x.hi >= 2:
        x, e = x * Iv.of(Fraction(1, 2)), e + 1
    while x.lo < Fraction(1, 2):
        x, e = x * Iv.of(Fraction(2)), e - 1
    if x.hi >= 2:
        raise IntervalError("ln of an interval too wide to reduce")
    one = Iv.of(Fraction(1))
    z = (x - one) / (x + one)                    # |z| < 1/3
    return Iv.of(Fraction(2)) * _atanh_series(z) + _ln2() * Iv.of(Fraction(e))


def _atan_series(z: Fraction, n: int = 120) -> Iv:
    coeffs = [Fraction(0) if k % 2 == 0 else Fraction((-1) ** (k // 2), k) for k in range(2 * n)]
    return _taylor(coeffs, Iv.of(z), abs(z) ** (2 * n + 1) / (2 * n + 1))


def pi() -> Iv:
    """Machin: pi = 16 atan(1/5) - 4 atan(1/239)."""
    return Iv.of(Fraction(16)) * _atan_series(Fraction(1, 5)) \
        - Iv.of(Fraction(4)) * _atan_series(Fraction(1, 239))


def _trig(x: Iv, cosine: bool) -> Iv:
    n = 80                                       # |x| <= 8 is enough for angles <= 400 deg
    if _mag(x) > 8:
        raise IntervalError("angle too large for the series")
    fact, coeffs = 1, []
    for k in range(2 * n):
        sign = (-1) ** (k // 2)
        coeffs.append(Fraction(0) if (k % 2 == 1) == cosine else Fraction(sign, fact))
        fact *= k + 1
    rem = _mag(x) ** (2 * n) / fact
    y = _taylor(coeffs, x, rem)
    return Iv.make(max(y.lo, Fraction(-1)), min(y.hi, Fraction(1)))


def cos(x: Iv) -> Iv:
    return _trig(x, True)


def sin(x: Iv) -> Iv:
    return _trig(x, False)


def sqrt(x: Iv) -> Iv:
    if x.lo < 0:
        raise IntervalError("sqrt of a value that may be negative")
    s = 1 << PREC

    def isq(v: Fraction, up: bool) -> Fraction:
        n = (v.numerator * s * s) // v.denominator
        r = isqrt(n)
        return Fraction(r + (1 if up and r * r != n else 0), s)
    return Iv(isq(x.lo, False), isq(x.hi, True) + Fraction(1, s))


def from_surd(terms: tuple[tuple[int, Fraction], ...]) -> Iv:
    """An exact surd sum c1 sqrt(k1) + ... as an enclosing interval."""
    out = Iv.of(Fraction(0))
    for k, c in terms:
        out = out + sqrt(Iv.of(Fraction(k))) * Iv.of(c)
    return out


def decide(op: str, a: Iv, b: Iv) -> bool | None:
    """The comparison if the intervals decide it (separated), else None."""
    if a.hi < b.lo:
        lt = True
    elif b.hi < a.lo:
        lt = False
    else:
        return None
    return {"=": False, "!=": True, "<": lt, "<=": lt, ">": not lt, ">=": not lt}[op]
