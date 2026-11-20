"""Compile concept classes (``fact type``) and object queries to RawOV formulas.

Untrusted, like all lowering: the output is RawOV (``raw.formula``), and the
trusted evaluator there decides every instance. This module only has to be
*syntactic*: it resolves names, linearises inheritance (a shared ancestor's
invariants once), types collections enough to resolve record fields, and
rejects, with a span, anything the exact evaluator could not decide.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING

from ..lang import ast as A
from ..lang.errors import Diagnostic
from ..lang.units import QUANTITY_TYPES
from ..raw.formula import COS2, DEG, ClassDef, Unsupported
from ..raw.program import Span
from ..raw.terms import Compound, Num, Str, Term, Var

if TYPE_CHECKING:
    from ..lang.check import Env

#: (name, args) types: ("Real",), ("Set", T), ("List", T), ("Point",) ...
Ty = tuple[object, ...]
REAL: Ty = ("Real",)
GENERATORS = {"cycles": 1, "orderings": 1, "pairs": 1, "subsets": 2}
FUNCS = {"count": 1, "dist": 2, "dist2": 2, "angle": 3, "abs": 1, "min": 2, "max": 2}


class _Fail(Exception):
    def __init__(self, code: str, msg: str, span: Span, hint: str = "") -> None:
        self.d = Diagnostic(code, msg, span, hint)


def _f(name: str, *args: Term) -> Compound:
    return Compound(f"f.{name}", args)


def conj(fs: Sequence[Term]) -> Term:
    return fs[0] if len(fs) == 1 else _f("and", *fs)


@dataclass
class Classes:
    """Everything the object layer knows after checking."""

    defs: dict[str, ClassDef] = field(default_factory=dict)
    prop_types: dict[str, dict[str, Ty]] = field(default_factory=dict)
    spans: dict[str, Span] = field(default_factory=dict)        # class / qualified member
    records: dict[str, tuple[str, ...]] = field(default_factory=dict)
    plans: dict[Span, ObjPlan] = field(default_factory=dict)
    ancestors: dict[str, tuple[str, ...]] = field(default_factory=dict)   # without the class


def records(env: Env) -> dict[str, tuple[str, ...]]:
    """Record types: entity types whose fields are all quantities (``Point``)."""
    out = {}
    for t in env.types.values():
        if t.fields and all(ft in QUANTITY_TYPES for ft, _ in t.fields.values()):
            out[t.name] = tuple(t.fields)
    return out


def ty_of(e: A.TyExpr, cls: Classes, env: Env) -> Ty:
    if e.name in ("Set", "List"):
        if len(e.args) != 1:
            raise _Fail("E205", f"{e.name} takes one type argument", e.span)
        return (e.name, ty_of(e.args[0], cls, env))
    if e.args:
        raise _Fail("E205", f"{e.name} takes no type arguments", e.span)
    if e.name in QUANTITY_TYPES:
        return (e.name,) if QUANTITY_TYPES[e.name] else REAL
    if e.name in cls.records:
        return (e.name,)
    raise _Fail("E201", f"unknown property type '{e.name}'", e.span,
                "use a quantity type, a record type such as Point, Set<T> or List<T>")


# ---------------------------------------------------------------- classes


def compile_classes(env: Env, decls: dict[str, A.FactType]) -> Classes:
    cls = Classes(records=records(env))
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(n: str, span: Span) -> None:
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            raise _Fail("E406", f"class '{n}' inherits from itself", span,
                        "remove one `extends` from the cycle")
        state[n] = 1
        for p in decls[n].parents:
            if p not in decls:
                raise _Fail("E201", f"unknown parent class '{p}'", decls[n].span)
            visit(p, decls[n].span)
        state[n] = 2
        order.append(n)

    for n, d in decls.items():
        try:
            visit(n, d.span)
        except _Fail as e:
            env.diags.append(e.d)
            return cls
    for n in order:
        if any(a not in cls.defs for a in _ancestors(n, decls)[:-1]):
            continue    # a parent failed to compile and was reported
        try:
            _compile_class(decls[n], decls, cls, env)
        except _Fail as e:
            env.diags.append(e.d)
    return cls


def _ancestors(n: str, decls: dict[str, A.FactType]) -> list[str]:
    """``n``'s ancestors and ``n``, each once, parents before children (the diamond rule)."""
    out: list[str] = []

    def go(c: str) -> None:
        for p in decls[c].parents:
            go(p)
        if c not in out:
            out.append(c)
    go(n)
    return out


