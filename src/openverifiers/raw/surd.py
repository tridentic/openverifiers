"""Exact quadratic surds: sums of rational multiples of square roots of
squarefree integers, c1*sqrt(k1) + c2*sqrt(k2) + ... (k = 1 is the rational part).

Square roots of distinct squarefree integers are linearly independent over the
rationals, so two surds are equal exactly when their coefficients are. The sign
of a nonzero surd is found by bounding each square root between integer square
roots at growing precision until the bound excludes 0, which always happens for
a nonzero value. Everything is exact; nothing is rounded.

Trusted code (the evaluator uses it for distances, square roots and the cosines
and sines of the special angles).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import isqrt

#: Integers are reduced to squarefree form by trial division up to this bound;
#: larger unreduced factors are refused rather than guessed.
_TRIAL = 1_000_000


class SurdError(ValueError):
    """Outside the exact fragment (an unreducible radicand, a nonlinear root)."""


def _squarefree(n: int) -> tuple[int, int]:
    """n = g^2 * k with k squarefree: (g, k). n > 0."""
    g, k, p = 1, 1, 2
    while p * p <= n:
        if p > _TRIAL:
            raise SurdError("radicand too large to factor exactly")
        e = 0
        while n % p == 0:
            n //= p
            e += 1
        g *= p ** (e // 2)
        if e % 2:
            k *= p
        p += 1 if p == 2 else 2
    return g, k * n


@dataclass(frozen=True, slots=True)
class Surd:
    terms: tuple[tuple[int, Fraction], ...]    # (squarefree k, coefficient), sorted, no zeros

    @staticmethod
    def make(d: dict[int, Fraction]) -> Surd:
        return Surd(tuple(sorted((k, c) for k, c in d.items() if c != 0)))

    @staticmethod
    def of(x: Fraction) -> Surd:
        return Surd.make({1: x})

    @staticmethod
    def sqrt(x: Fraction) -> Surd:
        """The non-negative square root of a rational x >= 0."""
        if x < 0:
            raise SurdError("square root of a negative number")
        n, d = x.numerator, x.denominator
        g, k = _squarefree(n * d)                # sqrt(n/d) = sqrt(n d) / d
        return Surd.make({k: Fraction(g, d)})

    def rational(self) -> Fraction | None:
        if not self.terms:
            return Fraction(0)
        if len(self.terms) == 1 and self.terms[0][0] == 1:
            return self.terms[0][1]
        return None

    def __add__(self, o: Surd) -> Surd:
        d = dict(self.terms)
        for k, c in o.terms:
            d[k] = d.get(k, Fraction(0)) + c
        return Surd.make(d)

    def __neg__(self) -> Surd:
        return Surd(tuple((k, -c) for k, c in self.terms))

    def __sub__(self, o: Surd) -> Surd:
        return self + (-o)

    def __mul__(self, o: Surd) -> Surd:
        d: dict[int, Fraction] = {}
        for k1, c1 in self.terms:
            for k2, c2 in o.terms:
                g, k = _squarefree(k1 * k2)
                d[k] = d.get(k, Fraction(0)) + c1 * c2 * g
        return Surd.make(d)

    def inverse(self) -> Surd:
        """1 / self, for a single term c sqrt(k) (or a rational)."""
        if len(self.terms) != 1:
            raise SurdError("division by a sum of square roots")
        k, c = self.terms[0]
        return Surd.make({k: 1 / (c * k)})

    def sign(self) -> int:
        if not self.terms:
            return 0
        if all(c > 0 for _, c in self.terms):
            return 1
        if all(c < 0 for _, c in self.terms):
            return -1
        p = 10
        while True:                    # terminates: a nonzero surd has a nonzero bound
            scale = 10 ** p
            lo = hi = Fraction(0)
            for k, c in self.terms:
                r = isqrt(k * scale * scale)          # r <= sqrt(k) * scale < r + 1
                a, b = Fraction(r, scale), Fraction(r + 1, scale) if r * r != k * scale * scale \
                    else Fraction(r, scale)
                lo += c * a if c > 0 else c * b
                hi += c * b if c > 0 else c * a
            if lo > 0:
                return 1
            if hi < 0:
                return -1
            p *= 2
