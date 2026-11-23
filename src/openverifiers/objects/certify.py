"""Find proof certificates for class theorems (untrusted; sympy).

The trusted checker is raw/certificate.py: whatever this module proposes is
re-checked there by exact polynomial normal form, so a wrong proposal can only
fail to certify, never certify something false.

The search:
1. Goal: a comparison L op R (op =, >=, <=), or a conjunction of them.
2. Hypotheses: the class's equation invariants, plus earlier certified theorems.
3. Multipliers: none, then each nonzero/positive hypothesis, then pairs.
6. For =: elimination by pseudo-division (``_pseudo``), whose leading
   coefficients become the multiplier when they are products of nonzero hypotheses.
4. Ideal part: reduce M (L - R) by the equations with sympy, trying several
   variable orders (defined properties eliminated first). A zero remainder gives
   the coefficients.
5. For >=: a remainder that is a non-negative constant times a square.
"""

from __future__ import annotations

import contextlib
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
    """The ring's variables in t, by their normal-form names: properties, pi, exp atoms."""
    if isinstance(t, Compound):
        if t.functor in ("f.p", "f.at", "f.v", "f.pi"):
            out[str(t)] = t
            return
        if t.functor == "f.exp":
            with contextlib.suppress(Unsupported):
                out[next(iter(poly(t)))[0][0]] = t
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


PI = Compound("f.pi", ())


def _cert(names: tuple[str, ...] | list[str], coeffs: tuple[tuple[str, Term], ...] = (),
          squares: tuple[tuple[Fraction, Term], ...] = ()) -> Certificate:
    """A certificate; the pseudo-factor "@pi" becomes a constant the checker signs."""
    return Certificate(tuple(n for n in names if n != "@pi"), coeffs, squares,
                       tuple(PI for n in names if n == "@pi"))


def find(goal: Term, hyps: Mapping[str, Term]) -> Certificate | None:
    try:
        return _find(goal, hyps)
    except (Unsupported, sympy.PolynomialError, sympy.CoercionFailed, ValueError,
            NotImplementedError, KeyError):
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
    fpolys: dict[str, sympy.Expr] = {}
    if str(PI) in syms:                             # pi > 0: signed by the checker itself
        fpolys["@pi"] = syms[str(PI)]
    for name in factors:
        h = hyps[name]
        assert isinstance(h, Compound)
        d = Compound("-", (h.args[1], h.args[2]) if h.args[0] != Str("<")
                     else (h.args[2], h.args[1]))
        fpolys[name] = _to_sympy(poly(d), syms)
    factors = factors + (["@pi"] if "@pi" in fpolys else [])
    for k in range(3):
        for fs in itertools.combinations(factors, k):
            m = sympy.Integer(1)
            for name in fs:
                m = m * fpolys[name]
            target = sympy.expand(m * target0)
            for gens in orders:
                cert = _try(target, eqs, gens, back, fs, op)
                if cert is not None and check(goal, hyps, cert):
                    return cert
    if op == "=":
        cert = _pseudo(target0, eqs, fpolys, back)
        if cert is not None and check(goal, hyps, cert):
            return cert
    return None


def _factors_of(lc: sympy.Expr, fpolys: Mapping[str, sympy.Expr]
                ) -> tuple[list[str], sympy.Expr] | None:
    """lc as a constant times a product of nonzero hypotheses, or None."""
    const, facs = sympy.factor_list(lc)
    names: list[str] = []
    for f, k in facs:
        hit = next(((n, s) for n, g in sorted(fpolys.items()) for s in (1, -1)
                    if sympy.expand(g - s * f) == 0), None)
        if hit is None:
            return None
        names += [hit[0]] * k
        const *= hit[1] ** k
    return names, const