def _compile_class(d: A.FactType, decls: dict[str, A.FactType], cls: Classes, env: Env) -> None:
    props: dict[str, Ty] = {}
    derived: dict[str, A.Expr] = {}
    invariants: list[tuple[str, Term]] = []
    for c in _ancestors(d.name, decls):
        for m in decls[c].members:
            if isinstance(m, A.Prop):
                t = ty_of(m.ty, cls, env)
                if props.get(m.name, t) != t:
                    raise _Fail("E202", f"property '{m.name}' is declared with two types",
                                m.span)
                props[m.name] = t
            elif isinstance(m, A.Derived):
                derived[m.name] = m.expr
    cls.prop_types[d.name] = props
    cls.spans[d.name] = d.span
    cls.ancestors[d.name] = tuple(_ancestors(d.name, decls)[:-1])
    for c in _ancestors(d.name, decls):
        for m in decls[c].members:
            if isinstance(m, A.Invariant) and not m.theorem:
                if c == d.name:
                    invariants.append((f"{c}.{m.name}", _Formula(cls, props, derived).body(
                        m.body, m.span)))
                else:
                    invariants += [x for x in cls.defs[c].invariants if x[0] == f"{c}.{m.name}"]
    theorems = []
    for m in d.members:
        if isinstance(m, A.Invariant) and m.theorem:
            theorems.append((f"{d.name}.{m.name}",
                             _Formula(cls, props, derived).body(m.body, m.span)))
            cls.spans[f"{d.name}.{m.name}"] = m.span
        elif isinstance(m, A.Invariant):
            cls.spans[f"{d.name}.{m.name}"] = m.span
    cls.defs[d.name] = ClassDef(d.name, tuple(props), tuple(invariants), tuple(theorems))


_SHIFT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)-(\d+)$")


