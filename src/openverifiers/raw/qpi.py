"""Exact arithmetic in Q(pi) (D-026).

A value is p(pi) / q(pi) with p, q polynomials over the rationals (coefficient
tuples, lowest degree first) and q not the zero polynomial. pi is
transcendental, so a polynomial in pi is zero exactly when all its coefficients
are: equality is decided by exact normal form, with no numerics. The sign of a
nonzero value is the sign of p(pi) q(pi), read off a rigorous interval
enclosure of pi; if the enclosure does not exclude 0 the comparison is refused
(QPiError), never guessed. Stored as the term f.qpi(n, p..., q...) with n the
number of coefficients of p.

Trusted code (exact-arithmetic unit).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from . import interval as I
from .terms import Compound, Num, Term

P = tuple[Fraction, ...]
ONE: P = (Fraction(1),)


class QPiError(ValueError):
    """Undecided (an enclosure that does not separate) or undefined (division by 0)."""


def _trim(p: P) -> P:
    while p and p[-1] == 0:
        p = p[:-1]
    return p


def _add(p: P, q: P) -> P:
    n = max(len(p), len(q))
    z = Fraction(0)
    return _trim(tuple((p[i] if i < len(p) else z) + (q[i] if i < len(q) else z)
                       for i in range(n)))


def _mul(p: P, q: P) -> P:
    out = [Fraction(0)] * max(len(p) + len(q) - 1, 0)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            out[i + j] += a * b
    return _trim(tuple(out))


@dataclass(frozen=True, slots=True)
class QPi:
    num: P
    den: P

    @staticmethod
    def make(num: P, den: P) -> QPi:
        num, den = _trim(tuple(map(Fraction, num))), _trim(tuple(map(Fraction, den)))
        if not den:
            raise QPiError("division by zero")
        return QPi(num, den)

    def __add__(self, o: QPi) -> QPi:
        return QPi.make(_add(_mul(self.num, o.den), _mul(o.num, self.den)), _mul(self.den, o.den))

    def __mul__(self, o: QPi) -> QPi:
        return QPi.make(_mul(self.num, o.num), _mul(self.den, o.den))

    def __sub__(self, o: QPi) -> QPi:
        return self + o * QPi(tuple([Fraction(-1)]), ONE)

    def rational(self) -> Fraction | None:
        """The value if it is rational: p = k q for a constant k."""
        k = self.num[-1] / self.den[-1] if self.num else Fraction(0)
        ok = not self.num or (len(self.num) == len(self.den)
                              and all(a == k * b for a, b in zip(self.num, self.den, strict=True)))
        return k if ok else None

    def iv(self) -> I.Iv:
        return _at_pi(self.num) / _at_pi(self.den)

    def sign(self) -> int:
        s = _at_pi(_mul(self.num, self.den)) if self.num else I.Iv.of(Fraction(0))
        if s.lo > 0 or s.hi < 0 or not self.num:
            return 0 if not self.num else (1 if s.lo > 0 else -1)
        raise QPiError("the enclosure of pi does not decide the sign")


PI = QPi((Fraction(0), Fraction(1)), ONE)


def _at_pi(p: P) -> I.Iv:
    out, x, pi = I.Iv.of(Fraction(0)), I.Iv.of(Fraction(1)), I.pi()
    for c in p:
        out, x = out + x * I.Iv.of(c), x * pi
    return out


def to_qpi(v: object) -> QPi:
    if isinstance(v, QPi):
        return v
    if isinstance(v, Num) and not v.dims:
        return QPi.make((v.value,), ONE)
    raise QPiError(f"not a number in Q(pi): {v}")


def apply(f: str, vals: Sequence[object]) -> QPi:
    """An arithmetic operation on numbers of Q(pi)."""
    xs = [to_qpi(v) for v in vals]
    k = xs[1].rational() if len(xs) == 2 else None
    if f == "-" and len(xs) == 1:
        return QPi.make((), ONE) - xs[0]
    if f == "^" and k is not None and k.denominator == 1 and k >= 0:
        out = QPi.make(ONE, ONE)
        for _ in range(int(k)):
            out = out * xs[0]
        return out
    if f in ("+", "-", "*", "/") and len(xs) == 2:
        a, b = xs
        return a + b if f == "+" else a - b if f == "-" else \
            a * b if f == "*" else a * QPi.make(b.den, b.num)
    raise QPiError(f"cannot apply {f} in Q(pi)")


def value(q: QPi) -> Num | QPi:
    r = q.rational()
    return Num(r) if r is not None else q


def to_term(q: QPi) -> Term:
    return Compound("f.qpi", (Num(Fraction(len(q.num))), *map(Num, q.num), *map(Num, q.den)))


def from_term(args: tuple[Term, ...]) -> QPi:
    cs = [a.value for a in args if isinstance(a, Num) and not a.dims]
    if len(cs) != len(args) or not cs or cs[0].denominator != 1 or not 0 <= cs[0] < len(cs):
        raise QPiError("malformed Q(pi) value")
    return QPi.make(tuple(cs[1:int(cs[0]) + 1]), tuple(cs[int(cs[0]) + 1:]))
