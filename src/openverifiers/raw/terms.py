"""RawOV terms: constants, variables, compounds, plus matching and ordering.

Trusted code. Everything here is small, total, and has no side effects.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from fractions import Fraction

#: A dimension vector: sorted ``(base_dimension, exponent)`` pairs, no zero exponents.
Dims = tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True, slots=True)
class Sym:
    """A symbolic constant, e.g. ``block`` or ``'2-methylbut-1-ene'``."""

    name: str


@dataclass(frozen=True, slots=True)
class Str:
    """A string constant."""

    value: str


@dataclass(frozen=True, slots=True)
class Num:
    """An exact rational quantity. ``dims`` is empty for pure numbers.

    Values are always stored in SI base units (or the base unit of a
    user-declared dimension), so equal quantities are equal terms.
    """

    value: Fraction
    dims: Dims = ()


@dataclass(frozen=True, slots=True)
class Var:
    name: str


@dataclass(frozen=True, slots=True)
class Compound:
    functor: str
    args: tuple[Term, ...]


Term = Sym | Str | Num | Var | Compound
Subst = Mapping[str, Term]


def make_dims(pairs: Mapping[str, Fraction | int]) -> Dims:
    """Normalise a mapping into a canonical dimension vector."""
    return tuple(sorted((k, Fraction(v)) for k, v in pairs.items() if v != 0))


def is_ground(t: Term) -> bool:
    if isinstance(t, Var):
        return False
    if isinstance(t, Compound):
        return all(is_ground(a) for a in t.args)
    return True


def depth(t: Term) -> int:
    """Nesting depth of compound terms (constants and variables have depth 0)."""
    if isinstance(t, Compound):
        return 1 + max((depth(a) for a in t.args), default=0)
    return 0


def variables(t: Term) -> Iterator[str]:
    if isinstance(t, Var):
        yield t.name
    elif isinstance(t, Compound):
        for a in t.args:
            yield from variables(a)


def substitute(t: Term, s: Subst) -> Term:
    if isinstance(t, Var):
        return s.get(t.name, t)
    if isinstance(t, Compound):
        return Compound(t.functor, tuple(substitute(a, s) for a in t.args))
    return t


def match(pattern: Term, ground: Term, s: dict[str, Term]) -> bool:
    """One-way matching of ``pattern`` against a ground term, extending ``s`` in place.

    On failure ``s`` may hold partial bindings; callers pass a copy.
    """
    if isinstance(pattern, Var):
        bound = s.get(pattern.name)
        if bound is None:
            s[pattern.name] = ground
            return True
        return bound == ground
    if isinstance(pattern, Compound):
        if (not isinstance(ground, Compound) or ground.functor != pattern.functor
                or len(ground.args) != len(pattern.args)):
            return False
        return all(match(p, g, s) for p, g in zip(pattern.args, ground.args, strict=True))
    return pattern == ground


def order_key(t: Term) -> tuple[object, ...]:
    """Standard term order: variables < numbers < strings < symbols < compounds.

    Numbers order by dimension vector, then value. Compounds order by
    arity, then functor, then arguments left to right.
    """
    if isinstance(t, Var):
        return (0, t.name)
    if isinstance(t, Num):
        return (1, tuple((k, e) for k, e in t.dims), t.value)
    if isinstance(t, Str):
        return (2, t.value)
    if isinstance(t, Sym):
        return (3, t.name)
    return (4, len(t.args), t.functor, tuple(order_key(a) for a in t.args))
