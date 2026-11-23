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
import dataclasses
import hashlib
import itertools
import re
from collections.abc import Mapping
from fractions import Fraction

import sympy

from ..raw.certificate import ATOMS, Certificate, Poly, check, poly
from ..raw.formula import Unsupported
from ..raw.terms import Compound, Num, Str, Term


def comparisons(f: Term, name: str) -> list[tuple[str, Term]]:
    """The top-level comparison conjuncts of a formula, named name, name#2, ..."""
    parts = list(f.args) if isinstance(f, Compound) and f.functor == "f.and" else [f]
    out = [p for p in parts if isinstance(p, Compound) and p.functor in ("f.cmp", "f.isint")]
    return [(name if i == 0 else f"{name}#{i + 1}", p) for i, p in enumerate(out)]


def _vars(t: Term, out: dict[str, Term]) -> None:
    """The ring's variables in t, by their normal-form names: properties, pi, exp atoms,
    and sqrt(k) atoms of surd values (each with the relation sqrt(k)^2 = k)."""
    if isinstance(t, Compound):
        if t.functor in ("f.p", "f.at", "f.v", "f.pi"):
            out[str(t)] = t
            return
        if t.functor == "f.surd":
            for k in t.args[0::2]:
                if isinstance(k, Num) and k.value != 1:
                    out[f"sqrt({k.value})"] = Compound("f.surd", (k, Num(Fraction(1))))
            return
        if t.functor in ("f.exp", "f.ln") or (t.functor == "/" and not (
                isinstance(t.args[1], Num) and not t.args[1].dims)):
            with contextlib.suppress(Unsupported, StopIteration, IndexError):
                p = poly(t if t.functor != "/" else Compound("/", (Num(Fraction(1)), t.args[1])))
                if len(p) == 1 and next(iter(p.values())) == 1:
                    out[next(iter(p))[0][0]] = t if t.functor != "/" else \
                        Compound("/", (Num(Fraction(1)), t.args[1]))
        for a in t.args:
            _vars(a, out)


def _poly_term(p: Poly, terms: Mapping[str, Term]) -> Term:
    """A term whose normal form is p (variables by their names in terms, or atoms)."""
    out: Term = Num(Fraction(0))
    for m, c in sorted(p.items()):
        t: Term = Num(c)
        for v, k in m:
            vt = terms[v] if v in terms else _atom_term(v, terms)
            for _ in range(k):
                t = Compound("*", (t, vt))
        out = Compound("+", (out, t))
    return out


def _atom_term(name: str, terms: Mapping[str, Term]) -> Term:
    kind, u = ATOMS[name]
    arg = _poly_term(u, terms)
    return Compound("/", (Num(Fraction(1)), arg)) if kind == "inv" else \
        Compound(f"f.{kind}", (arg,))


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
          squares: tuple[tuple[Fraction, Term], ...] = (),
          wsquares: tuple[tuple[Fraction, tuple[str, ...], Term], ...] = (),
          sums: tuple[tuple[tuple[Term, tuple[str, ...], Term | None], ...], ...] = ()
          ) -> Certificate:
    """A certificate; the pseudo-factor "@pi" becomes a constant the checker signs, and
    the pseudo-equations "@sqrt(k)" (sqrt(k)^2 = k) are dropped: the checker's normal
    form reduces by them itself."""
    return Certificate(tuple(n for n in names if n != "@pi"),
                       tuple((n, c) for n, c in coeffs if not n.startswith("@sqrt(")), squares,
                       tuple(PI for n in names if n == "@pi"), wsquares, sums=sums)


def find(goal: Term, hyps: Mapping[str, Term]) -> Certificate | None:
    try:
        return _find(goal, hyps)
    except (Unsupported, sympy.PolynomialError, sympy.CoercionFailed, ValueError,
            NotImplementedError, KeyError):
        return None