class _Formula:
    """Compile one class's formulas. Tracks bound variables and their types."""

    def __init__(self, cls: Classes, props: dict[str, Ty], derived: dict[str, A.Expr]) -> None:
        self.cls, self.props, self.derived = cls, props, derived
        self.bound: dict[str, Ty] = {}

    def body(self, items: tuple[A.Formula, ...], span: Span) -> Term:
        return conj([self.formula(f) for f in items])

    def formula(self, f: A.Formula) -> Term:
        if isinstance(f, A.FChain):
            return self.chain(f)
        if isinstance(f, A.FNot):
            return _f("not", self.chain(f.body))
        if isinstance(f, A.FAll) and f.coll is None:
            return self.index_all(f)
        var = f.var
        if var in self.bound or var in self.props:
            raise _Fail("E202", f"'{var}' is already bound", f.span)
        assert f.coll is not None
        coll, ty = self.coll(f.coll)
        elem = ty[1]
        assert isinstance(elem, tuple)
        self.bound[var] = elem
        try:
            inner = self.chain(f.body) if isinstance(f, A.FAll) else self.body(f.body, f.span)
        finally:
            del self.bound[var]
        if isinstance(f, A.FAll):
            return _f("forall", Str(var), coll, inner)
        ex = _f("exists", Str(var), coll, inner)
        return _f("not", ex) if f.negated else ex

    def index_all(self, f: A.FAll) -> Term:
        lists: list[Term] = []
        self.bound[f.var] = REAL
        try:
            inner = self.chain(f.body, lists, f.var)
        finally:
            del self.bound[f.var]
        if not lists:
            raise _Fail("E206", f"`all {f.var}:` without `in` needs a body that indexes a list "
                        f"with {f.var}", f.span, "write `all x in coll: ...` instead")
        if any(x != lists[0] for x in lists):
            raise _Fail("E206", f"`all {f.var}:` indexes lists of different lengths", f.span)
        return _f("forall_idx", Str(f.var), lists[0], inner)

    def chain(self, c: A.FChain, lists: list[Term] | None = None, ivar: str = "") -> Term:
        if not c.ops:
            raise _Fail("E206", "a condition must be a comparison", c.span,
                        "write e.g. `count(vertices) = 4`")
        terms = [self.expr(e, lists, ivar) for e in c.exprs]
        out = []
        for i, op in enumerate(c.ops):
            self.comparable(c.exprs[i], op, c.exprs[i + 1], c.span)
            out.append(_f("cmp", Str(op), terms[i][0], terms[i + 1][0]))
        return conj(out)

    def comparable(self, a: A.Expr, op: str, b: A.Expr, span: Span) -> None:
        """Reject, at compile time, comparisons the exact evaluator cannot decide."""
        for x, y in ((a, b), (b, a)):
            if isinstance(x, A.Call) and x.fn == "angle" and (
                    op not in ("=", "!=") or not isinstance(y, A.Quantity) or y.dims != DEG
                    or y.value not in COS2):
                    raise _Fail("E405", "an angle can only be compared, by = or !=, with "
                                "0, 30, 45, 60, 90, 120, 135, 150 or 180 deg", span,
                                "these are the angles whose cosine squared is rational, "
                                "so the check stays exact")
            if isinstance(x, A.Call) and x.fn == "dist" and (
                    (isinstance(y, A.Quantity) and y.dims) or (isinstance(y, A.BinOp)
                    and _has_dist(y))):
                raise _Fail("E405", "a distance can only be compared with another distance or "
                            "a number", span, "use dist2 (the squared distance) for "
                            "arithmetic, e.g. `dist2(a, b) = dist2(b, c) + dist2(a, c)`")
            if isinstance(x, A.Quantity) and x.dims == DEG and not (
                    isinstance(y, A.Call) and y.fn == "angle"):
                raise _Fail("E301", "an angle in degrees compared with something that is not "
                            "an angle", span)

    # ------------------------------------------------------------ expressions
    def coll(self, e: A.Expr) -> tuple[Term, Ty]:
        if isinstance(e, A.Call) and e.fn in GENERATORS:
            if len(e.args) != GENERATORS[e.fn]:
                raise _Fail("E205", f"{e.fn} takes {GENERATORS[e.fn]} argument(s)", e.span)
            src, ty = self.expr(e.args[0])
            if ty[0] not in ("Set", "List"):
                raise _Fail("E302", f"{e.fn} needs a Set or List", e.args[0].span)
            elem = ty[1]
            rest = [self.expr(a)[0] for a in e.args[1:]]
            gen_ty: Ty = {"cycles": ("List", ("List", elem)), "orderings": ("List", ("List", elem)),
                          "pairs": ("List", ("Pair", elem)),
                          "subsets": ("List", ("Set", elem))}[e.fn]
            return _f(e.fn, src, *rest), gen_ty
        t, ty = self.expr(e)
        if ty[0] not in ("Set", "List"):
            raise _Fail("E302", "a quantifier ranges over a Set, a List or a generator", e.span)
        return t, ty

    def expr(self, e: A.Expr, lists: list[Term] | None = None, ivar: str = "") -> tuple[Term, Ty]:
        def go(x: A.Expr) -> tuple[Term, Ty]:
            return self.expr(x, lists, ivar)
        if isinstance(e, A.Quantity):
            return Num(e.value, e.dims), REAL
        if isinstance(e, A.Name):
            if e.name in self.bound:
                return _f("v", Str(e.name)), self.bound[e.name]
            if e.name in self.props:
                return _f("p", Str(e.name)), self.props[e.name]
            if e.name in self.derived:
                return go(self.derived[e.name])
            m = _SHIFT.match(e.name)
            if m and m.group(1) in self.bound:   # `v[i-1]`: the lexer read `i-1` as one name
                return Compound("-", (_f("v", Str(m.group(1))), Num(Fraction(m.group(2))))), REAL
            raise _Fail("E201", f"unknown name '{e.name}' in a class formula", e.span,
                        "use a property, a derived property or a bound variable")
        if isinstance(e, A.Index):
            obj, ty = go(e.obj)
            idx, _ = go(e.idx)
            if ty[0] not in ("List", "Pair", "Set"):
                raise _Fail("E302", "only a list can be indexed", e.obj.span)
            if lists is not None and ivar and _mentions(e.idx, ivar):
                lists.append(obj)
            elem = ty[1]
            assert isinstance(elem, tuple)
            return _f("idx", obj, idx), elem
        if isinstance(e, A.Field):
            obj, ty = go(e.obj)
            rec = self.cls.records.get(str(ty[0]))
            if rec is None or e.name not in rec:
                raise _Fail("E204", f"unknown field '{e.name}'", e.span)
            return _f("at", obj, Num(Fraction(rec.index(e.name)))), REAL
        if isinstance(e, A.BinOp):
            (lt, _), (rt, _) = go(e.left), go(e.right)
            return Compound(e.op, (lt, rt)), REAL
        if isinstance(e, A.Neg):
            return Compound("-", (go(e.arg)[0],)), REAL
        if isinstance(e, A.TupleLit):
            return _f("tuple", *(go(x)[0] for x in e.items)), ("Tuple",)
        if isinstance(e, A.SetLit):
            items = [go(x) for x in e.items]
            return _f("set", *(t for t, _ in items)), ("Set", items[0][1] if items else REAL)
        if isinstance(e, A.Call) and e.fn in FUNCS:
            if len(e.args) != FUNCS[e.fn]:
                raise _Fail("E205", f"{e.fn} takes {FUNCS[e.fn]} argument(s)", e.span)
            args = [go(a)[0] for a in e.args]
            name = e.fn if e.fn in ("count", "dist", "dist2", "angle") else None
            return (_f(name, *args) if name else Compound(e.fn, tuple(args))), REAL
        if isinstance(e, A.Call) and e.fn in GENERATORS:
            return self.coll(e)
        if isinstance(e, A.Call):
            raise _Fail("E201", f"unknown function '{e.fn}' in a class formula", e.span,
                        "class formulas use count, dist, dist2, angle, abs, min, max and the "
                        "generators cycles, orderings, subsets, pairs")
        raise _Fail("E206", "not allowed in a class formula", e.span)


