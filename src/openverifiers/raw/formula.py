"""Object-layer formulas: concept-class definitions and their exact ground evaluator.

A ``fact type`` lowers to a :class:`ClassDef`: property names, the named
invariants (own and inherited) and the named theorems. Every formula is an
ordinary RawOV term, so it prints and parses with ``openverifiers.rawtext`` and
canonical JSON (``raw/canon.py``).

Formula terms::

    f.and(F, ...)   f.or(F, ...)   f.not(F)   f.cmp("op", E, E)
    f.exists("v", C, F)   f.forall("v", C, F)   f.forall_idx("i", C, F)

Expression terms::

    numbers, f.v("name") (bound variable), f.p("name") (property),
    f.tuple(E..), f.set(E..), f.list(E..), f.idx(C, E) (index mod length),
    f.at(E, k) (tuple component), + - * / ^ abs min max, f.count(C),
    f.dist(P, P), f.dist2(P, P) (squared), f.angle(P, P, P), f.cycles(C), f.orderings(C),
    f.subsets(C, k), f.pairs(C),
    f.integral(E, X, U) (the integral of E in the variable X from 0 to U's value),
    f.deriv(E, X, U) (dE/dX at X = U); X is a variable designator (f.p("t") or a
    component's f.at(..)), and E must be a polynomial in it

The evaluator here re-checks every instance any solver proposes. It is exact:
``dist`` values are kept as square roots of rationals and compared by
squaring, and ``angle(a, b, c) = θ deg`` is decided on the dot product for
the angles whose cosine squared is rational. Generators enumerate *every*
ordering: symmetry pruning is the solver's business, never the checker's.
Anything outside this fragment raises :class:`Unsupported`.

Trusted code.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, permutations

from . import interval as I
from . import qpi as Q
from .builtins import ARITH, apply_op
from .surd import Surd, SurdError
from .terms import Compound, Num, Str, Term, make_dims, order_key

DEG = make_dims({"deg": 1})
#: angle in degrees -> (sign of cos, cos^2)
COS2: dict[int, tuple[int, Fraction]] = {
    0: (1, Fraction(1)), 30: (1, Fraction(3, 4)), 45: (1, Fraction(1, 2)), 60: (1, Fraction(1, 4)),
    90: (0, Fraction(0)), 120: (-1, Fraction(1, 4)), 135: (-1, Fraction(1, 2)),
    150: (-1, Fraction(3, 4)), 180: (-1, Fraction(1)),
}


class Unsupported(ValueError):
    """The formula leaves the exact fragment (or is ill-typed at run time)."""


@dataclass(frozen=True, slots=True)
class ClassDef:
    name: str
    props: tuple[str, ...]
    invariants: tuple[tuple[str, Term], ...]   # qualified name -> formula, ancestors first
    theorems: tuple[tuple[str, Term], ...]


@dataclass(frozen=True, slots=True)
class _Root:
    """The non-negative square root of an irrational surd (a nested radical): only
    compared, by its square."""

    sq: Surd


@dataclass(frozen=True, slots=True)
class _Angle:
    dot: Surd
    norms: Surd              # |u|^2 * |w|^2


Value = Term | Surd | _Root | _Angle | I.Iv | Q.QPi


def _iv(v: Value) -> I.Iv:
    if isinstance(v, I.Iv):
        return v
    if isinstance(v, Surd):
        return I.from_surd(v.terms)
    if isinstance(v, Q.QPi):
        return v.iv()
    return I.Iv.of(_rat(v))


def _surd(v: Value) -> Surd:
    """A dimensionless number as a surd; Unsupported for anything else."""
    if isinstance(v, Surd):
        return v
    if isinstance(v, Num) and not v.dims:
        return Surd.of(v.value)
    raise Unsupported(f"not a plain number: {v}")


def _value(s: Surd) -> Value:
    r = s.rational()
    return Num(r) if r is not None else s


_SURD_OPS = {"+": Surd.__add__, "-": Surd.__sub__, "*": Surd.__mul__}


def make_set(items: list[Term]) -> Compound:
    uniq: dict[Term, None] = dict.fromkeys(items)
    return Compound("f.set", tuple(sorted(uniq, key=order_key)))


def _seq(v: Value) -> tuple[Term, ...]:
    if isinstance(v, Compound) and v.functor in ("f.set", "f.list", "f.tuple"):
        return v.args
    raise Unsupported(f"not a collection: {v}")


def _coord(a: Term) -> Surd:
    if isinstance(a, Num) and not a.dims:
        return Surd.of(a.value)
    if isinstance(a, Compound) and a.functor == "f.surd" and len(a.args) % 2 == 0 \
            and all(isinstance(x, Num) and not x.dims for x in a.args):
        nums = [x.value for x in a.args if isinstance(x, Num)]
        out = Surd.of(Fraction(0))
        for k, c in zip(nums[0::2], nums[1::2], strict=True):
            out = out + Surd.sqrt(k) * Surd.of(c)
        return out
    raise Unsupported(f"not a coordinate: {a}")


def _point(v: Value) -> tuple[Surd, ...]:
    if isinstance(v, Compound) and v.functor == "f.tuple":
        try:
            return tuple(_coord(a) for a in v.args)
        except SurdError as e:
            raise Unsupported(str(e)) from None
    raise Unsupported(f"not a point: {v}")


def _sub(a: tuple[Surd, ...], b: tuple[Surd, ...]) -> tuple[Surd, ...]:
    if len(a) != len(b):
        raise Unsupported("points of different dimension")
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _dot(a: tuple[Surd, ...], b: tuple[Surd, ...]) -> Surd:
    return sum((x * y for x, y in zip(a, b, strict=True)), Surd.of(Fraction(0)))


def _term_of(s: Surd) -> Term:
    r = s.rational()
    if r is not None:
        return Num(r)
    return Compound("f.surd", tuple(x for k, c in s.terms for x in (Num(Fraction(k)),
                                                                       Num(c))))


def subst(t: Term, x: Term, val: Term) -> Term:
    """t with the variable designator x replaced by val. An inner integral or
    derivative in x binds x: only its upper limit is substituted."""
    if t == x:
        return val
    if isinstance(t, Compound):
        if t.functor in ("f.integral", "f.deriv") and t.args[1] == x:
            return Compound(t.functor, (t.args[0], x, subst(t.args[2], x, val)))
        return Compound(t.functor, tuple(subst(a, x, val) for a in t.args))
    return t


def _degree(t: Term, x: Term) -> int:
    """An upper bound on t's degree as a polynomial in the variable x; Unsupported if
    t is not polynomial in it."""
    if t == x:
        return 1
    if not isinstance(t, Compound) or not _mentions(t, x):
        return 0
    f, a = t.functor, t.args
    if f in ("f.integral", "f.deriv"):
        if a[1] == x and a[2] == x:              # bound in x, evaluated at x
            d = _degree(a[0], x)
            return d + 1 if f == "f.integral" else max(d - 1, 0)
        raise Unsupported(f"nested calculus in {x} with another variable or limit")
    ds = [_degree(y, x) for y in a]
    if f in ("+", "-"):
        return max(ds)
    if f == "*":
        return sum(ds)
    if f == "/" and ds[1] == 0:
        return ds[0]
    if f == "^" and isinstance(a[1], Num) and a[1].value.denominator == 1 and a[1].value >= 0:
        return ds[0] * int(a[1].value)
    raise Unsupported(f"{f} is not polynomial in {x}")


def _subterms(t: Term) -> Iterator[Term]:
    yield t
    for a in t.args if isinstance(t, Compound) else ():
        yield from _subterms(a)


def _mentions(t: Term, x: Term) -> bool:
    return t == x or (isinstance(t, Compound) and any(_mentions(y, x) for y in t.args))


def _coefficients(ys: list[Fraction]) -> list[Fraction]:
    """c with sum(c[k] * i^k) = ys[i] for i = 0..n-1 (exact Gaussian elimination)."""
    n = len(ys)
    m = [[Fraction(i) ** k for k in range(n)] + [ys[i]] for i in range(n)]
    for col in range(n):
        piv = next(r for r in range(col, n) if m[r][col] != 0)
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[r][col] != 0:
                k = m[r][col] / m[col][col]
                m[r] = [x - k * y for x, y in zip(m[r], m[col], strict=True)]
    return [m[k][n] / m[k][k] for k in range(n)]


def generate(name: str, items: tuple[Term, ...], k: int | None = None) -> Iterator[Term]:
    """Elements of a collection generator, all of them, in a fixed order."""
    if name in ("f.cycles", "f.orderings"):
        for p in permutations(items):
            yield Compound("f.list", p)
    elif name == "f.subsets" and k is not None:
        for c in combinations(items, k):
            yield Compound("f.set", c)
    elif name == "f.pairs":
        for c in combinations(items, 2):
            yield Compound("f.tuple", c)
    else:
        raise Unsupported(f"unknown generator {name}")


class _Eval:
    def __init__(self, props: Mapping[str, Term], env: Mapping[str, Term] | None = None) -> None:
        self.props = props
        self.env: dict[str, Term] = dict(env or {})

    def expr(self, t: Term) -> Value:
        if isinstance(t, Num):
            return t
        if not isinstance(t, Compound):
            raise Unsupported(f"unexpected term {t}")
        f, a = t.functor, t.args
        if f in ("f.v", "f.p"):
            key = a[0].value if isinstance(a[0], Str) else ""
            table = self.env if f == "f.v" else self.props
            if key not in table:
                raise Unsupported(f"unbound {key}")
            # Bound variables hold values; properties hold expressions to evaluate.
            return _stored(table[key]) if f == "f.v" else self.expr(table[key])
        if f in ("f.integral", "f.deriv"):
            return self._calculus(f, a)
        if f == "f.valueat":                 # E with the designator x set to c (D-027)
            return self.expr(subst(a[0], a[1], a[2]))
        if f == "f.sum" and isinstance(a[1], Str):   # sum of E for i = 1..n (gap e)
            n = _rat(self.expr(a[2]))
            if n.denominator != 1 or not 0 <= n <= 10_000:
                raise Unsupported("sum needs a whole upper limit in 0..10000")
            return Num(sum((_rat(_Eval(self.props, {**self.env, a[1].value: Num(Fraction(i))})
                                 .expr(a[0])) for i in range(1, int(n) + 1)), Fraction(0)))
        vals = [self.expr(x) for x in a] if f not in ("f.at",) else []
        if f in ("f.tuple", "f.list"):
            return Compound(f, tuple(self._term(v) for v in vals))
        if f == "f.set":
            return make_set([self._term(v) for v in vals])
        if f == "f.at":
            k = a[1]
            seq = _seq(self.expr(a[0]))
            if not isinstance(k, Num) or not 0 <= k.value < len(seq) or k.value.denominator != 1:
                raise Unsupported("bad component index")
            return _stored(seq[int(k.value)])
        if f == "f.idx":
            seq, i = _seq(vals[0]), vals[1]
            if not seq or not isinstance(i, Num) or i.value.denominator != 1:
                raise Unsupported("bad index")
            return _stored(seq[int(i.value) % len(seq)])
        if f == "f.count":
            return Num(Fraction(len(_seq(vals[0]))))
        if f == "f.mod" and _rat(vals[1]) != 0:   # a - b floor(a / b)
            return Num(_rat(vals[0]) % _rat(vals[1]))
        if f == "f.dist":
            d = _sub(_point(vals[0]), _point(vals[1]))
            sq = self._exact(lambda: _dot(d, d))
            assert isinstance(sq, Surd)
            q = sq.rational()
            if q is None:
                return _Root(sq)
            return self._exact(lambda: _value(Surd.sqrt(q)))
        if f == "f.sqrt":
            x = vals[0]
            if not isinstance(x, Num) or x.dims:
                raise Unsupported("sqrt of something other than a rational number")
            return self._exact(lambda: _value(Surd.sqrt(x.value)))
        if f == "f.surd":                     # a solver value: sqrt(k1) c1 + sqrt(k2) c2 ...
            return self._exact(lambda: _value(sum(
                (Surd.sqrt(_rat(vals[i])) * Surd.of(_rat(vals[i + 1]))
                 for i in range(0, len(vals), 2)), Surd.of(Fraction(0)))))
        if f in ("f.pi", "f.qpi"):           # exact in Q(pi) (D-026)
            return self._exact(lambda: Q.PI if f == "f.pi" else Q.value(Q.from_term(a)))
        if f in ("f.exp", "f.ln", "f.sin", "f.cos", "f.iv") or any(isinstance(v, I.Iv)
                                                                  for v in vals):
            return self._numeric(f, vals)
        if f in ARITH and any(isinstance(v, Q.QPi) for v in vals):
            return self._exact(lambda: Q.value(Q.apply(f, vals)))
        if f in ARITH and any(isinstance(v, Surd) for v in vals):
            return self._exact(lambda: _surd_op(f, vals))
        if f == "f.dist2":
            d = _sub(_point(vals[0]), _point(vals[1]))
            return self._exact(lambda: _value(_dot(d, d)))
        if f == "f.angle":
            u = _sub(_point(vals[0]), _point(vals[1]))
            w = _sub(_point(vals[2]), _point(vals[1]))
            return self._exact(lambda: _Angle(_dot(u, w), _dot(u, u) * _dot(w, w)))
        if f in ARITH and all(isinstance(v, Num) for v in vals):
            r = apply_op(f, [v for v in vals if isinstance(v, Num)])
            if r is None:
                raise Unsupported(f"arithmetic failed: {t}")
            return r
        raise Unsupported(f"cannot evaluate {f}")

    @staticmethod
    def _numeric(f: str, vals: list[Value]) -> Value:
        """Rigorous interval arithmetic (exp, ln, pi, stored intervals, mixed arithmetic)."""
        try:
            if f == "f.iv":
                return I.Iv(_rat(vals[0]), _rat(vals[1]))
            xs = [_iv(v) for v in vals]
            if f in ("f.exp", "f.ln", "f.sin", "f.cos"):
                return I.exp(xs[0]) if f == "f.exp" else I.ln(xs[0]) if f == "f.ln" \
                    else I.trig(xs[0], f == "f.cos")
            if f == "-" and len(xs) == 1:
                return -xs[0]
            if f == "^" and isinstance(vals[1], Num) and vals[1].value.denominator == 1 \
                    and vals[1].value >= 0:
                return xs[0].power(int(vals[1].value))
            ops = {"+": I.Iv.__add__, "-": I.Iv.__sub__, "*": I.Iv.__mul__,
                   "/": I.Iv.__truediv__}
            if f in ops and len(xs) == 2:
                return ops[f](xs[0], xs[1])
        except (I.IntervalError, SurdError) as e:
            raise Unsupported(str(e)) from None
        raise Unsupported(f"no interval form for {f}")

    def _calculus(self, f: str, a: tuple[Term, ...]) -> Value:
        """Exact: sample the polynomial at x = 0..degree, recover its coefficients,
        then integrate from 0 (or differentiate) and evaluate at the upper limit.
        The result is linear in the samples, so samples in Q(pi) (D-030) are combined
        with the rational weights of the unit samples."""
        body, var, upper = a
        try:
            deg = _degree(body, var)
        except Unsupported:
            if f != "f.deriv":
                raise
            return self._exact(lambda: self._symbolic_deriv(a))
        x = self.expr(upper)
        ys: list[Num | Q.QPi] = []
        for i in range(deg + 1):
            y = self.expr(subst(body, var, Num(Fraction(i))))
            if not ((isinstance(y, Num) and not y.dims) or isinstance(y, Q.QPi)):
                raise Unsupported("integral or derivative of a non-number")
            ys.append(y)
        if not isinstance(x, Num) or x.dims:
            raise Unsupported(f"the limit {upper} is not a number")

        def at(vs: list[Fraction]) -> Fraction:
            c = _coefficients(vs)
            if f == "f.integral":
                return sum((c[k] * x.value ** (k + 1) / (k + 1) for k in range(len(c))),
                           Fraction(0))
            return sum((k * c[k] * x.value ** (k - 1) for k in range(1, len(c))), Fraction(0))
        if all(isinstance(y, Num) for y in ys):
            return Num(at([y.value for y in ys if isinstance(y, Num)]))
        w = [at([Fraction(i == j) for i in range(len(ys))]) for j in range(len(ys))]

        def combine() -> Value:
            total = Q.to_qpi(Num(Fraction(0)))
            for wj, y in zip(w, ys, strict=True):
                total = total + Q.to_qpi(Num(wj)) * Q.to_qpi(y)
            return Q.value(total)
        return self._exact(combine)

    def _symbolic_deriv(self, a: tuple[Term, ...]) -> Value:
        """d/dx of a body that is not polynomial in x (exp, ln, 1/u, sin, cos): the
        certificate normal form's derivative (raw/certificate.py), evaluated with
        rigorous intervals (D-033)."""
        from .certificate import ATOMS, poly
        names = {str(t): t for t in _subterms(Compound("f.deriv", a))
                 if isinstance(t, Compound) and t.functor in ("f.p", "f.at", "f.v")}

        def ev(p: dict[tuple[tuple[str, int], ...], Fraction]) -> I.Iv:
            out = I.Iv.of(Fraction(0))
            for m, c in p.items():
                term = I.Iv.of(c)
                for v, k in m:
                    kind, u = ATOMS.get(v, ("", {}))
                    y = (I.exp(ev(u)) if kind == "exp" else I.ln(ev(u)) if kind == "ln" else
                         ev(u).inverse() if kind == "inv" else I.trig(ev(u), kind == "cos")
                         if kind else I.sqrt(I.Iv.of(Fraction(v[5:-1]))) if v[:5] == "sqrt("
                         else I.pi() if v == "Compound(functor='f.pi', args=())"
                         else _iv(self.expr(names[v])))
                    term = term * y.power(k)
                out = out + term
            return out
        return ev(poly(Compound("f.deriv", a)))

    @staticmethod
    def _exact(fn: Callable[[], Value]) -> Value:
        try:
            return fn()
        except (SurdError, Q.QPiError) as e:
            raise Unsupported(str(e)) from None

    @staticmethod
    def _term(v: Value) -> Term:
        if isinstance(v, _Angle | _Root):
            raise Unsupported("an angle or nested root cannot be stored in a collection")
        if isinstance(v, I.Iv):
            return Compound("f.iv", (Num(v.lo), Num(v.hi)))
        if isinstance(v, Q.QPi):
            return Q.to_term(v)
        return _term_of(v) if isinstance(v, Surd) else v

    def coll(self, t: Term) -> Iterator[Term]:
        if isinstance(t, Compound) and t.functor in ("f.cycles", "f.orderings", "f.pairs"):
            yield from generate(t.functor, _seq(self.expr(t.args[0])))
        elif isinstance(t, Compound) and t.functor == "f.subsets":
            k = self.expr(t.args[1])
            if not isinstance(k, Num) or k.value.denominator != 1:
                raise Unsupported("subsets needs an integer size")
            yield from generate(t.functor, _seq(self.expr(t.args[0])), int(k.value))
        else:
            yield from _seq(self.expr(t))

    def holds(self, t: Term) -> bool:
        if not isinstance(t, Compound):
            raise Unsupported(f"not a formula: {t}")
        f, a = t.functor, t.args
        if f == "f.and":
            return all(self.holds(x) for x in a)
        if f == "f.or":
            return any(self.holds(x) for x in a)
        if f == "f.not":
            return not self.holds(a[0])
        if f == "f.cmp" and isinstance(a[0], Str):
            return compare(a[0].value, self.expr(a[1]), self.expr(a[2]))
        if f == "f.isint":                   # a whole number (Integer properties, D-027)
            v = self.expr(a[0])
            return isinstance(v, Num) and not v.dims and v.value.denominator == 1
        if f in ("f.exists", "f.forall", "f.forall_idx") and isinstance(a[0], Str):
            var = a[0].value
            if f == "f.forall_idx":
                n = len(_seq(self.expr(a[1])))
                items: list[Term] = [Num(Fraction(i)) for i in range(n)]
            else:
                items = list(self.coll(a[1]))
            saved = self.env.get(var)
            results = []
            for x in items:
                self.env[var] = x
                results.append(self.holds(a[2]))
                if results[-1] == (f == "f.exists"):
                    break
            if saved is None:
                self.env.pop(var, None)
            else:
                self.env[var] = saved
            return any(results) if f == "f.exists" else all(results)
        raise Unsupported(f"unknown formula {f}")


def _ordered(op: str, x: Fraction, y: Fraction) -> bool:
    return {"=": x == y, "!=": x != y, "<": x < y, "<=": x <= y,
            ">": x > y, ">=": x >= y}[op]


def _stored(t: Term) -> Value:
    """A value read out of a tuple, list or binding: an exact surd term becomes a Surd."""
    if isinstance(t, Compound) and t.functor in ("f.surd", "f.qpi"):
        try:
            return _value(_coord(t)) if t.functor == "f.surd" else Q.value(Q.from_term(t.args))
        except (SurdError, Q.QPiError) as e:
            raise Unsupported(str(e)) from None
    return t


def _rat(v: Value) -> Fraction:
    if isinstance(v, Num) and not v.dims:
        return v.value
    raise Unsupported(f"not a rational number: {v}")


def _surd_op(f: str, vals: list[Value]) -> Value:
    xs = [_surd(v) for v in vals]
    if f == "-" and len(xs) == 1:
        return _value(-xs[0])
    if f in _SURD_OPS and len(xs) == 2:
        return _value(_SURD_OPS[f](xs[0], xs[1]))
    if f == "/" and len(xs) == 2:
        return _value(xs[0] * xs[1].inverse())
    if f == "^" and len(xs) == 2 and (k := xs[1].rational()) is not None \
            and k.denominator == 1 and k >= 0:
        out = Surd.of(Fraction(1))
        for _ in range(int(k)):
            out = out * xs[0]
        return _value(out)
    raise Unsupported(f"cannot apply {f} to square roots")


def compare(op: str, a: Value, b: Value) -> bool:
    if op not in ("=", "!=", "<", "<=", ">", ">="):
        raise Unsupported(f"unknown comparison {op}")
    if isinstance(a, I.Iv) or isinstance(b, I.Iv):     # decided only when separated
        d = I.decide(op, _iv(a), _iv(b))
        if d is None:
            raise Unsupported("the intervals overlap: not decided numerically")
        return d
    if isinstance(a, Q.QPi) or isinstance(b, Q.QPi):
        try:
            s = (Q.to_qpi(a) - Q.to_qpi(b)).sign()
        except Q.QPiError as e:
            raise Unsupported(str(e)) from None
        return {"=": s == 0, "!=": s != 0, "<": s < 0, "<=": s <= 0, ">": s > 0, ">=": s >= 0}[op]
    if isinstance(a, Num | Surd) and isinstance(b, _Angle | _Root):
        flip = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
        return compare(flip.get(op, op), b, a)
    if isinstance(a, _Root):               # both sides >= 0: compare the squares
        try:
            if isinstance(b, _Root):
                return compare(op, a.sq, b.sq)
            c = _surd(b)
            if c.sign() < 0:
                return op in ("!=", ">", ">=")
            return compare(op, a.sq, c * c)
        except SurdError as e:
            raise Unsupported(str(e)) from None
    if isinstance(a, Surd) or isinstance(b, Surd):
        try:
            s = (_surd(a) - _surd(b)).sign()
        except SurdError as e:
            raise Unsupported(str(e)) from None
        return {"=": s == 0, "!=": s != 0, "<": s < 0, "<=": s <= 0,
                ">": s > 0, ">=": s >= 0}[op]
    if isinstance(a, _Angle):
        if op not in ("=", "!=") or not isinstance(b, Num) or b.dims != DEG \
                or b.value not in COS2:
            raise Unsupported("angles compare by = or != with 0, 30, 45, 60, 90, 120, 135, "
                              "150 or 180 deg")
        sign, c2 = COS2[int(b.value)]
        try:
            eq = a.norms.sign() > 0 and a.dot.sign() == sign \
                and (a.dot * a.dot - Surd.of(c2) * a.norms).sign() == 0
        except SurdError as e:
            raise Unsupported(str(e)) from None
        return eq if op == "=" else not eq
    if isinstance(a, Num) and isinstance(b, Num):
        if a.dims != b.dims:
            raise Unsupported("dimension mismatch")
        return _ordered(op, a.value, b.value)
    if op in ("=", "!="):
        return (a == b) == (op == "=")
    raise Unsupported("ordering on a non-number")


def holds(formula: Term, props: Mapping[str, Term]) -> bool:
    """Decide a ground formula for an instance with the given property values."""
    return _Eval(props).holds(formula)


def failing(cls: ClassDef, props: Mapping[str, Term]) -> tuple[str, ...]:
    """The invariants of ``cls`` the instance violates (empty: it is a member)."""
    if set(props) != set(cls.props):
        raise Unsupported(f"{cls.name} needs properties {', '.join(cls.props)}")
    return tuple(n for n, f in cls.invariants if not holds(f, props))