def _find(goal: Term, hyps: Mapping[str, Term]) -> Certificate | None:
    if not (isinstance(goal, Compound) and goal.functor == "f.cmp"):
        return None
    lhs0 = goal.args[1]
    if isinstance(lhs0, Compound) and lhs0.functor == "f.sum":     # by induction on n
        n = lhs0.args[2]
        isint = next((k for k, h in hyps.items() if h == Compound("f.isint", (n,))), None)
        nonneg = next((k for k, h in hyps.items()
                       if h == Compound("f.cmp", (Str(">="), n, Num(Fraction(0))))), None)
        return Certificate(induction=(isint, nonneg)) if isint and nonneg else None
    hyps = {k: h for k, h in hyps.items() if isinstance(h, Compound) and h.functor == "f.cmp"}
    op = goal.args[0].value if isinstance(goal.args[0], Str) else ""
    if op not in ("=", ">=", "<="):
        return None
    lhs, rhs = (goal.args[1], goal.args[2]) if op != "<=" else (goal.args[2], goal.args[1])
    terms: dict[str, Term] = {}
    for t in (goal, *hyps.values()):
        _vars(t, terms)
    # Atoms that calculus makes (inv(u) from d ln(u), ...), and inv(u) for each ln(u).
    for t in (goal, *hyps.values()):
        with contextlib.suppress(Unsupported, KeyError):
            for m in poly(Compound("-", (t.args[1], t.args[2]))):  # type: ignore[union-attr]
                for v, _ in m:
                    if v not in terms and v in ATOMS:
                        terms[v] = _atom_term(v, terms)
    for nm in [n for n in terms if n in ATOMS and ATOMS[n][0] == "ln"]:
        inv = next(iter(poly(Compound("/", (Num(Fraction(1)), _poly_term(ATOMS[nm][1],
                                                                           terms))))))
        if len(inv) == 1 and inv[0][0] not in terms:
            terms[inv[0][0]] = _atom_term(inv[0][0], terms)
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
    for nm, at in terms.items():                    # sqrt(k)^2 = k, for the finder
        if nm.startswith("sqrt("):
            r = Fraction(nm[5:-1])
            eqs.append((f"@{nm}", syms[nm] ** 2 - sympy.Rational(r.numerator, r.denominator),
                        Compound("f.cmp", (Str("="), Compound("*", (at, at)), Num(r)))))
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
    positive = {n: g for n, g in fpolys.items() if n != "@pi" and _op(hyps[n]) in (">", "<")}
    # Witnesses that each ln/inv argument u is > 0, and u inv(u) - 1 as "@pos<i>".
    wits: list[tuple[Term, Term, tuple[str, ...], tuple[Term, ...]]] = []
    for nm in [n for n in terms if n in ATOMS and ATOMS[n][0] == "inv"]:
        u = ATOMS[nm][1]
        w = _witness(_to_sympy(u, syms), positive, {syms[k]: terms[k] for k in terms
                                                     if k in ATOMS and ATOMS[k][0] == "exp"})
        if w is not None:
            c, names, exps = w
            eqs.append((f"@pos{len(wits)}", sympy.expand(_to_sympy(u, syms) * syms[nm] - 1),
                        Compound("f.cmp", (Str("="), Num(Fraction(0)), Num(Fraction(0))))))
            wits.append((_poly_term(u, terms), Num(c), names, exps))

    def fin(cert: Certificate) -> Certificate:
        return dataclasses.replace(cert, positive=tuple(wits))
    factors = factors + (["@pi"] if "@pi" in fpolys else [])
    for k in range(3):
        for fs in itertools.combinations(factors, k):
            m = sympy.Integer(1)
            for name in fs:
                m = m * fpolys[name]
            target = sympy.expand(m * target0)
            for gens in orders:
                cert = _try(target, eqs, gens, back, fs, op, positive)
                if cert is not None and check(goal, hyps, fin(cert)):
                    return fin(cert)
    if op == "=":
        posvar = {g: n for n, g in sorted(positive.items()) if isinstance(g, sympy.Symbol)}
        consts = {syms[k] for k in terms if k.startswith("sqrt(") or k == str(PI)}
        cert = _pseudo(target0, eqs, fpolys, back, posvar, consts)
        if cert is not None and check(goal, hyps, fin(cert)):
            return fin(cert)
    return None


def _witness(u: sympy.Expr, positive: Mapping[str, sympy.Expr],
             exps: Mapping[sympy.Symbol, Term]
             ) -> tuple[Fraction, tuple[str, ...], tuple[Term, ...]] | None:
    """u as c * (positive hypotheses) * (exp atoms) with c > 0, or None."""
    const, facs = sympy.factor_list(u)
    names: list[str] = []
    xs: list[Term] = []
    for f, k in facs:
        if f in exps:
            xs += [exps[f]] * k
            continue
        hit = next(((n, s) for n, g in sorted(positive.items()) for s in (1, -1)
                    if sympy.expand(g - s * f) == 0), None)
        if hit is None:
            return None
        names += [hit[0]] * k
        const *= hit[1] ** k
    if not const.is_Rational or const <= 0:
        return None
    return _frac(const), tuple(names), tuple(xs)


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


