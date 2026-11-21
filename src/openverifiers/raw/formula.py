"""Object-layer formulas: concept-class definitions and their exact ground evaluator.

A ``fact type`` lowers to a :class:`ClassDef`: property names, the named
invariants (own and inherited) and the named theorems. Every formula is an
ordinary RawOV term, so it prints and parses with ``raw.text``.

Formula terms::

    f.and(F, ...)   f.or(F, ...)   f.not(F)   f.cmp("op", E, E)
    f.exists("v", C, F)   f.forall("v", C, F)   f.forall_idx("i", C, F)

Expression terms::

    numbers, f.v("name") (bound variable), f.p("name") (property),
    f.tuple(E..), f.set(E..), f.list(E..), f.idx(C, E) (index mod length),
    f.at(E, k) (tuple component), + - * / ^ abs min max, f.count(C),
    f.dist(P, P), f.dist2(P, P) (squared), f.angle(P, P, P), f.cycles(C), f.orderings(C),
    f.subsets(C, k), f.pairs(C),
    f.integral(E, "t") (the integral of E from 0 to property t's value, in t),
    f.deriv(E, "t") (dE/dt at t's value); E must be a polynomial in t

The evaluator here re-checks every instance any solver proposes. It is exact:
``dist`` values are kept as square roots of rationals and compared by
squaring, and ``angle(a, b, c) = θ deg`` is decided on the dot product for
the angles whose cosine squared is rational. Generators enumerate *every*
ordering: symmetry pruning is the solver's business, never the checker's.
Anything outside this fragment raises :class:`Unsupported`.

Trusted code.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, permutations

from .builtins import ARITH, apply_op
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
    """The non-negative square root of ``sq``."""

    sq: Fraction


@dataclass(frozen=True, slots=True)
class _Angle:
    dot: Fraction
    norms: Fraction          # |u|^2 * |w|^2


Value = Term | _Root | _Angle


def make_set(items: list[Term]) -> Compound:
    uniq: dict[Term, None] = dict.fromkeys(items)
    return Compound("f.set", tuple(sorted(uniq, key=order_key)))


def _seq(v: Value) -> tuple[Term, ...]:
    if isinstance(v, Compound) and v.functor in ("f.set", "f.list", "f.tuple"):
        return v.args
    raise Unsupported(f"not a collection: {v}")


def _point(v: Value) -> tuple[Fraction, ...]:
    if isinstance(v, Compound) and v.functor == "f.tuple" and all(
            isinstance(a, Num) and not a.dims for a in v.args):
        return tuple(a.value for a in v.args if isinstance(a, Num))
    raise Unsupported(f"not a point: {v}")


def _sub(a: tuple[Fraction, ...], b: tuple[Fraction, ...]) -> tuple[Fraction, ...]:
    if len(a) != len(b):
        raise Unsupported("points of different dimension")
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _dot(a: tuple[Fraction, ...], b: tuple[Fraction, ...]) -> Fraction:
    return sum((x * y for x, y in zip(a, b, strict=True)), Fraction(0))


def _degree(t: Term, var: str) -> int:
    """An upper bound on t's degree as a polynomial in property ``var``; Unsupported if
    t is not polynomial in it."""
    if not isinstance(t, Compound):
        return 0
    f, a = t.functor, t.args
    if f == "f.p":
        return 1 if a[0] == Str(var) else 0
    if f in ("f.v", "f.tuple", "f.list", "f.set") or not _mentions(t, var):
        return 0
    ds = [_degree(x, var) for x in a if not isinstance(x, Str)]
    if f in ("+", "-"):
        return max(ds)
    if f == "*":
        return sum(ds)
    if f == "/" and ds[1] == 0:
        return ds[0]
    if f == "^" and isinstance(a[1], Num) and a[1].value.denominator == 1 and a[1].value >= 0:
        return ds[0] * int(a[1].value)
    if f in ("f.integral", "f.deriv"):
        own = a[1] == Str(var)
        return ds[0] + 1 if own and f == "f.integral" else max(ds[0] - 1, 0) if own else ds[0]
    raise Unsupported(f"{f} is not polynomial in {var}")


def _mentions(t: Term, var: str) -> bool:
    if isinstance(t, Compound):        # integral(e, t) and deriv(e, t) depend on t's value
        return (t.functor in ("f.p", "f.integral", "f.deriv") and Str(var) in t.args) or any(
            _mentions(x, var) for x in t.args)
    return False


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
    def __init__(self, props: Mapping[str, Term]) -> None:
        self.props = props
        self.env: dict[str, Term] = {}

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
            return table[key] if f == "f.v" else self.expr(table[key])
        if f in ("f.integral", "f.deriv"):
            return self._calculus(f, a)
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
            return seq[int(k.value)]
        if f == "f.idx":
            seq, i = _seq(vals[0]), vals[1]
            if not seq or not isinstance(i, Num) or i.value.denominator != 1:
                raise Unsupported("bad index")
            return seq[int(i.value) % len(seq)]
        if f == "f.count":
            return Num(Fraction(len(_seq(vals[0]))))
        if f == "f.dist":
            d = _sub(_point(vals[0]), _point(vals[1]))
            return _Root(_dot(d, d))
        if f == "f.dist2":
            d = _sub(_point(vals[0]), _point(vals[1]))
            return Num(_dot(d, d))
        if f == "f.angle":
            u = _sub(_point(vals[0]), _point(vals[1]))
            w = _sub(_point(vals[2]), _point(vals[1]))
            return _Angle(_dot(u, w), _dot(u, u) * _dot(w, w))
        if f in ARITH and all(isinstance(v, Num) for v in vals):
            r = apply_op(f, [v for v in vals if isinstance(v, Num)])
            if r is None:
                raise Unsupported(f"arithmetic failed: {t}")
            return r
        raise Unsupported(f"cannot evaluate {f}")

    def _calculus(self, f: str, a: tuple[Term, ...]) -> Num:
        """Exact: sample the polynomial at 0..degree, recover its coefficients, then
        integrate from 0 (or differentiate) and evaluate at the property's value."""
        var = a[1].value if isinstance(a[1], Str) else ""
        x = self.expr(Compound("f.p", (Str(var),)))
        ys = []
        for i in range(_degree(a[0], var) + 1):
            e = _Eval({**self.props, var: Num(Fraction(i))})
            e.env = self.env
            y = e.expr(a[0])
            if not isinstance(y, Num) or y.dims:
                raise Unsupported("integral or derivative of a non-number")
            ys.append(y.value)
        if not isinstance(x, Num) or x.dims:
            raise Unsupported(f"{var} is not a number")
        c = _coefficients(ys)
        if f == "f.integral":
            return Num(sum((c[k] * x.value ** (k + 1) / (k + 1) for k in range(len(c))),
                           Fraction(0)))
        return Num(sum((k * c[k] * x.value ** (k - 1) for k in range(1, len(c))), Fraction(0)))

    @staticmethod
    def _term(v: Value) -> Term:
        if isinstance(v, _Root | _Angle):
            raise Unsupported("a distance or angle cannot be stored in a collection")
        return v

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


def compare(op: str, a: Value, b: Value) -> bool:
    if op not in ("=", "!=", "<", "<=", ">", ">="):
        raise Unsupported(f"unknown comparison {op}")
    if isinstance(a, Num) and isinstance(b, _Root | _Angle):
        flip = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
        return compare(flip.get(op, op), b, a)
    if isinstance(a, _Root):
        if isinstance(b, _Root):
            return _ordered(op, a.sq, b.sq)
        if isinstance(b, Num) and not b.dims:
            if b.value < 0:
                return op in ("!=", ">", ">=")
            return _ordered(op, a.sq, b.value * b.value)
        raise Unsupported("a distance compared with a non-constant")
    if isinstance(a, _Angle):
        if op not in ("=", "!=") or not isinstance(b, Num) or b.dims != DEG \
                or b.value not in COS2:
            raise Unsupported("angles compare by = or != with 0, 30, 45, 60, 90, 120, 135, "
                              "150 or 180 deg")
        sign, c2 = COS2[int(b.value)]
        s = (a.dot > 0) - (a.dot < 0)
        eq = a.norms > 0 and s == sign and a.dot * a.dot == c2 * a.norms
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
