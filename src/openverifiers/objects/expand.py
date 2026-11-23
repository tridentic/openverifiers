"""Expand a RawOV class formula with unknowns into polynomial constraints.

Untrusted: this is the solver's view of a formula. It mirrors the exact
evaluator in ``raw.formula`` (squared distances, angles via the dot product),
but over polynomials in the unknown coordinates, so z3 can search for models.
Whatever it gets wrong, the evaluator catches when it re-checks the model.

Symmetry: a generator expands to one disjunct per ordering, and disjuncts are
kept in canonical form, so orderings that give the same constraints (the
rotations and reflections of a cycle under a rotation-invariant body) merge
into one. ``symmetry=False`` keeps every ordering, for the ablation test.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, permutations
from math import isqrt

from ..raw.formula import COS2, DEG, Unsupported, subst
from ..raw.terms import Compound, Dims, Num, Str, Term, Var

Mono = tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Poly:
    terms: tuple[tuple[Mono, Fraction], ...]     # sorted, no zero coefficients

    @staticmethod
    def make(d: Mapping[Mono, Fraction]) -> Poly:
        return Poly(tuple(sorted((m, c) for m, c in d.items() if c != 0)))

    @staticmethod
    def const(c: Fraction) -> Poly:
        return Poly.make({(): c})

    @staticmethod
    def var(n: str) -> Poly:
        return Poly.make({((n, 1),): Fraction(1)})

    def constant(self) -> Fraction | None:
        if not self.terms:
            return Fraction(0)
        if len(self.terms) == 1 and self.terms[0][0] == ():
            return self.terms[0][1]
        return None

    def __add__(self, o: Poly) -> Poly:
        d = dict(self.terms)
        for m, c in o.terms:
            d[m] = d.get(m, Fraction(0)) + c
        return Poly.make(d)

    def scale(self, k: Fraction) -> Poly:
        return Poly.make({m: c * k for m, c in self.terms})

    def __sub__(self, o: Poly) -> Poly:
        return self + o.scale(Fraction(-1))

    def __mul__(self, o: Poly) -> Poly:
        d: dict[Mono, Fraction] = {}
        for m1, c1 in self.terms:
            for m2, c2 in o.terms:
                e = dict(m1)
                for v, k in m2:
                    e[v] = e.get(v, 0) + k
                m = tuple(sorted(e.items()))
                d[m] = d.get(m, Fraction(0)) + c1 * c2
        return Poly.make(d)


def poly_deriv(p: Poly, v: str) -> Poly:
    d: dict[Mono, Fraction] = {}
    for m, c in p.terms:
        e = dict(m)
        k = e.pop(v, 0)
        if k:
            if k > 1:
                e[v] = k - 1
            mono = tuple(sorted(e.items()))
            d[mono] = d.get(mono, Fraction(0)) + c * k
    return Poly.make(d)


def poly_integral(p: Poly, v: str) -> Poly:
    """The antiderivative in v with no constant term (so its value at v = 0 is 0)."""
    d: dict[Mono, Fraction] = {}
    for m, c in p.terms:
        e = dict(m)
        k = e.get(v, 0) + 1
        e[v] = k
        mono = tuple(sorted(e.items()))
        d[mono] = d.get(mono, Fraction(0)) + c / k
    return Poly.make(d)


def poly_subst(p: Poly, v: str, q: Poly) -> Poly:
    out = Poly.const(Fraction(0))
    for m, c in p.terms:
        e = dict(m)
        k = e.pop(v, 0)
        term = Poly.make({tuple(sorted(e.items())): c})
        for _ in range(k):
            term = term * q
        out = out + term
    return out


# ---------------------------------------------------------------- constraint formulas
# ("true",) ("false",) ("atom", op, poly) with op in = != > >= meaning poly op 0,
# ("and", parts) ("or", parts); parts are frozensets (merged) or tuples (kept).

CF = tuple[object, ...]
TRUE: CF = ("true",)
FALSE: CF = ("false",)


def atom(op: str, p: Poly) -> CF:
    if op in ("int", "nint"):                    # p is (not) an integer (D-027)
        c = p.constant()
        if c is not None:
            return TRUE if (c.denominator == 1) == (op == "int") else FALSE
        return ("atom", op, p)
    if op in ("<", "<="):
        op, p = (">" if op == "<" else ">="), p.scale(Fraction(-1))
    c = p.constant()
    if c is not None:
        return TRUE if {"=": c == 0, "!=": c != 0, ">": c > 0, ">=": c >= 0}[op] else FALSE
    lead = p.terms[-1][1]
    p = p.scale(1 / (lead if op in ("=", "!=") else abs(lead)))
    return ("atom", op, p)


def and_(parts: Iterable[CF], keep: bool = False) -> CF:
    out: list[CF] = []
    for x in parts:
        if x == FALSE:
            return FALSE
        if x == TRUE:
            continue
        out.extend(x[1] if x[0] == "and" else (x,))  # type: ignore[arg-type]
    if not out:
        return TRUE
    return out[0] if len(out) == 1 else ("and", tuple(out) if keep else frozenset(out))


def or_(parts: Iterable[CF], keep: bool = False) -> CF:
    out: list[CF] = []
    for x in parts:
        if x == TRUE:
            return TRUE
        if x == FALSE:
            continue
        out.extend(x[1] if x[0] == "or" else (x,))  # type: ignore[arg-type]
    if not out:
        return FALSE
    if not keep:
        out = list(dict.fromkeys(out))
    return out[0] if len(out) == 1 else ("or", tuple(out) if keep else frozenset(out))


_FLIP = {"=": "!=", "!=": "=", ">": ">=", ">=": ">", "int": "nint", "nint": "int"}


def not_(f: CF) -> CF:
    if f == TRUE:
        return FALSE
    if f == FALSE:
        return TRUE
    if f[0] == "atom":
        op, p = f[1], f[2]
        assert isinstance(op, str) and isinstance(p, Poly)
        return atom(_FLIP[op], p if op in ("=", "!=", "int", "nint") else p.scale(Fraction(-1)))
    parts = f[1]
    assert isinstance(parts, (frozenset, tuple))
    return (or_ if f[0] == "and" else and_)(not_(x) for x in parts)


# ---------------------------------------------------------------- symbolic values


@dataclass(frozen=True)
class SNum:
    p: Poly
    dims: Dims = ()


@dataclass(frozen=True)
class SSeq:
    kind: str                    # tuple | set | list
    items: tuple[SVal, ...]


@dataclass(frozen=True)
class SRoot:
    sq: Poly


@dataclass(frozen=True)
class SAngle:
    dot: Poly
    nu: Poly        # |u|^2
    nw: Poly        # |w|^2


SVal = SNum | SSeq | SRoot | SAngle


#: Square roots used in arithmetic: variable name -> its radicand. A root r of X is
#: the unique d with d^2 = X and d >= 0, so the solver may add that definition
#: globally (even when the root sits under a negation): see ``root_definitions``.
ROOTS: dict[str, Poly] = {}
#: exp(u) used in a formula: variable name -> u. Defined by e > 0 (and e = 1 when
#: u = 0); otherwise an opaque positive number, so a proof that holds for every
#: positive value holds for the true one.
EXPS: dict[str, Poly] = {}
#: ln(u): variable name -> u, defined by exp(L) = u with u > 0.
LOGS: dict[str, Poly] = {}
#: 1/D for a non-constant D: variable name -> D, defined by R D = 1. That is the
#: formula multiplied through by D, with the side condition D != 0 recorded (an
#: instance with D = 0 makes the formula undefined, so it is no member).
RECIPS: dict[str, Poly] = {}
#: mod(a, b) for a constant integer b > 0: variable name (the remainder r) ->
#: (a, b), defined by r = a - b q with q an integer and 0 <= r < b.
MODS: dict[str, tuple[Poly, int]] = {}


def mod_var(a: Poly, b: int) -> SNum:
    name = _atom_name("MOD", a.scale(Fraction(1, b)))
    MODS[name] = (a, b)
    return SNum(Poly.var(name))


def recip_var(d: Poly) -> SNum:
    name = _atom_name("RECIP", d)
    RECIPS[name] = d
    return SNum(Poly.var(name))


def _atom_name(kind: str, x: Poly) -> str:
    return f"{kind}_" + hashlib.sha1(repr(x.terms).encode()).hexdigest()[:12]


def exp_var(x: Poly) -> SNum:
    if x.constant() == 0:
        return SNum(Poly.const(Fraction(1)))
    name = _atom_name("EXP", x)
    EXPS[name] = x
    return SNum(Poly.var(name))


def log_var(x: Poly) -> SNum:
    if x.constant() == 1:
        return SNum(Poly.const(Fraction(0)))
    name = _atom_name("LN", x)
    LOGS[name] = x
    exp_var(Poly.var(name))                      # exp(ln u) = u, defined below
    return SNum(Poly.var(name))


def _depends(v: str, tau: str, seen: frozenset[str] = frozenset()) -> bool:
    """Whether the solver variable v (possibly an atom) depends on tau."""
    if v == tau:
        return True
    arg = ROOTS.get(v) or EXPS.get(v) or LOGS.get(v) or RECIPS.get(v) or \
        (MODS[v][0] if v in MODS else None)
    if arg is None or v in seen:
        return False
    return any(_depends(w, tau, seen | {v}) for m, _ in arg.terms for w, _ in m)


def calculus(p: Poly, tau: str, integral: bool) -> Poly:
    """The integral (from 0) or derivative in tau of p, where p may contain atoms.
    Atoms that depend on tau: refused for integrals; for derivatives, exp(u) follows
    the chain rule (d exp(u) = exp(u) u'), and any other is refused. Treating such an
    atom as a constant would be unsound."""
    atoms = {v for m, _ in p.terms for v, _ in m if v != tau and _depends(v, tau)}
    if not atoms:
        return poly_integral(p, tau) if integral else poly_deriv(p, tau)
    if integral or any(a not in EXPS for a in atoms):
        raise Unsupported("calculus of a non-polynomial in the variable (sqrt, ln, exp)")
    out = poly_deriv(p, tau)                     # the polynomial part
    for a in atoms:                              # + d p / d a * exp(u) * u'
        out = out + poly_deriv(p, a) * Poly.var(a) * calculus(EXPS[a], tau, False)
    return out


def subst_atoms(p: Poly, tau: str, val: Poly) -> Poly:
    """p with tau replaced by val, inside atoms too: exp(u(tau)) becomes exp(u(val))."""
    out = p
    for v in sorted({w for m, _ in p.terms for w, _ in m}):
        if v == tau or not _depends(v, tau):
            continue
        if v in EXPS:
            new = exp_var(subst_atoms(EXPS[v], tau, val)).p
        elif v in ROOTS:
            new = root_var(subst_atoms(ROOTS[v], tau, val)).p
        elif v in LOGS:
            new = log_var(subst_atoms(LOGS[v], tau, val)).p
        elif v in RECIPS:
            new = recip_var(subst_atoms(RECIPS[v], tau, val)).p
        elif v in MODS:
            new = mod_var(subst_atoms(MODS[v][0], tau, val), MODS[v][1]).p
        else:
            continue
        out = poly_subst(out, v, new)
    return poly_subst(out, tau, val)


def root_var(x: Poly) -> SNum:
    """sqrt(x) as a solver variable, defined by ROOTS."""
    c = x.constant()
    if c is not None and c >= 0:
        n, d = isqrt(c.numerator), isqrt(c.denominator)
        if n * n == c.numerator and d * d == c.denominator:
            return SNum(Poly.const(Fraction(n, d)))
    name = "ROOT_" + hashlib.sha1(repr(x.terms).encode()).hexdigest()[:12]
    ROOTS[name] = x
    return SNum(Poly.var(name))


def root_definitions(names: Iterable[str]) -> list[CF]:
    """The defining constraints of the atoms among ``names`` (and of atoms those
    mention): d^2 = X, d >= 0 for roots; e > 0 for exp; exp(L) = u, u > 0 for ln;
    R D = 1 for 1/D."""
    out: list[CF] = []
    todo, done = list(names), set()
    while todo:
        n = todo.pop()
        if n in done:
            continue
        done.add(n)
        v = Poly.var(n)
        if n == "PI":                     # pi in [3.14159265358979, 3.14159265358980]
            out += [atom(">", v - Poly.const(Fraction(314159265358979, 10**14))),
                    atom("<", v - Poly.const(Fraction(314159265358980, 10**14)))]
        elif n in ROOTS:
            out += [atom("=", v * v - ROOTS[n]), atom(">=", v)]
            todo += [w for m, _ in ROOTS[n].terms for w, _ in m]
        elif n in EXPS:
            out.append(atom(">", v))
            todo += [w for m, _ in EXPS[n].terms for w, _ in m]
        elif n in MODS:
            a, b = MODS[n]
            q = Poly.var(n + "_Q")
            out += [atom("int", q), atom("=", v - a + q.scale(Fraction(b))), atom(">=", v),
                    atom(">", Poly.const(Fraction(b)) - v)]
            todo += [w for m, _ in a.terms for w, _ in m]
        elif n in RECIPS:
            out.append(atom("=", v * RECIPS[n] - Poly.const(Fraction(1))))
            todo += [w for m, _ in RECIPS[n].terms for w, _ in m]
        elif n in LOGS:
            e = _atom_name("EXP", v)
            out += [atom("=", Poly.var(e) - LOGS[n]), atom(">", LOGS[n])]
            todo += [e, *(w for m, _ in LOGS[n].terms for w, _ in m)]
    return out


def _num(v: SVal) -> SNum:
    if isinstance(v, SRoot):               # a distance used in arithmetic
        return root_var(v.sq)
    if not isinstance(v, SNum):
        raise Unsupported(f"expected a number, got {type(v).__name__}")
    return v


def _seq(v: SVal) -> tuple[SVal, ...]:
    if not isinstance(v, SSeq):
        raise Unsupported("expected a collection")
    return v.items


def _point(v: SVal) -> tuple[Poly, ...]:
    if not isinstance(v, SSeq) or v.kind != "tuple":
        raise Unsupported("expected a point")
    return tuple(_num(x).p for x in v.items)


def _int(v: SVal) -> int:
    c = _num(v).p.constant()
    if c is None or c.denominator != 1:
        raise Unsupported("an index must be a known integer")
    return int(c)


def _dot(a: tuple[Poly, ...], b: tuple[Poly, ...]) -> Poly:
    out = Poly.const(Fraction(0))
    for x, y in zip(a, b, strict=True):
        out = out + x * y
    return out


def _diff(a: tuple[Poly, ...], b: tuple[Poly, ...]) -> tuple[Poly, ...]:
    if len(a) != len(b):
        raise Unsupported("points of different dimension")
    return tuple(x - y for x, y in zip(a, b, strict=True))


def equal(a: SVal, b: SVal) -> CF:
    if isinstance(a, SNum) and isinstance(b, SNum):
        if a.dims != b.dims:
            raise Unsupported("dimension mismatch")
        return atom("=", a.p - b.p)
    if isinstance(a, SSeq) and isinstance(b, SSeq) and a.kind == b.kind == "tuple":
        if len(a.items) != len(b.items):
            return FALSE
        return and_(equal(x, y) for x, y in zip(a.items, b.items, strict=True))
    raise Unsupported("equality of collections with unknowns")


class Expander:
    def __init__(self, props: Mapping[str, Term], symmetry: bool = True) -> None:
        self.props, self.symmetry = props, symmetry
        self.env: dict[str, SVal] = {}
        self.fresh_tau = 0

    def value(self, t: Term) -> SVal:
        if isinstance(t, Num):
            return SNum(Poly.const(t.value), t.dims)
        if isinstance(t, Var):
            return SNum(Poly.var(t.name))
        if not isinstance(t, Compound):
            raise Unsupported(f"unexpected term {t}")
        f, a = t.functor, t.args
        if f in ("f.v", "f.p"):
            key = a[0].value if isinstance(a[0], Str) else ""
            if f == "f.v":
                return self.env[key]
            return self.value(self.props[key])
        if f in ("f.tuple", "f.list", "f.set"):
            items = [self.value(x) for x in a]
            if f == "f.set":
                items = list(dict.fromkeys(items))   # syntactic duplicates only; see cases()
            return SSeq(f[2:], tuple(items))
        if f == "f.at":
            k = a[1]
            seq = _seq(self.value(a[0]))
            assert isinstance(k, Num)
            return seq[int(k.value)]
        if f == "f.surd":                  # c1 sqrt(k1) + ...: each root a defined variable
            nums = [x.value for x in a if isinstance(x, Num)]
            out = Poly.const(Fraction(0))
            for rad, coef in zip(nums[0::2], nums[1::2], strict=True):
                out = out + root_var(Poly.const(rad)).p.scale(coef)
            return SNum(out)
        if f in ("f.integral", "f.deriv"):
            self.fresh_tau += 1
            tau = f"TAU_{self.fresh_tau}"
            body = _num(self.value(subst(a[0], a[1], Var(tau))))
            q = calculus(body.p, tau, f == "f.integral")
            return SNum(subst_atoms(q, tau, _num(self.value(a[2])).p))
        vals = [self.value(x) for x in a]
        if f == "f.idx":
            seq = _seq(vals[0])
            if not seq:
                raise Unsupported("index into an empty list")
            return seq[_int(vals[1]) % len(seq)]
        if f == "f.count":
            return SNum(Poly.const(Fraction(len(_seq(vals[0])))))
        if f == "f.dist":
            d = _diff(_point(vals[0]), _point(vals[1]))
            return SRoot(_dot(d, d))
        if f == "f.sqrt":
            x = _num(vals[0])
            return root_var(x.p)
        if f == "f.pi":
            return SNum(Poly.var("PI"))
        if f == "f.mod":
            b = _num(vals[1]).p.constant()
            if b is None or b <= 0 or b.denominator != 1:
                raise Unsupported("mod by something other than a positive integer constant")
            return mod_var(_num(vals[0]).p, int(b))
        if f == "f.exp":
            return exp_var(_num(vals[0]).p)
        if f == "f.ln":
            return log_var(_num(vals[0]).p)
        if f == "f.dist2":
            d = _diff(_point(vals[0]), _point(vals[1]))
            return SNum(_dot(d, d))
        if f == "f.angle":
            u = _diff(_point(vals[0]), _point(vals[1]))
            w = _diff(_point(vals[2]), _point(vals[1]))
            return SAngle(_dot(u, w), _dot(u, u), _dot(w, w))
        return self.arith(f, [_num(v) for v in vals])

    @staticmethod
    def arith(f: str, xs: list[SNum]) -> SNum:
        if f == "-" and len(xs) == 1:
            return SNum(xs[0].p.scale(Fraction(-1)), xs[0].dims)
        if len(xs) != 2:
            raise Unsupported(f"cannot expand {f}")
        x, y = xs
        if f in ("+", "-"):
            if x.dims != y.dims:
                raise Unsupported("dimension mismatch")
            return SNum(x.p + y.p if f == "+" else x.p - y.p, x.dims)
        if f == "*" and not x.dims and not y.dims:
            return SNum(x.p * y.p)
        if f == "/" and not y.dims and (c := y.p.constant()) not in (None, 0):
            assert c is not None
            return SNum(x.p.scale(1 / c), x.dims)
        if f == "/" and not y.dims and not x.dims and y.p.constant() is None:
            return SNum(x.p * recip_var(y.p).p)      # multiplied through; D != 0 recorded
        if f == "^" and not x.dims and (k := y.p.constant()) is not None \
                and k.denominator == 1 and k >= 0:
            out = Poly.const(Fraction(1))
            for _ in range(int(k)):
                out = out * x.p
            return SNum(out)
        raise Unsupported(f"cannot expand {f} on these operands")

    def items(self, t: Term) -> list[SVal]:
        if isinstance(t, Compound) and t.functor in ("f.cycles", "f.orderings", "f.pairs",
                                                     "f.subsets"):
            src = _seq(self.value(t.args[0]))
            if t.functor in ("f.cycles", "f.orderings"):
                return [SSeq("list", p) for p in permutations(src)]
            if t.functor == "f.pairs":
                return [SSeq("tuple", c) for c in combinations(src, 2)]
            return [SSeq("set", c) for c in combinations(src, _int(self.value(t.args[1])))]
        return list(_seq(self.value(t)))

    def formula(self, t: Term) -> CF:
        if not isinstance(t, Compound):
            raise Unsupported(f"not a formula: {t}")
        f, a = t.functor, t.args
        if f == "f.and":
            out = []
            for x in a:
                c = self.formula(x)
                if c == FALSE:
                    return FALSE
                out.append(c)
            return and_(out)
        if f == "f.or":
            return or_(self.formula(x) for x in a)
        if f == "f.not":
            return not_(self.formula(a[0]))
        if f == "f.cmp" and isinstance(a[0], Str):
            return compare(a[0].value, self.value(a[1]), self.value(a[2]))
        if f == "f.isint":
            return atom("int", _num(self.value(a[0])).p)
        if f in ("f.exists", "f.forall", "f.forall_idx") and isinstance(a[0], Str):
            var = a[0].value
            if f == "f.forall_idx":
                elems: list[SVal] = [SNum(Poly.const(Fraction(i)))
                                     for i in range(len(_seq(self.value(a[1]))))]
            else:
                elems = self.items(a[1])
            parts = []
            for el in elems:
                self.env[var] = el
                parts.append(self.formula(a[2]))
            self.env.pop(var, None)
            if f == "f.exists":
                return or_(parts, keep=not self.symmetry)
            return and_(parts)
        raise Unsupported(f"unknown formula {f}")


def compare(op: str, a: SVal, b: SVal) -> CF:
    if isinstance(a, SNum) and isinstance(b, SRoot | SAngle):
        flip = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
        return compare(flip.get(op, op), b, a)
    if isinstance(a, SRoot):
        if isinstance(b, SRoot):
            return atom(op, a.sq - b.sq)
        if isinstance(b, SNum) and not b.dims:
            # sqrt(sq) op e, exactly: square both sides where e >= 0 decides the sign.
            e, d = b.p, a.sq - b.p * b.p
            if op in ("=", "!="):
                eq = and_([atom(">=", e), atom("=", d)])
                return eq if op == "=" else not_(eq)
            if op in (">", ">="):
                return or_([atom("<", e), atom(op, d)])
            return and_([atom(">" if op == "<" else ">=", e), atom(op, d)])
        raise Unsupported("a distance compared with a dimensioned value")
    if isinstance(a, SAngle):
        c = b.p.constant() if isinstance(b, SNum) and b.dims == DEG else None
        if op not in ("=", "!=") or c is None or c not in COS2:
            raise Unsupported("unsupported angle comparison")
        sign, c2 = COS2[int(c)]
        # Both arms non-zero, the right sign of cos, and cos^2 exact. For 90 deg the
        # dot product is simply zero (kept at degree 2: nonlinear search is much faster).
        parts = [atom(">", a.nu), atom(">", a.nw),
                 atom("=" if sign == 0 else ">", a.dot.scale(Fraction(sign or 1)))]
        if sign != 0:
            parts.append(atom("=", a.dot * a.dot - (a.nu * a.nw).scale(c2)))
        eq = and_(parts)
        return eq if op == "=" else not_(eq)
    if isinstance(a, SNum) and isinstance(b, SNum):
        if a.dims != b.dims:
            raise Unsupported("dimension mismatch")
        return atom(op, a.p - b.p)
    if op in ("=", "!="):
        same = equal(a, b)
        return same if op == "=" else not_(same)
    raise Unsupported("ordering on a non-number")


# ---------------------------------------------------------------- set cases


def _partitions(items: list[int], ground: set[int]) -> Iterable[list[list[int]]]:
    """Set partitions of ``items`` in which no block holds two ground elements."""
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for part in _partitions(rest, ground):
        for i, block in enumerate(part):
            if first in ground and any(x in ground for x in block):
                continue
            yield [*part[:i], [first, *block], *part[i + 1:]]
        yield [[first], *part]


def _has_var(t: Term) -> bool:
    if isinstance(t, Var):
        return True
    return isinstance(t, Compound) and any(_has_var(a) for a in t.args)


def cases(props: Mapping[str, Term], symmetry: bool = True) -> list[tuple[dict[str, Term], CF]]:
    """Split on which unknown elements of each set coincide.

    ``{(3,1), ?p}`` has one element if ``?p = (3,1)`` and two otherwise. Each
    case fixes that choice (as equalities and disequalities between elements)
    and gives the sets the case's distinct elements, so ``count`` and the
    generators see the true set.
    """
    out: list[tuple[dict[str, Term], CF]] = [(dict(props), TRUE)]
    for name, val in props.items():
        if not (isinstance(val, Compound) and val.functor == "f.set" and _has_var(val)):
            continue
        items = list(dict.fromkeys(val.args))
        ground = {i for i, x in enumerate(items) if not _has_var(x)}
        ex = Expander({})
        vals = [ex.value(x) for x in items]
        nxt = []
        for part in _partitions(list(range(len(items))), ground):
            reps = []
            conds: list[CF] = []
            for block in part:
                rep = next((i for i in block if i in ground), block[0])
                reps.append(rep)
                conds += [equal(vals[i], vals[rep]) for i in block if i != rep]
            for x, y in combinations(reps, 2):
                if not (x in ground and y in ground):
                    conds.append(not_(equal(vals[x], vals[y])))
            cond = and_(conds)
            if cond == FALSE:
                continue
            for p, c in out:
                q = dict(p)
                q[name] = Compound("f.set", tuple(items[i] for i in sorted(reps)))
                nxt.append((q, and_([c, cond])))
        out = nxt
    return out


def expand(formula: Term, props: Mapping[str, Term], symmetry: bool = True) -> CF:
    """The formula as constraints on the unknowns, over every set case."""
    return or_(and_([cond, Expander(p, symmetry).formula(formula)])
               for p, cond in cases(props, symmetry))


def seq_items(v: SVal) -> tuple[SVal, ...]:
    """The elements of a symbolic collection."""
    return _seq(v)


def _atoms(f: CF, out: list[Poly]) -> list[Poly]:
    if f[0] == "atom":
        p = f[2]
        assert isinstance(p, Poly)
        out.append(p)
    elif f[0] in ("and", "or"):
        parts = f[1]
        assert isinstance(parts, (frozenset, tuple))
        for x in parts:
            _atoms(x, out)
    return out


def _shifted(p: Poly, group: set[str]) -> Poly:
    """p with every variable v in group replaced by v + T (T a fresh symbol)."""
    t = Poly.var("__shift__")
    out = Poly.const(Fraction(0))
    for mono, c in p.terms:
        term = Poly.const(c)
        for v, k in mono:
            base = Poly.var(v) + t if v in group else Poly.var(v)
            for _ in range(k):
                term = term * base
        out = out + term
    return out


def translation_invariant(fs: Iterable[CF], group: set[str]) -> bool:
    """Every constraint is unchanged when all variables in group move by the same amount.

    Then any model can be shifted so that one of them is 0: fixing it loses no model."""
    return all(_shifted(p, group) == p for f in fs for p in _atoms(f, []))