def _possum(g: sympy.Expr, back: Mapping[sympy.Symbol, Term],
            posvar: Mapping[sympy.Symbol, str], consts: set[sympy.Symbol]
            ) -> tuple[tuple[Term, tuple[str, ...], Term | None], ...] | None:
    """g as a sum of terms c * h1 * ... (c > 0 a constant, possibly with sqrt(k) or pi;
    each h a variable with a stated positive hypothesis), or None."""
    gens = sorted(g.free_symbols, key=str)
    if not gens:
        return None
    out = []
    for monom, coeff in sympy.Poly(g, *gens).terms():
        if coeff <= 0:
            return None
        c: Term = Num(Fraction(int(coeff.p), int(coeff.q)))
        names: list[str] = []
        for v, k in zip(gens, monom, strict=True):
            if v in consts:
                for _ in range(k):
                    c = Compound("*", (c, back[v]))
            elif v in posvar:
                names += [posvar[v]] * k
            elif k:
                return None
        out.append((c, tuple(names), None))
    return tuple(out)


def _posmult(g: sympy.Expr, back: Mapping[sympy.Symbol, Term],
             posvar: Mapping[sympy.Symbol, str], consts: set[sympy.Symbol]
             ) -> tuple[tuple[Term, tuple[str, ...], Term | None], ...] | None:
    """g > 0 as a positive sum, or as squares (exact LDL of its quadratic part) plus a
    positive sum of the rest."""
    rep = _possum(g, back, posvar, consts)
    if rep is not None:
        return rep
    xs = sorted(g.free_symbols - set(consts), key=str)
    if not xs:
        return None
    pg = sympy.Poly(g, *xs)
    quad = sum((c * sympy.prod([x ** k for x, k in zip(xs, m, strict=True)])
                for m, c in pg.terms() if sum(m) == 2), sympy.Integer(0))
    rest = _possum(sympy.expand(g - quad), back, posvar, consts)
    if rest is None or quad == 0:
        return None
    n = len(xs)
    gram = [[sympy.Integer(0)] * n for _ in range(n)]
    pq = sympy.Poly(quad, *xs)
    for i in range(n):
        for j in range(i, n):
            c = pq.coeff_monomial(xs[i] * xs[j])
            gram[i][j] = gram[j][i] = c if i == j else c / 2
    squares: list[tuple[Term, tuple[str, ...], Term | None]] = []
    for k in range(n):                              # exact LDL, pivoting in order
        d = gram[k][k]
        if d < 0 or (d == 0 and any(gram[k][j] != 0 for j in range(k + 1, n))):
            return None
        if d == 0:
            continue
        row = [gram[k][j] / d for j in range(n)]
        squares.append((Num(_frac(d)), (), _to_term(sympy.expand(
            sum((row[j] * xs[j] for j in range(k, n)), sympy.Integer(0))), back)))
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                gram[i][j] -= d * row[i] * row[j]
    return (*rest, *squares)


