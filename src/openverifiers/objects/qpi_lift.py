"""Lift a solver model into Q(pi) (untrusted; D-026).

z3 sees pi as a variable bounded by an interval, so its models put a rational
stand-in for pi into every value that depends on it, and the exact re-check
rightly rejects them. This search repairs such a model: it keeps the model's
values where it can and re-solves, with pi as a symbol, for variables that the
equations then force. It first frees the variables whose values carry the
rational stand-in for pi (huge numerators or denominators), then, while an
equation is still violated, one more variable that occurs linearly in it; the
solution must be a rational function of pi. The
result goes back to the trusted re-check (raw/formula.py with raw/qpi.py); a
wrong lift can only be rejected there, never accepted.
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction

import sympy

from ..raw.formula import ClassDef
from ..raw.qpi import QPi
from ..raw.surd import Surd
from ..raw.terms import Compound, Num, Str, Term, Var

PI = sympy.Symbol("PI_")


class _Skip(Exception):
    pass


def _sym(t: Term, props: Mapping[str, Term]) -> sympy.Expr:
    if isinstance(t, Num):
        if t.dims and t.dims != ():
            raise _Skip
        return sympy.Rational(t.value.numerator, t.value.denominator)
    if isinstance(t, Var):
        return sympy.Symbol(t.name)
    if not isinstance(t, Compound):
        raise _Skip
    f, a = t.functor, t.args
    if f == "f.p" and isinstance(a[0], Str) and a[0].value in props:
        return _sym(props[a[0].value], props)
    if f == "f.at" and isinstance(a[1], Num):
        base = a[0]
        while isinstance(base, Compound) and base.functor == "f.p" \
                and isinstance(base.args[0], Str):
            base = props[base.args[0].value]
        if isinstance(base, Compound) and base.functor == "f.tuple":
            return _sym(base.args[int(a[1].value)], props)
        raise _Skip
    if f == "f.pi":
        return PI
    if f == "f.valueat":
        from ..raw.formula import subst
        return _sym(subst(a[0], a[1], a[2]), props)
    if f in ("f.integral", "f.deriv"):          # polynomial calculus in the designator
        var, dummy = _sym(a[1], props), sympy.Dummy("x")
        body = _sym(a[0], props).subs(var, dummy)
        upper = _sym(a[2], props)
        if f == "f.integral":
            return sympy.integrate(body, (dummy, 0, upper))
        return sympy.diff(body, dummy).subs(dummy, upper)
    xs = [_sym(x, props) for x in a]
    if f == "+" and len(xs) == 2:
        return xs[0] + xs[1]
    if f == "-":
        return -xs[0] if len(xs) == 1 else xs[0] - xs[1]
    if f == "*":
        return xs[0] * xs[1]
    if f == "/":
        return xs[0] / xs[1]
    if f == "^" and a[1:] and isinstance(a[1], Num):
        return xs[0] ** int(a[1].value)
    raise _Skip


def _equations(cls: ClassDef, props: Mapping[str, Term]) -> list[sympy.Expr]:
    out = []
    for _, inv in cls.invariants:
        parts = inv.args if isinstance(inv, Compound) and inv.functor == "f.and" else (inv,)
        for c in parts:
            if isinstance(c, Compound) and c.functor == "f.cmp" and c.args[0] == Str("="):
                try:
                    out.append(sympy.together(_sym(c.args[1], props) - _sym(c.args[2], props)))
                except (_Skip, KeyError, IndexError):
                    continue
    return out


def _solve(eqs: list[sympy.Expr], vals: dict[sympy.Symbol, sympy.Expr],
           free: list[sympy.Symbol]) -> bool:
    """Re-solve the free variables with the others fixed; True if uniquely, in Q(pi)."""
    sub = {s: v for s, v in vals.items() if s not in free}
    rest = [sympy.numer(sympy.together(e.subs(sub))) for e in eqs]
    sol = sympy.solve([e for e in rest if e.free_symbols & set(free)], free, dict=True)
    if len(sol) != 1 or set(sol[0]) != set(free) or \
            any(v.free_symbols - {PI} for v in sol[0].values()):
        return False
    vals.update(sol[0])
    return True


def lift(cls: ClassDef, props: Mapping[str, Term], model: Mapping[str, Fraction | Surd]
         ) -> dict[str, Fraction | Surd | QPi] | None:
    """A model in which the values that depend on pi are exact elements of Q(pi)."""
    eqs = [e for e in _equations(cls, props) if e != 0]
    if not any(PI in e.free_symbols for e in eqs) or \
            not all(isinstance(v, Fraction) for v in model.values()):
        return None
    vals: dict[sympy.Symbol, sympy.Expr] = {
        sympy.Symbol(k): sympy.Rational(v.numerator, v.denominator)
        for k, v in model.items() if isinstance(v, Fraction)}
    free: list[sympy.Symbol] = sorted(
        (s for s, v in vals.items() if str(s) != "PI" and max(abs(sympy.numer(v)),
                                                              sympy.denom(v)) > 10 ** 8),
        key=str)
    if free and not _solve(eqs, vals, free):
        return None
    for _ in range(len(vals)):
        bad = [e for e in eqs
               if sympy.simplify(sympy.numer(sympy.together(e.subs(vals)))) != 0]
        if not bad:
            break
        num = sympy.numer(sympy.together(bad[0]))
        pick = next((s for s in sorted(num.free_symbols - {PI} - set(free), key=str)
                     if sympy.degree(num, s) == 1), None)
        if pick is None:
            return None
        free.append(pick)
        if not _solve(eqs, vals, free):
            return None
    else:
        return None
    out: dict[str, Fraction | Surd | QPi] = {}
    for k in model:
        n, d = sympy.fraction(sympy.cancel(vals[sympy.Symbol(k)]))
        pn, pd = sympy.Poly(n, PI), sympy.Poly(d, PI)
        coeffs = [[Fraction(int(c.p), int(c.q)) for c in reversed(p.all_coeffs())]
                  for p in (pn, pd)]
        q = QPi.make(tuple(coeffs[0]), tuple(coeffs[1]))
        r = q.rational()
        out[k] = r if r is not None else q
    return out
