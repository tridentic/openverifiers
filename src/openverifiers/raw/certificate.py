"""Polynomial normal form and proof certificates (the exact-arithmetic unit).

An untrusted finder (sympy) proposes a certificate; this module only checks it.
For a goal L op R (op is =, >= or <=) under hypotheses, a certificate gives:

- factors: hypotheses `f != 0`, `f > 0` or `f < 0`. Their product M is the
  multiplier: nonzero for an equation, positive for an inequality (a `<` factor
  enters as -f);
- coeffs: (hypothesis `A = B`, polynomial c): the ideal part, sum c (A - B);
- squares: (weight w >= 0, polynomial q), for inequalities only.

It checks, by exact polynomial normal form, that M (L - R) - sum c (A - B) -
sum w q^2 is 0. On any instance where the hypotheses hold, each A - B is 0, so
M (L - R) = sum w q^2, which is >= 0. With M != 0 (or M > 0) that gives the
goal. A polynomial "law solved for one variable" (a = F / m with m > 0) is the
case with a factor. The caller passes only true hypotheses: class invariants,
and theorems already certified.

Two kinds of atom are indeterminates of the ring (D-026): pi, and exp(u) for a
polynomial u. An identity that holds for every value of an indeterminate holds
for the true one. The derivative follows the chain rule d exp(u) = u' exp(u);
an integral, or an evaluation at a limit, of an exp(u) whose u depends on the
variable is refused.

Trusted code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from .formula import Unsupported
from .terms import Compound, Num, Str, Term

Mono = tuple[tuple[str, int], ...]
Poly = dict[Mono, Fraction]
#: exp atoms: name -> exponent polynomial (the name is the exponent's normal form,
#: so equal exponents give the same atom)
EXPS: dict[str, Poly] = {}


def _exp(u: Poly) -> Poly:
    name = "exp" + repr(sorted(u.items()))
    EXPS[name] = u
    return {((name, 1),): Fraction(1)}


def _uses(p: Poly, v: str) -> bool:
    return any(x == v or (x in EXPS and _uses(EXPS[x], v)) for m in p for x, _ in m)


def _add(a: Poly, b: Poly, k: Fraction = Fraction(1)) -> Poly:
    out = dict(a)
    for m, c in b.items():
        out[m] = out.get(m, Fraction(0)) + k * c
    return {m: c for m, c in out.items() if c != 0}


def _mul(a: Poly, b: Poly) -> Poly:
    out: Poly = {}
    for m1, c1 in a.items():
        for m2, c2 in b.items():
            e = dict(m1)
            for v, k in m2:
                e[v] = e.get(v, 0) + k
            m = tuple(sorted(e.items()))
            out[m] = out.get(m, Fraction(0)) + c1 * c2
    return {m: c for m, c in out.items() if c != 0}


def _calc(p: Poly, v: str, integral: bool) -> Poly:
    out: Poly = {}
    for m, c in p.items():
        for x, k in m:          # chain rule: d(E^k)/dv = k E^k u' for E = exp(u)
            if x in EXPS and _uses(EXPS[x], v):
                if integral:
                    raise Unsupported("integral of exp of the variable")
                out = _add(out, _mul({m: c * k}, _calc(EXPS[x], v, False)))
        e = dict(m)
        k = e.pop(v, 0)
        if integral:
            e[v] = k + 1
        elif k == 0:
            continue
        elif k > 1:
            e[v] = k - 1
        mono = tuple(sorted(e.items()))
        out = _add(out, {mono: c / (k + 1) if integral else c * k})
    return out


def _subst(p: Poly, v: str, q: Poly) -> Poly:
    """p with v replaced by q, inside exp atoms too."""
    out: Poly = {}
    for m, c in p.items():
        term: Poly = {(): c}
        for x, k in m:
            f: Poly = q if x == v else _exp(_subst(EXPS[x], v, q)) if x in EXPS \
                and _uses(EXPS[x], v) else {((x, 1),): Fraction(1)}
            for _ in range(k):
                term = _mul(term, f)
        out = _add(out, term)
    return out


def poly(t: Term) -> Poly:
    """A class-formula expression as an exact polynomial; Unsupported otherwise.
    Variables are property references (f.p, f.at, f.v), named by their text."""
    if isinstance(t, Num) and not t.dims:
        return {(): t.value} if t.value else {}
    if isinstance(t, Compound) and t.functor in ("f.p", "f.at", "f.v", "f.pi"):
        return {((str(t), 1),): Fraction(1)}
    if isinstance(t, Compound) and t.functor == "f.exp":
        return _exp(poly(t.args[0]))
    if not isinstance(t, Compound):
        raise Unsupported(f"not polynomial: {t}")
    f, a = t.functor, t.args
    if f in ("f.integral", "f.deriv"):
        x = str(a[1])
        return _subst(_calc(poly(a[0]), x, f == "f.integral"), x, poly(a[2]))
    ps = [poly(x) for x in a]
    if f == "+" and len(ps) == 2:
        return _add(ps[0], ps[1])
    if f == "-":
        return _add({}, ps[0], Fraction(-1)) if len(ps) == 1 else _add(ps[0], ps[1],
                                                                       Fraction(-1))
    if f == "*" and len(ps) == 2:
        return _mul(ps[0], ps[1])
    k = ps[1].get((), Fraction(0)) if len(ps) == 2 and set(ps[1]) <= {()} else None
    if f == "/" and k:
        return _add({}, ps[0], 1 / k)
    if f == "^" and k is not None and k.denominator == 1 and k >= 0:
        out: Poly = {(): Fraction(1)}
        for _ in range(int(k)):
            out = _mul(out, ps[0])
        return out
    raise Unsupported(f"not polynomial: {f}")


@dataclass(frozen=True)
class Certificate:
    factors: tuple[str, ...] = ()
    coeffs: tuple[tuple[str, Term], ...] = ()
    squares: tuple[tuple[Fraction, Term], ...] = ()


def _cmp(f: Term) -> tuple[str, Term, Term]:
    if isinstance(f, Compound) and f.functor == "f.cmp" and isinstance(f.args[0], Str):
        return f.args[0].value, f.args[1], f.args[2]
    raise Unsupported("not a comparison")


def check(goal: Term, hyps: Mapping[str, Term], cert: Certificate) -> bool:
    """True when the certificate proves the goal from the hypotheses."""
    op, lhs, rhs = _cmp(goal)
    if op == "<=":
        op, lhs, rhs = ">=", rhs, lhs
    if op not in ("=", ">=") or (op == "=" and cert.squares):
        return False
    m: Poly = {(): Fraction(1)}
    for name in cert.factors:
        fop, a, b = _cmp(hyps[name])
        if fop not in ({"!=", ">", "<"} if op == "=" else {">", "<"}):
            return False
        m = _mul(m, poly(Compound("-", (a, b) if fop != "<" else (b, a))))
    total = _mul(m, poly(Compound("-", (lhs, rhs))))
    for name, c in cert.coeffs:
        hop, a, b = _cmp(hyps[name])
        if hop != "=":
            return False
        total = _add(total, _mul(poly(c), poly(Compound("-", (a, b)))), Fraction(-1))
    for w, q in cert.squares:
        if w < 0:
            return False
        sq = poly(q)
        total = _add(total, _mul(sq, sq), -w)
    return not total