def _pseudo(target0: sympy.Expr, eqs: list[tuple[str, sympy.Expr, Term]],
            fpolys: Mapping[str, sympy.Expr], back: Mapping[sympy.Symbol, Term],
            posvar: Mapping[sympy.Symbol, str] | None = None,
            consts: set[sympy.Symbol] | None = None) -> Certificate | None:
    """Eliminate variables from the goal by pseudo-division.

    A pool holds members of the hypotheses' ideal, each with its cofactors (the
    equations themselves, and equations derived from them by eliminating a
    variable: no nonzero condition is needed to derive a member). The goal t is
    divided only by a member linear in some variable whose leading coefficient is
    a constant times a product of nonzero hypotheses: that product joins the
    multiplier M. Invariant: M t0 - sum c_i h_i = t. Success when t is 0.
    When stuck on t = a y + b, t is multiplied by its conjugate a y - b if that is a
    positive sum (D-030: a surd value's positive root), which joins M."""
    posvar, consts = posvar or {}, consts or set()
    roots = [(v, e) for n, e, _ in eqs if n.startswith("@sqrt(")
             for v in e.free_symbols]

    def red(e: sympy.Expr) -> sympy.Expr:              # by sqrt(k)^2 = k
        for v, rel in roots:
            e = sympy.rem(sympy.expand(e), rel, v)
        return sympy.expand(e)
    pool = [(h, {n: sympy.Integer(1)}) for n, h, _ in eqs]
    t, mult = sympy.expand(target0), list[str]()
    sums: list[tuple[tuple[Term, tuple[str, ...], Term | None], ...]] = []
    coeffs: dict[str, sympy.Expr] = {}
    used: set[int] = set()
    # Variables of nonzero hypotheses are the parameters: eliminate the others first.
    params = {v for g in fpolys.values() for v in g.free_symbols}

    def order(vs: set[sympy.Symbol]) -> list[sympy.Symbol]:
        return sorted(vs, key=lambda v: (v in params, str(v)))

    def eliminate(i: int, x: sympy.Symbol) -> None:
        """Eliminate x from every other unused member by member i (ideal members stay
        ideal members, with their cofactors; no nonzero condition is needed)."""
        e, cf = pool[i]
        lc = sympy.LC(sympy.Poly(e, x))
        for j, (g, gcf) in enumerate(pool):
            if j == i or j in used or sympy.degree(g, x) < sympy.degree(e, x):
                continue
            q2, r2 = sympy.pdiv(g, e, x)            # lc^d2 g = q2 e + r2
            lc_d2 = sympy.expand(lc ** (sympy.degree(g, x) - sympy.degree(e, x) + 1))
            rc = {n: sympy.expand(c * lc_d2) for n, c in gcf.items()}
            for n, c in cf.items():
                rc[n] = sympy.expand(rc.get(n, 0) - q2 * c)
            pool[j] = (red(r2), {n: red(c) for n, c in rc.items()})
            if pool[j][0] == 0:
                used.add(j)

    # Pre-pass (Gauss): a member linear in a variable with a constant leading
    # coefficient defines it; eliminate it from the other members, non-parameters first.
    pivots: set[int] = set()
    progress = True
    while progress:
        progress = False
        for i, (e, _) in enumerate(pool):
            if i in pivots or i in used:
                continue
            x = next((v for v in order(e.free_symbols - set(consts))
                      if sympy.degree(e, v) == 1 and sympy.LC(sympy.Poly(e, v)).is_number
                      and any(j != i and j not in used and v in g.free_symbols
                              for j, (g, _) in enumerate(pool))), None)
            if x is not None:
                pivots.add(i)
                eliminate(i, x)
                progress = True
    for _ in range(4 * len(eqs) + 4):
        t = red(t)
        if t == 0:
            return _cert(mult, tuple((n, _to_term(c, back))
                                     for n, c in coeffs.items() if c != 0), sums=tuple(sums))
        step = next(((i, e, cf, x, f) for x in order(t.free_symbols - set(consts))
                     for i, (e, cf) in enumerate(pool)
                     if i not in used and 1 <= sympy.degree(e, x) <= sympy.degree(t, x)
                     and (f := _factors_of(sympy.LC(sympy.Poly(e, x)), fpolys)) is not None),
                    None)
        if step is not None:
            i, e, cf, x, (names, const) = step
            used.add(i)
            d = sympy.degree(t, x) - sympy.degree(e, x) + 1
            q, r = sympy.pdiv(t, e, x)              # lc^d t = q e + r
            scale = sympy.Integer(1) / const ** d
            lc_d = sympy.expand(sympy.LC(sympy.Poly(e, x)) ** d)
            coeffs = {n: sympy.expand(c * lc_d * scale) for n, c in coeffs.items()}
            for n, c in cf.items():
                coeffs[n] = sympy.expand(coeffs.get(n, 0) + q * c * scale)
            mult += names * d
            t = sympy.expand(r * scale)
            eliminate(i, x)                         # triangularize the pool too
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
        if new is None:                    # a member t * Q with Q > 0: Q joins M
            hit = None
            for e, cf in (p for j, p in enumerate(pool) if j not in used):
                gens = sorted(e.free_symbols | t.free_symbols, key=str)
                if not gens or not t.free_symbols:
                    continue
                qq, rr = sympy.div(e, t, *gens)
                for sgn in (1, -1):
                    rep = _posmult(red(sgn * qq), back, posvar, consts) if rr == 0 else None
                    if rep is not None:
                        hit = (sgn * qq, sgn, cf, rep)
                        break
                if hit:
                    break
            if hit is not None:
                qq, sgn, cf, rep = hit
                coeffs = {n: red(c * qq) for n, c in coeffs.items()}
                for n, c in cf.items():
                    coeffs[n] = red(coeffs.get(n, 0) + sgn * c)
                sums.append(rep)
                t = sympy.Integer(0)
                continue
            conj = None
            for y in order(t.free_symbols - set(consts)) if len(sums) < 2 else []:
                if sympy.degree(t, y) != 1:
                    continue
                g0 = sympy.expand(t.coeff(y, 1) * y - t.coeff(y, 0))
                for g in (g0, -g0):
                    rep = _possum(red(g), back, posvar, consts)
                    if rep is not None:
                        conj = (g, rep)
                        break
                if conj:
                    break
            if conj is None:
                return None
            g, rep = conj
            t = red(t * g)
            coeffs = {n: red(c * g) for n, c in coeffs.items()}
            sums.append(rep)
            continue
        pool.append(new)
    return None


