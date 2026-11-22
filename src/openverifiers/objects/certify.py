"""Find proof certificates for class theorems (untrusted; sympy).

The trusted checker is raw/certificate.py: whatever this module proposes is
re-checked there by exact polynomial normal form, so a wrong proposal can only
fail to certify, never certify something false.

The search:
1. Goal: a comparison L op R (op =, >=, <=), or a conjunction of them.
2. Hypotheses: the class's equation invariants, plus earlier certified theorems.
3. Multipliers: none, then each nonzero/positive hypothesis, then pairs.
4. Ideal part: reduce M (L - R) by the equations with sympy, trying several
   variable orders (defined properties eliminated first). A zero remainder gives
   the coefficients.
5. For >=: a remainder that is a non-negative constant times a square.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from collections.abc import Mapping
from fractions import Fraction

import sympy

from ..raw.certificate import Certificate, Poly, check, poly
from ..raw.formula import Unsupported
from ..raw.terms import Compound, Num, Str, Term


def comparisons(f: Term, name: str) -> list[tuple[str, Term]]:
    """The top-level comparison conjuncts of a formula, named name, name#2, ..."""
    parts = list(f.args) if isinstance(f, Compound) and f.functor == "f.and" else [f]
    out = [p for p in parts if isinstance(p, Compound) and p.functor == "f.cmp"]
    return [(name if i == 0 else f"{name}#{i + 1}", p) for i, p in enumerate(out)]


def _vars(t: Term, out: dict[str, Term]) -> None:
    if isinstance(t, Compound):
        if t.functor in ("f.p", "f.at", "f.v"):
            out[str(t)] = t
            return
        for a in t.args:
            _vars(a, out)


def _sym(k: str) -> sympy.Symbol:
    # A stable name (not Python's salted hash): variable orders, and so the search,
    # are the same in every run.
    return sympy.Symbol("v_" + re.sub(r"\W", "_", k) + "_"
                        + hashlib.sha1(k.encode()).hexdigest()[:6])


def _to_sympy(p: Poly, syms: Mapping[str, sympy.Symbol]) -> sympy.Expr:
    out = sympy.Integer(0)
    for m, c in p.items():
        term = sympy.Rational(c.numerator, c.denominator)
        for v, k in m:
            term = term * syms[v] ** k
        out = out + term
    return sympy.expand(out)


def _to_term(e: sympy.Expr, back: Mapping[sympy.Symbol, Term]) -> Term:
    p = sympy.Poly(sympy.expand(e), *back.keys()) if back else None
    if p is None or p.is_zero:
        return Num(Fraction(0)) if p is None or p.is_zero else Num(Fraction(str(e)))
    out: Term | None = None
    gens = list(back.keys())
    for monom, coeff in p.terms():
        t: Term = Num(Fraction(int(coeff.p), int(coeff.q)))
        for g, k in zip(gens, monom, strict=True):
            for _ in range(k):
                t = Compound("*", (t, back[g]))
        out = t if out is None else Compound("+", (out, t))
    return out if out is not None else Num(Fraction(0))


def find(goal: Term, hyps: Mapping[str, Term]) -> Certificate | None:
    try:
        return _find(goal, hyps)
    except (Unsupported, sympy.PolynomialError, sympy.CoercionFailed, ValueError,
            NotImplementedError):
        return None


def _find(goal: Term, hyps: Mapping[str, Term]) -> Certificate | None:
    if not (isinstance(goal, Compound) and goal.functor == "f.cmp"):
        return None
    op = goal.args[0].value if isinstance(goal.args[0], Str) else ""
    if op not in ("=", ">=", "<="):
        return None
    lhs, rhs = (goal.args[1], goal.args[2]) if op != "<=" else (goal.args[2], goal.args[1])
    terms: dict[str, Term] = {}
    for t in (goal, *hyps.values()):
        _vars(t, terms)
    syms = {k: _sym(k) for k in terms}
    back = {syms[k]: terms[k] for k in terms}
    eqs, factors = [], []
    for name, h in hyps.items():
        hop = h.args[0].value if isinstance(h, Compound) and isinstance(h.args[0], Str) else ""
        try:
            hp = poly(Compound("-", (h.args[1], h.args[2])))  # type: ignore[union-attr]
        except Unsupported:
            continue
        if hop == "=":
            eqs.append((name, _to_sympy(hp, syms), h))
        elif hop in ("!=", ">", "<") and (op == "=" or hop != "!="):
            factors.append(name)
    target0 = _to_sympy(poly(Compound("-", (lhs, rhs))), syms)
    defined = [syms[str(h.args[1])] for _, _, h in eqs  # type: ignore[union-attr]
               if str(h.args[1]) in syms]                # type: ignore[union-attr]
    others = [s for s in syms.values() if s not in defined]
    orders = [list(dict.fromkeys([*defined, *others])), list(dict.fromkeys([*others, *defined])),
              sorted(syms.values(), key=str)]
    for k in range(3):
        for fs in itertools.combinations(factors, k):
            m = sympy.Integer(1)
            for name in fs:
                h = hyps[name]
                assert isinstance(h, Compound)
                d = Compound("-", (h.args[1], h.args[2]) if h.args[0] != Str("<")
                             else (h.args[2], h.args[1]))
                m = m * _to_sympy(poly(d), syms)
            target = sympy.expand(m * target0)
            for gens in orders:
                cert = _try(target, eqs, gens, back, fs, op)
                if cert is not None and check(goal, hyps, cert):
                    return cert
    return None


def _try(target: sympy.Expr, eqs: list[tuple[str, sympy.Expr, Term]], gens: list[sympy.Symbol],
         back: Mapping[sympy.Symbol, Term], fs: tuple[str, ...], op: str) -> Certificate | None:
    if not gens:
        return None
    hs = [e for _, e, _ in eqs if e != 0]
    names = [n for n, e, _ in eqs if e != 0]
    if hs:
        qs, r = sympy.reduced(target, hs, *gens, order="lex")
    else:
        qs, r = [], target
    coeffs = tuple((n, _to_term(q, back)) for n, q in zip(names, qs, strict=True) if q != 0)
    r = sympy.expand(r)
    if r == 0:
        return Certificate(fs, coeffs)
    if op == "=":
        return None
    # The remainder, or the remainder shifted by one equation (r - s h, s = +-1), as a
    # non-negative constant times a square.
    for name, h in [("", sympy.Integer(0)), *((n, e) for n, e, _ in eqs)]:
        for sign in ((0,) if not name else (1, -1)):
            rr = sympy.expand(r - sign * h)
            sq = _square(rr, back)
            if sq is None:
                continue
            extra = ((name, _to_term(sympy.Integer(sign), back)),) if name else ()
            merged = dict(coeffs)
            for n, t in extra:
                merged[n] = t if n not in merged else Compound("+", (merged[n], t))
            return Certificate(fs, tuple(merged.items()), (sq,))
    return None


def _square(r: sympy.Expr, back: Mapping[sympy.Symbol, Term]) -> tuple[Fraction, Term] | None:
    const, facs = sympy.factor_list(r)
    if const < 0 or any(k % 2 for _, k in facs):
        return None
    q = sympy.Integer(1)
    for f, k in facs:
        q = q * f ** (k // 2)
    return Fraction(int(sympy.Rational(const).p), int(sympy.Rational(const).q)), _to_term(q, back)