def _has_dist(e: A.Expr) -> bool:
    if isinstance(e, A.Call):
        return e.fn in ("dist", "angle") or any(_has_dist(a) for a in e.args)
    if isinstance(e, A.BinOp):
        return _has_dist(e.left) or _has_dist(e.right)
    return isinstance(e, A.Neg) and _has_dist(e.arg)


def _mentions(e: A.Expr, var: str) -> bool:
    if isinstance(e, A.Name):
        m = _SHIFT.match(e.name)
        return e.name == var or bool(m and m.group(1) == var)
    if isinstance(e, A.BinOp):
        return _mentions(e.left, var) or _mentions(e.right, var)
    if isinstance(e, A.Neg):
        return _mentions(e.arg, var)
    return False


# ---------------------------------------------------------------- queries


@dataclass
class ObjPlan:
    """An object-layer query, compiled: what to solve and how to report it."""

    kind: str                                   # find | unique | count | check | counterexample
    query: A.Query
    cls: ClassDef
    props: dict[str, Term]                      # property -> value expression (Vars = unknowns)
    unknowns: dict[str, tuple[Var, ...]] = field(default_factory=dict)  # ?x -> coordinates
    is_tuple: dict[str, bool] = field(default_factory=dict)
    theorem: tuple[str, Term] | None = None
    limit: int | None = None
    note: str = ""                              # why there is no bounded instance


def is_object_query(o: A.Okql) -> bool:
    if isinstance(o, (A.Unique, A.Count, A.CheckIs, A.Counterexample)):
        return True
    return isinstance(o, A.Find) and any(
        isinstance(w, A.Holds) and isinstance(w.expr, A.Pattern) for w in o.where)