def _try(target: sympy.Expr, eqs: list[tuple[str, sympy.Expr, Term]], gens: list[sympy.Symbol],
         back: Mapping[sympy.Symbol, Term], fs: tuple[str, ...], op: str,
         pos: Mapping[str, sympy.Expr] | None = None) -> Certificate | None:
    pos = pos or {}
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
            sos = _sos(rr, back, pos)
            if sos is None:
                continue
            extra = ((name, _to_term(sympy.Integer(sign), back)),) if name else ()
            merged = dict(coeffs)
            for n, t in extra:
                merged[n] = t if n not in merged else Compound("+", (merged[n], t))
            return _cert(fs, tuple(merged.items()), *sos)
    return None


def _op(h: Term) -> str:
    return h.args[0].value if isinstance(h, Compound) and isinstance(h.args[0], Str) else ""


def _frac(x: sympy.Expr) -> Fraction:
    r = sympy.Rational(x)
    return Fraction(int(r.p), int(r.q))


def _sos(r: sympy.Expr, back: Mapping[sympy.Symbol, Term], pos: Mapping[str, sympy.Expr]
         ) -> tuple[tuple[tuple[Fraction, Term], ...],
                    tuple[tuple[Fraction, tuple[str, ...], Term], ...]] | None:
    """r as a sum of squares (D-027): one square; a quadratic by exact LDL of its Gram
    matrix; or a constant times positive hypotheses times a square."""
    sq = _square(r, back)
    if sq is not None:
        return (sq,), ()
    xs = sorted(r.free_symbols, key=str)
    if xs and sympy.Poly(r, *xs).total_degree() == 2:
        z = [sympy.Integer(1), *xs]
        poly2 = sympy.Poly(r, *xs)
        n = len(z)
        g = [[sympy.Integer(0)] * n for _ in range(n)]
        for i in range(n):
            for j in range(i, n):
                c = poly2.coeff_monomial(z[i] * z[j])
                g[i][j] = g[j][i] = c if i == j else c / 2
        squares = []
        for k in range(n):                       # exact LDL, pivoting in order
            d = g[k][k]
            if d < 0:
                break
            if d == 0:
                if any(g[k][j] != 0 for j in range(k + 1, n)):
                    break
                continue
            row = [g[k][j] / d for j in range(n)]
            squares.append((_frac(d), _to_term(sympy.expand(
                sum((row[j] * z[j] for j in range(k, n)), sympy.Integer(0))), back)))
            for i in range(k + 1, n):
                for j in range(k + 1, n):
                    g[i][j] -= d * row[i] * row[j]
        else:
            return tuple(squares), ()
    const, facs = sympy.factor_list(r)
    if const < 0:
        return None
    names, q = [], sympy.Integer(1)
    for f, k in facs:
        hit = next((nm for nm, g2 in sorted(pos.items()) if sympy.expand(g2 - f) == 0), None)
        if hit is not None:
            names += [hit] * k
        elif k % 2 == 0:
            q = q * f ** (k // 2)
        else:
            return None
    if not names:
        return None
    return (), ((_frac(const), tuple(names), _to_term(q, back)),)


def _square(r: sympy.Expr, back: Mapping[sympy.Symbol, Term]) -> tuple[Fraction, Term] | None:
    const, facs = sympy.factor_list(r)
    if const < 0 or any(k % 2 for _, k in facs):
        return None
    q = sympy.Integer(1)
    for f, k in facs:
        q = q * f ** (k // 2)
    return Fraction(int(sympy.Rational(const).p), int(sympy.Rational(const).q)), _to_term(q, back)