def _pseudo(target0: sympy.Expr, eqs: list[tuple[str, sympy.Expr, Term]],
            fpolys: Mapping[str, sympy.Expr], back: Mapping[sympy.Symbol, Term]
            ) -> Certificate | None:
    """Eliminate variables from the goal by pseudo-division.

    A pool holds members of the hypotheses' ideal, each with its cofactors (the
    equations themselves, and equations derived from them by eliminating a
    variable: no nonzero condition is needed to derive a member). The goal t is
    divided only by a member linear in some variable whose leading coefficient is
    a constant times a product of nonzero hypotheses: that product joins the
    multiplier M. Invariant: M t0 - sum c_i h_i = t. Success when t is 0."""
    pool = [(h, {n: sympy.Integer(1)}) for n, h, _ in eqs]
    t, mult = sympy.expand(target0), list[str]()
    coeffs: dict[str, sympy.Expr] = {}
    used: set[int] = set()
    # Variables of nonzero hypotheses are the parameters: eliminate the others first.
    params = {v for g in fpolys.values() for v in g.free_symbols}

    def order(vs: set[sympy.Symbol]) -> list[sympy.Symbol]:
        return sorted(vs, key=lambda v: (v in params, str(v)))
    for _ in range(4 * len(eqs) + 4):
        if t == 0:
            return _cert(mult, tuple((n, _to_term(c, back))
                                                  for n, c in coeffs.items() if c != 0))
        step = next(((i, e, cf, x, f) for x in order(t.free_symbols)
                     for i, (e, cf) in enumerate(pool)
                     if i not in used and sympy.degree(e, x) == 1
                     and (f := _factors_of(sympy.expand(e.coeff(x, 1)), fpolys)) is not None),
                    None)
        if step is not None:
            i, e, cf, x, (names, const) = step
            used.add(i)
            d = sympy.degree(t, x)
            q, r = sympy.pdiv(t, e, x)              # lc^d t = q e + r, r free of x
            scale = sympy.Integer(1) / const ** d
            lc_d = sympy.expand(e.coeff(x, 1) ** d)
            coeffs = {n: sympy.expand(c * lc_d * scale) for n, c in coeffs.items()}
            for n, c in cf.items():
                coeffs[n] = sympy.expand(coeffs.get(n, 0) + q * c * scale)
            mult += names * d
            t = sympy.expand(r * scale)
            continue
        # Derive a member: in some member linear in a goal variable, eliminate a
        # variable of its leading coefficient by another member linear in it.
        new = None
        for x in order(t.free_symbols):
            for j, (e, cf) in enumerate(pool):
                if j in used or sympy.degree(e, x) != 1:
                    continue
                for y in sorted(sympy.expand(e.coeff(x, 1)).free_symbols, key=str):
                    g = next(((g, gc) for k, (g, gc) in enumerate(pool) if k != j
                              and k not in used
                              and sympy.degree(g, y) == 1 and sympy.degree(g, x) == 0), None)
                    if g is None:
                        continue
                    q, r = sympy.pdiv(e, g[0], y)    # lc_g^d e = q g + r
                    lc_d = sympy.expand(g[0].coeff(y, 1) ** sympy.degree(e, y))
                    rc = {n: sympy.expand(c * lc_d) for n, c in cf.items()}
                    for n, c in g[1].items():
                        rc[n] = sympy.expand(rc.get(n, 0) - q * c)
                    r = sympy.expand(r)
                    if r != 0 and all(sympy.expand(r - o) != 0 for o, _ in pool):
                        new = (r, rc)
                        break
                if new:
                    break
            if new:
                break
        if new is None:
            return None
        pool.append(new)
    return None


def _try(target: sympy.Expr, eqs: list[tuple[str, sympy.Expr, Term]], gens: list[sympy.Symbol],
         back: Mapping[sympy.Symbol, Term], fs: tuple[str, ...], op: str) -> Certificate | None:
    if not gens:
        return None
    if sympy.expand(target) == 0:                 # an identity: no ideal part needed
        return _cert(fs)
    hs = [e for _, e, _ in eqs if e != 0]
    names = [n for n, e, _ in eqs if e != 0]
    if hs:
        qs, r = sympy.reduced(target, hs, *gens, order="lex")
    else:
        qs, r = [], target
    coeffs = tuple((n, _to_term(q, back)) for n, q in zip(names, qs, strict=True) if q != 0)
    r = sympy.expand(r)
    if r == 0:
        return _cert(fs, coeffs)
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
            return _cert(fs, tuple(merged.items()), (sq,))
    return None


def _square(r: sympy.Expr, back: Mapping[sympy.Symbol, Term]) -> tuple[Fraction, Term] | None:
    const, facs = sympy.factor_list(r)
    if const < 0 or any(k % 2 for _, k in facs):
        return None
    q = sympy.Integer(1)
    for f, k in facs:
        q = q * f ** (k // 2)
    return Fraction(int(sympy.Rational(const).p), int(sympy.Rational(const).q)), _to_term(q, back)