def plan_query(qy: A.Query, cls: Classes, last_find: ObjPlan | None) -> ObjPlan:
    o = qy.q
    if isinstance(o, A.Counterexample):
        cname = o.theorem.rpartition(".")[0]
        cdef = cls.defs.get(cname)
        found = [t for t in (cdef.theorems if cdef else ()) if t[0] == o.theorem]
        if not found or cdef is None:
            raise _Fail("E201", f"unknown theorem '{o.theorem}'", o.span,
                        "name it as Class.theorem")
        try:
            gen = generic(cdef, cls.prop_types[cname], cls.records)
        except Unsupported as e:
            gen = str(e)
        if isinstance(gen, str):
            return ObjPlan("counterexample", qy, cdef, {}, theorem=found[0], note=gen)
        return ObjPlan("counterexample", qy, cdef, gen, theorem=found[0])
    if isinstance(o, A.CheckIs):
        if o.cls not in cls.defs:
            raise _Fail("E201", f"unknown class '{o.cls}'", o.span)
        if not isinstance(o.obj, A.Pattern):
            raise _Fail("E206", "CHECK needs an instance written as a pattern, "
                        "e.g. `CHECK Quadrilateral{vertices = {...}} IS Square`", o.obj.span)
        p = _Instance(cls, {})
        props = p.pattern(o.obj, cls.defs[o.cls])
        if p.unknowns:
            raise _Fail("E206", "CHECK needs a fully known instance", o.obj.span,
                        "use FIND to solve for unknowns")
        return ObjPlan("check", qy, cls.defs[o.cls], props)
    assert isinstance(o, (A.Find, A.Unique, A.Count))
    kind = {A.Find: "find", A.Unique: "unique", A.Count: "count"}[type(o)]
    if not o.where:
        if last_find is None or {v.name for v in o.vars} != set(last_find.unknowns):
            raise _Fail("E206", f"{kind.upper()} without WHERE refers to the FIND before it, "
                        "which must solve for the same variables", o.span)
        return ObjPlan(kind, qy, last_find.cls, last_find.props, last_find.unknowns,
                       last_find.is_tuple)
    pats = [w.expr for w in o.where if isinstance(w, A.Holds) and isinstance(w.expr, A.Pattern)]
    if len(pats) != 1 or len(o.where) != 1:
        raise _Fail("E206", "an object query's WHERE is exactly one pattern `T{...}`", o.span,
                    "conditions on the unknowns belong in the class's invariants")
    pat = pats[0]
    if pat.cls not in cls.defs:
        raise _Fail("E201", f"unknown class '{pat.cls}'", pat.span)
    declared = {v.name: v.ty for v in o.vars}
    inst = _Instance(cls, declared)
    props = inst.pattern(pat, cls.defs[pat.cls])
    for v in o.vars:
        if v.name not in inst.unknowns:
            raise _Fail("E201", f"?{v.name} does not occur in WHERE", v.span)
    limit = o.limit if isinstance(o, A.Find) else None
    return ObjPlan(kind, qy, cls.defs[pat.cls], props, inst.unknowns, inst.is_tuple,
                   limit=limit)


class _Instance:
    """Turn a pattern into property value expressions; ``?x`` become coordinate Vars."""

    def __init__(self, cls: Classes, declared: dict[str, str | None]) -> None:
        self.cls, self.declared = cls, declared
        self.unknowns: dict[str, tuple[Var, ...]] = {}
        self.is_tuple: dict[str, bool] = {}
        self.fresh = 0

    def pattern(self, p: A.Pattern, cdef: ClassDef) -> dict[str, Term]:
        types = self.cls.prop_types[cdef.name]
        given = dict(p.fields)
        for f in given:
            if f not in types:
                raise _Fail("E204", f"'{cdef.name}' has no property '{f}'", p.span)
        out = {}
        for name, ty in types.items():
            if name in given:
                out[name] = self.value(given[name], ty)
            elif ty[0] in ("Set", "List"):
                raise _Fail("E206", f"property '{name}' is unspecified and has no bound size",
                            p.span, f"give {name} in the pattern")
            else:
                out[name] = self.fresh_value(ty, f"{cdef.name}_{name}")
        return out

    def fresh_value(self, ty: Ty, base: str) -> Term:
        self.fresh += 1
        rec = self.cls.records.get(str(ty[0]))
        if rec is not None:
            return _f("tuple", *(Var(f"U{self.fresh}_{base}_{f}") for f in rec))
        return Var(f"U{self.fresh}_{base}")

    def value(self, e: A.Expr, ty: Ty) -> Term:
        if isinstance(e, A.QVar):
            want = self.declared.get(e.name)
            if want is not None and (want,) != ty and not (want in QUANTITY_TYPES and ty == REAL):
                raise _Fail("E302", f"?{e.name} is declared {want} but used as {ty[0]}", e.span)
            if e.name in self.unknowns:
                vs = self.unknowns[e.name]
                return _f("tuple", *vs) if self.is_tuple[e.name] else vs[0]
            rec = self.cls.records.get(str(ty[0]))
            if rec is not None:
                vs = tuple(Var(f"Q_{e.name}_{f}") for f in rec)
                self.unknowns[e.name], self.is_tuple[e.name] = vs, True
                return _f("tuple", *vs)
            if ty != REAL:
                raise _Fail("E206", f"?{e.name} must stand for a number or a record", e.span)
            self.unknowns[e.name], self.is_tuple[e.name] = (Var(f"Q_{e.name}"),), False
            return Var(f"Q_{e.name}")
        if isinstance(e, A.Quantity):
            if ty != REAL and (ty[0] not in QUANTITY_TYPES):
                raise _Fail("E302", f"expected {ty[0]}, got a number", e.span)
            return Num(e.value, e.dims)
        if isinstance(e, A.Neg) and isinstance(e.arg, A.Quantity):
            return Num(-e.arg.value, e.arg.dims)
        if isinstance(e, A.SetLit) and ty[0] in ("Set", "List"):
            elem = ty[1]
            assert isinstance(elem, tuple)
            return _f("set" if ty[0] == "Set" else "list", *(self.value(x, elem) for x in e.items))
        rec = self.cls.records.get(str(ty[0]))
        if isinstance(e, A.TupleLit) and rec is not None:
            if len(e.items) != len(rec):
                raise _Fail("E205", f"{ty[0]} has {len(rec)} fields", e.span)
            return _f("tuple", *(self.value(x, REAL) for x in e.items))
        if isinstance(e, A.Pattern) and rec is not None and e.cls == ty[0]:
            given = dict(e.fields)
            for f in given:
                if f not in rec:
                    raise _Fail("E204", f"'{e.cls}' has no field '{f}'", e.span)
            return _f("tuple", *(self.value(given[f], REAL) if f in given
                                 else self.fresh_value(REAL, f"{e.cls}_{f}") for f in rec))
        raise _Fail("E302", f"expected a value of type {_show_ty(ty)}", e.span)


def _show_ty(t: Ty) -> str:
    return str(t[0]) + (f"<{_show_ty(t[1])}>" if len(t) > 1 and isinstance(t[1], tuple) else "")


# ---------------------------------------------------------------- generic instances


def size_invariants(cls: ClassDef) -> tuple[str, ...]:
    """The invariants that fix the sizes of a generic instance's collections."""
    return tuple(dict.fromkeys(n for p in cls.props if (n := _size_source(cls, p))))


def _size_source(cls: ClassDef, prop: str) -> str | None:
    found = _size_full(cls, prop)
    return found[1] if found else None


def _size(cls: ClassDef, prop: str) -> int | None:
    found = _size_full(cls, prop)
    return found[0] if found else None


def _size_full(cls: ClassDef, prop: str) -> tuple[int, str] | None:
    """``n`` from a top-level invariant conjunct ``count(prop) = n``."""
    want = Compound("f.count", (Compound("f.p", (Str(prop),)),))

    def conjuncts(t: Term) -> list[Term]:
        if isinstance(t, Compound) and t.functor == "f.and":
            return [c for a in t.args for c in conjuncts(a)]
        return [t]
    for name, f in cls.invariants:
        for c in conjuncts(f):
            if isinstance(c, Compound) and c.functor == "f.cmp" and c.args[0] == Str("=") \
                    and want in c.args[1:]:
                other = c.args[2] if c.args[1] == want else c.args[1]
                if isinstance(other, Num) and other.value.denominator == 1 and other.value >= 0:
                    return int(other.value), name
    return None


def generic(cls: ClassDef, types: Mapping[str, Ty], records: Mapping[str, tuple[str, ...]]
            ) -> dict[str, Term] | str:
    """An instance with an unknown in every slot, or why there is none."""
    out: dict[str, Term] = {}
    k = 0

    def fresh(ty: Ty, base: str) -> Term:
        nonlocal k
        k += 1
        rec = records.get(str(ty[0]))
        if rec is not None:
            return Compound("f.tuple", tuple(Var(f"G{k}_{base}_{f}") for f in rec))
        if ty[0] in ("Set", "List"):
            raise Unsupported("nested collections")
        return Var(f"G{k}_{base}")
    for p in cls.props:
        ty = types[p]
        if ty[0] in ("Set", "List"):
            n = _size(cls, p)
            if n is None:
                return f"property '{p}' has no `count({p}) = n` invariant, so its size is open"
            elem = ty[1]
            assert isinstance(elem, tuple)
            out[p] = Compound(f"f.{str(ty[0]).lower()}", tuple(fresh(elem, p) for _ in range(n)))
        else:
            out[p] = fresh(ty, p)
    return out
