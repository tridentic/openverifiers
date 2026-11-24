"""Lower a checked OV ``Env`` to RawOV: one program per scenario.

Lowering is deterministic and syntactic. Every rule and fact keeps the span
of the OV text it came from. The constructs and what they become:

* ``axiom n(params): body -> heads`` (and ``transformation ... requires ...
  ensures ...``): one rule per head, or a fact when there is no body.
* A head equation ``lhs = rhs`` relates *slots* (fields such as ``b.mass`` and
  calls of functional predicates). It becomes one rule per slot that can be
  solved for: the other slots become premises and the solved value is
  computed with ``is``. Only slots that occur once under ``+ - * /`` and
  unary minus are solvable; anything else is reported (E402) and left to the
  sympy plugin (Milestone 2).
* Functional predicates (``-> T``, and every field) get a rule that derives
  ``neg p(x, v2)`` when two different values are derived: a clash becomes
  INCONSISTENT. Unordered outputs (``-> {T, T}``) get a rule that swaps them.
* ``unordered`` functions build canonical terms: arguments are sorted (at
  lowering time when ground, with ``sort_args`` otherwise), so equal
  structures are equal terms.
* Scenario facts and assumptions about known entities become facts (with
  ``fact:<scenario>`` or ``assume:<name>`` origins). Statements that are not
  plain atoms (inequalities, for example) become checks that derive
  ``neg ov.consistent(<id>)`` when violated.
* Unknowns (``generator A from ...`` and outputs such as ``f(A) -> {C, D}``)
  are solved by candidate elimination. Unknowns linked by statements form a
  component with a candidate relation. Every other statement about them
  eliminates the candidates for which its contradiction is *derived*. A value
  is PROVEN only when exactly one candidate survives a complete generator;
  several give UNKNOWN; none makes the scenario INCONSISTENT.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from ..lang import ast as A
from ..lang.check import Env, ScenarioInfo
from ..lang.errors import Diagnostic, OVError
from ..objects.compile import is_object_query
from ..raw.builtins import ARITH
from ..raw.builtins import evaluate as eval_term
from ..raw.program import (
    Assign,
    Atom,
    Compare,
    Fact,
    Literal,
    Naf,
    Pos,
    Program,
    Rule,
    Span,
    World,
    validate,
)
from ..raw.terms import Compound, Num, Str, Sym, Term, Var, is_ground, order_key, variables
from ..state.load import StateError
from ..state.load import facts as load_state

NEGATE = {"=": "!=", "!=": "=", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}
OV = "ov"


@dataclass(frozen=True)
class QueryPlan:
    """How to answer one ``query``: its RawOV predicate, variables and changes."""

    query: A.Query
    kind: str                       # "find" | "prove"
    pred: str
    vars: tuple[str, ...]           # FIND variables, in order
    unknown_vars: tuple[str, ...]   # which of them name scenario unknowns
    atom: Atom | None = None        # PROVE of one ground atom: asked directly
    retract_items: frozenset[str] = frozenset()
    retract_assumptions: frozenset[str] = frozenset()
    add_assumptions: frozenset[str] = frozenset()
    expect: A.Expect | None = None
    test: str | None = None


@dataclass
class Lowered:
    scenario: str
    program: Program
    queries: list[QueryPlan]
    names: dict[Term, str]                          # display names (never used to reason)
    candidates: dict[str, tuple[str, int, int]]     # unknown -> (cand pred, index, arity)
    meta: dict[str, tuple[Fraction | None, str | None]] = field(default_factory=dict)
    #: object-layer queries (patterns, UNIQUE, COUNT, CHECK, COUNTEREXAMPLE), answered by
    #: ``objects.engine`` rather than by evaluating the program
    objects: list[tuple[A.Query, A.Expect | None, str | None]] = field(default_factory=list)
    #: assumption name -> (its statement's text, the predicates it states). Covers
    #: declared assumptions and the hidden ones that make a fact retractable.
    assumption_info: dict[str, tuple[str, frozenset[str]]] = field(default_factory=dict)


#: Prefix of the hidden assumption that labels a fact some WHAT IF RETRACTs. The fact
#: is lowered as an assumption that is active by default, so the kernel's labels
#: answer "without this fact" with no second evaluation. Hidden names are never
#: shown as assumptions of an answer.
HIDDEN = "fact#"


def is_hidden(name: str) -> bool:
    return name.startswith(HIDDEN)


def _lit_preds(x: object, env: Env) -> set[str]:
    """Predicate names a statement mentions (calls of declared predicates, fields)."""
    out: set[str] = set()
    if isinstance(x, A.Call) and x.fn in env.preds:
        out.add(x.fn)
    if isinstance(x, A.Field):
        out.add(x.name)
    if isinstance(x, tuple):
        for i in x:
            out |= _lit_preds(i, env)
    elif hasattr(x, "__dataclass_fields__"):
        for f in x.__dataclass_fields__:
            if f != "span":
                out |= _lit_preds(getattr(x, f), env)
    return out


class _Fail(Exception):
    def __init__(self, code: str, msg: str, span: Span, hint: str = "") -> None:
        self.d = Diagnostic(code, msg, span, hint)


# ---------------------------------------------------------------- term building


class _Ctx:
    """Translation state for one rule, fact or query."""

    def __init__(self, env: Env, info: ScenarioInfo | None,
                 names: dict[str, Term] | None = None) -> None:
        self.env, self.info = env, info
        self.names: dict[str, Term] = dict(names or {})
        self.pre: list[Literal] = []
        self.used_unknowns: list[str] = []
        self.n = 0
        self.bound: set[str] = set()
        self.var_types: dict[str, str] = {}

    def fresh(self) -> Var:
        self.n += 1
        return Var(f"T_{self.n}")

    def emit(self, out: list[Literal], lit: Literal) -> None:
        out.append(lit)
        if isinstance(lit, Pos):
            for t in lit.atom.args:
                self.bound.update(variables(t))
        elif isinstance(lit, Assign):
            self.bound.add(lit.var.name)

    def flush(self, out: list[Literal]) -> None:
        pre, self.pre = self.pre, []
        for lit in pre:
            self.emit(out, lit)


def _canon(fn: str, args: tuple[Term, ...]) -> Compound:
    return Compound(fn, tuple(sorted(args, key=order_key)))


def _is_arith(t: Term) -> bool:
    return isinstance(t, Compound) and (t.functor in ARITH or any(_is_arith(a) for a in t.args))


def _value(t: Term, cx: _Ctx, span: Span) -> Term:
    """A term usable as an atom argument: arithmetic is computed or assigned."""
    if not _is_arith(t):
        return t
    if isinstance(t, Compound) and t.functor not in ARITH:
        return Compound(t.functor, tuple(_value(a, cx, span) for a in t.args))
    if is_ground(t):
        v = eval_term(t, {})
        if v is None:
            raise _Fail("E402", "this expression has no value (division by zero or "
                        "mismatched units)", span)
        return v
    v = cx.fresh()
    cx.pre.append(Assign(v, t))
    return v


SlotHook = Callable[[A.Expr, Atom, Var], Term]


def term(e: A.Expr, cx: _Ctx, build: bool, slot: SlotHook | None = None) -> Term:
    """Translate an expression. Fields and functional calls add premises to cx.pre."""
    env = cx.env
    if isinstance(e, A.Name):
        return _name(e.name, cx, e.span)
    if isinstance(e, A.QVar):
        info = cx.info
        if info is not None and e.name in info.unknowns:
            return _name(e.name, cx, e.span)
        return Var(f"Q_{e.name}")
    if isinstance(e, A.Quantity):
        return Num(e.value, e.dims)
    if isinstance(e, A.StrLit):
        return Str(e.value)
    if isinstance(e, A.UnknownLit):
        raise _Fail("E206", "`unknown` can only be the value of a fact", e.span)
    if isinstance(e, (A.SetLit, A.Interval)):
        raise _Fail("E206", "a set or interval is not allowed here", e.span)
    if isinstance(e, A.BinOp):
        return Compound(e.op, (term(e.left, cx, build, slot), term(e.right, cx, build, slot)))
    if isinstance(e, A.Neg):
        return Compound("-", (term(e.arg, cx, build, slot),))
    if isinstance(e, A.Field):
        if (isinstance(e.obj, A.Name) and e.obj.name in env.scenarios
                and e.obj.name not in cx.names and _lookup(e.obj.name, cx) is None):
            return _scenario_entity(e.obj.name, e.name, cx, e.span)
        obj = _value(term(e.obj, cx, build, slot), cx, e.span)
        objty = _type_name(e.obj, cx)
        found = env.field_of(objty, e.name) if objty else None
        if found is None:
            raise _Fail("E204", f"no field '{e.name}' here", e.span)
        v = cx.fresh()
        atom = Atom(f"{found[1]}.{e.name}", (obj, v))
        if slot is not None:
            return slot(e, atom, v)
        cx.pre.append(Pos(atom))
        return v
    assert isinstance(e, A.Call)
    if e.fn in ("abs", "min", "max", "canonical"):
        args = tuple(term(a, cx, build, slot) for a in e.args)
        return Compound("sort_args" if e.fn == "canonical" else e.fn, args)
    if e.fn in env.funcs:
        d = env.funcs[e.fn][0]
        fargs = [_value(term(a, cx, build, slot), cx, a.span) for a in e.args]
        for prm in d.params[len(e.args):]:
            assert prm.default is not None
            fargs.append(term(prm.default, cx, True))
        t = Compound(e.fn, tuple(fargs))
        if d.unordered and build:
            if is_ground(t):
                return _canon(e.fn, t.args)
            v = cx.fresh()
            cx.pre.append(Assign(v, Compound("sort_args", (t,))))
            return v
        return t
    p = env.preds[e.fn]
    args = tuple(_value(term(a, cx, build, slot), cx, a.span) for a in e.args)
    v = cx.fresh()
    atom = Atom(p.name, (*args, v))
    if slot is not None:
        return slot(e, atom, v)
    cx.pre.append(Pos(atom))
    return v


def _lookup(name: str, cx: _Ctx) -> object | None:
    info = cx.info
    if name in cx.names:
        return cx.names[name]
    if info is not None and (name in info.unknowns or name in info.entities):
        return name
    return cx.env.ents.get(name)


def _name(name: str, cx: _Ctx, span: Span) -> Term:
    if name in cx.names:
        return cx.names[name]
    info = cx.info
    if info is not None and name in info.unknowns:
        if name not in cx.used_unknowns:
            cx.used_unknowns.append(name)
        return Var(f"U_{name}")
    ent = info.entities.get(name) if info is not None else None
    if ent is None:
        ent = cx.env.ents.get(name)
    if ent is None:
        raise _Fail("E201", f"unknown name '{name}'", span)
    if ent.value is None:
        return Sym(name)
    sub = _Ctx(cx.env, info)
    return _value(term(ent.value, sub, True), sub, span)


def _scenario_entity(scn: str, name: str, cx: _Ctx, span: Span) -> Term:
    info = cx.env.scenarios[scn]
    if cx.info is not None and cx.info is not info:
        raise _Fail("E206", f"this query runs in scenario '{cx.info.decl.name}', not '{scn}'",
                    span)
    cx.info = info
    return _name(name, cx, span)


def _type_name(e: A.Expr, cx: _Ctx) -> str | None:
    """The declared entity type of an expression, for field lookup."""
    env, info = cx.env, cx.info
    if isinstance(e, A.Name):
        ent = (info.entities.get(e.name) if info else None) or env.ents.get(e.name)
        if ent is not None:
            return ent.type
        if info is not None and e.name in info.unknowns:
            t = info.unknowns[e.name]
            return str(t[1]) if t[0] == "e" else None
        return cx.var_types.get(e.name)
    if isinstance(e, A.Field):
        if isinstance(e.obj, A.Name) and e.obj.name in env.scenarios:
            other = env.scenarios[e.obj.name]
            ent = other.entities.get(e.name)
            return ent.type if ent else None
        base = _type_name(e.obj, cx)
        f = env.field_of(base, e.name) if base else None
        return f[0] if f else None
    if isinstance(e, A.Call):
        if e.fn in env.funcs:
            return env.funcs[e.fn][0].result
        if e.fn in env.preds and env.preds[e.fn].outputs:
            return env.preds[e.fn].outputs[0]
    return None


# ---------------------------------------------------------------- literals


def _slot_of(e: A.Expr, cx: _Ctx) -> bool:
    env = cx.env
    if isinstance(e, A.Field):
        return not (isinstance(e.obj, A.Name) and e.obj.name in env.scenarios
                    and _lookup(e.obj.name, cx) is None)
    return isinstance(e, A.Call) and e.fn in env.preds and env.preds[e.fn].functional


def _simple(e: A.Expr, cx: _Ctx) -> bool:
    """No arithmetic and no slots: a pattern or a value."""
    if isinstance(e, (A.BinOp, A.Neg, A.SetLit, A.Interval, A.UnknownLit)):
        return False
    if isinstance(e, A.Call):
        return e.fn in cx.env.funcs and all(_simple(a, cx) for a in e.args)
    if isinstance(e, A.Field):
        return not _slot_of(e, cx)
    return True


def _atom(e: A.Call, cx: _Ctx, build: bool) -> Atom:
    p = cx.env.preds[e.fn]
    args = [_value(term(a, cx, build), cx, a.span) for a in e.args]
    if len(args) < p.arity:
        args.extend(cx.fresh() for _ in range(p.arity - len(args)))
    return Atom(p.name, tuple(args))


def _slot_atom(e: A.Expr, value: A.Expr, cx: _Ctx, build: bool) -> Atom:
    """``slot = value`` as one atom: ``p(args, value)``."""
    if isinstance(e, A.Field):
        holder: list[Atom] = []

        def hook(_e: A.Expr, atom: Atom, _v: Var) -> Term:
            holder.append(atom)
            return _v
        term(e, cx, build, hook)
        atom = holder[0]
    else:
        assert isinstance(e, A.Call)
        p = cx.env.preds[e.fn]
        atom = Atom(p.name, (*(_value(term(a, cx, build), cx, a.span) for a in e.args),
                             Var("_")))
    val = _value(term(value, cx, build), cx, value.span)
    return Atom(atom.pred, (*atom.args[:-1], val))


def _member_atom(lit: A.Member, cx: _Ctx, build: bool) -> Atom:
    p = cx.env.preds["member"]
    return Atom(p.name, (_value(term(lit.coll, cx, build), cx, lit.coll.span),
                         _value(term(lit.item, cx, build), cx, lit.item.span)))


def body(lits: Iterable[A.Lit], cx: _Ctx, out: list[Literal]) -> None:
    """Translate premises (patterns are matched, not canonicalised)."""
    for lit in lits:
        _body_lit(lit, cx, out)


def _body_lit(lit: A.Lit, cx: _Ctx, out: list[Literal]) -> None:
    if isinstance(lit, A.Holds):
        assert isinstance(lit.expr, A.Call)
        a = _atom(lit.expr, cx, False)
        cx.flush(out)
        cx.emit(out, Pos(a))
    elif isinstance(lit, A.Member):
        if isinstance(lit.coll, A.Interval):
            x = _value(term(lit.item, cx, False), cx, lit.span)
            lo = term(lit.coll.lo, cx, False)
            hi = term(lit.coll.hi, cx, False)
            cx.flush(out)
            out.extend((Compare(">=", x, lo), Compare("<=", x, hi)))
            return
        a = _member_atom(lit, cx, False)
        cx.flush(out)
        cx.emit(out, Pos(a))
    elif isinstance(lit, A.Not):
        inner = lit.lit
        if isinstance(inner, A.Cmp):
            _body_lit(A.Cmp(NEGATE[inner.op], inner.left, inner.right, inner.span), cx, out)
            return
        if isinstance(inner, A.Member) and isinstance(inner.coll, A.Interval):
            raise _Fail("E206", "`not x in [a, b]` is not supported in premises", lit.span,
                        "write two axioms, one with `x < a` and one with `x > b`")
        a = _member_atom(inner, cx, False) if isinstance(inner, A.Member) else \
            _atom(_call(inner), cx, False)
        cx.flush(out)
        if cx.env.preds[a.pred].closed:
            out.append(Naf(a))
        else:  # open world: `not p` holds only when `neg p` is derived
            cx.emit(out, Pos(a.complement()))
    else:
        _body_eq(lit, cx, out)


def _call(lit: A.Lit) -> A.Call:
    assert isinstance(lit, A.Holds) and isinstance(lit.expr, A.Call)
    return lit.expr


def _body_eq(lit: A.Cmp, cx: _Ctx, out: list[Literal]) -> None:
    if lit.op == "=":
        for s, v in ((lit.left, lit.right), (lit.right, lit.left)):
            if _slot_of(s, cx) and _simple(v, cx):
                a = _slot_atom(s, v, cx, False)
                cx.flush(out)
                cx.emit(out, Pos(a))
                return
    left = term(lit.left, cx, False)
    right = term(lit.right, cx, False)
    cx.flush(out)
    if lit.op != "=":
        out.append(Compare(lit.op, left, right))
        return
    free = (set(variables(left)) | set(variables(right))) - cx.bound
    if not free:
        out.append(Compare("=", left, right))
        return
    if len(free) == 1:
        (x,) = free
        for lhs, rhs in ((left, right), (right, left)):
            solved = _solve(lhs, rhs, Var(x))
            if solved is not None:
                cx.emit(out, Assign(Var(x), solved))
                return
    raise _Fail("E402", "cannot solve this equation: "
                f"{', '.join(sorted(v.removeprefix('V_') for v in free))} unknown", lit.span,
                "bind all but one variable first; nonlinear equations need the sympy plugin")


def _count(t: Term, x: Var) -> int:
    if t == x:
        return 1
    return sum(_count(a, x) for a in t.args) if isinstance(t, Compound) else 0


def _solve(lhs: Term, rhs: Term, x: Var) -> Term | None:
    """Solve ``lhs = rhs`` for x when x occurs once in lhs, under + - * / and negation."""
    if _count(lhs, x) != 1 or _count(rhs, x) != 0:
        return None
    while lhs != x:
        if not isinstance(lhs, Compound):
            return None
        if lhs.functor == "-" and len(lhs.args) == 1:
            lhs, rhs = lhs.args[0], Compound("-", (rhs,))
            continue
        if lhs.functor not in ("+", "-", "*", "/") or len(lhs.args) != 2:
            return None
        a, b = lhs.args
        left = _count(a, x) == 1
        other = b if left else a
        op = lhs.functor
        if op == "+":
            rhs = Compound("-", (rhs, other))
        elif op == "*":
            rhs = Compound("/", (rhs, other))
        elif op == "-":
            rhs = Compound("+", (rhs, other)) if left else Compound("-", (other, rhs))
        else:
            rhs = Compound("*", (rhs, other)) if left else Compound("/", (other, rhs))
        lhs = a if left else b
    return rhs


# ---------------------------------------------------------------- contradictions


def contradiction(lit: A.FactLit, cx: _Ctx) -> list[list[Literal]]:
    """Alternative premise lists, each of which derives that ``lit`` is false."""
    env = cx.env
    if isinstance(lit, A.Arrow):
        lit = A.Holds(_arrow_call(lit), lit.span)
    if isinstance(lit, A.Not):
        inner = lit.lit
        if isinstance(inner, A.Cmp):
            out: list[Literal] = []
            _body_lit(inner, cx, out)
            return [out]
        out = []
        a = _member_atom(inner, cx, False) if isinstance(inner, A.Member) else \
            _atom(_call(inner), cx, False)
        cx.flush(out)
        return [[*out, Pos(a)]]
    if isinstance(lit, (A.Holds, A.Member)):
        out = []
        if isinstance(lit, A.Member):
            if isinstance(lit.coll, A.Interval):
                x = _value(term(lit.item, cx, False), cx, lit.span)
                lo, hi = term(lit.coll.lo, cx, False), term(lit.coll.hi, cx, False)
                cx.flush(out)
                return [[*out, Compare("<", x, lo)], [*out, Compare(">", x, hi)]]
            a = _member_atom(lit, cx, False)
        else:
            a = _atom(_call(lit), cx, False)
        cx.flush(out)
        if env.preds[a.pred].closed:
            return [[*out, Naf(a)]]
        return [[*out, Pos(a.complement())]]
    assert isinstance(lit, A.Cmp)
    if lit.op == "=":
        for s, v in ((lit.left, lit.right), (lit.right, lit.left)):
            if _slot_of(s, cx) and _simple(v, cx):
                pre: list[Literal] = []
                a = _slot_atom(s, v, cx, False)
                cx.flush(pre)
                other = cx.fresh()
                alts: list[list[Literal]] = [[*pre, Pos(Atom(a.pred, (*a.args[:-1], other))),
                                              Compare("!=", other, a.args[-1])]]
                if not env.preds[a.pred].closed:
                    alts.append([*pre, Pos(a.complement())])
                return alts
    out = []
    _body_lit(A.Cmp(NEGATE[lit.op], lit.left, lit.right, lit.span), cx, out)
    return [out]


def _arrow_call(lit: A.Arrow) -> A.Call:
    assert isinstance(lit.call, A.Call)
    outs = lit.out.items if isinstance(lit.out, A.SetLit) else (lit.out,)
    return A.Call(lit.call.fn, (*lit.call.args, *outs), lit.span)


# ---------------------------------------------------------------- the lowering


class _Lowering:
    def __init__(self, env: Env, info: ScenarioInfo,
                 retracted: frozenset[object] = frozenset()) -> None:
        self.env, self.info = env, info
        self.retracted = retracted          # shapes of the facts some WHAT IF retracts
        self.assumption_info: dict[str, tuple[str, frozenset[str]]] = {}
        self.scn = info.decl.name
        self.facts: list[Fact] = []
        self.rules: list[Rule] = []
        self.closed: set[str] = set()
        self.ids: set[str] = set()
        self.stmt_items: list[tuple[A.FactStmt | A.AssumeStmt, set[str]]] = []
        self.meta: dict[str, tuple[Fraction | None, str | None]] = {}
        self.candidates: dict[str, tuple[str, int, int]] = {}
        self.queries: list[QueryPlan] = []
        self.nq = 0

    def uid(self, base: str) -> str:
        i, out = 1, base
        while out in self.ids:
            i += 1
            out = f"{base}#{i}"
        self.ids.add(out)
        return out

    def rule(self, rid: str, head: Atom, lits: list[Literal], span: Span | None) -> str:
        rid = self.uid(rid)
        self.rules.append(Rule(rid, head, tuple(lits), span))
        return rid

    def fact(self, fid: str, atom: Atom, origin: str, span: Span | None) -> str:
        fid = self.uid(fid)
        self.facts.append(Fact(fid, atom, origin, span))
        return fid

    # ------------------------------------------------------------ packages
    def packages(self) -> None:
        env = self.env
        pkgs = set(self.info.packages)
        for p in env.preds.values():
            if p.pkg not in pkgs:
                continue
            if p.closed:
                self.closed.add(p.name)
            xs = tuple(Var(f"X{i}") for i in range(p.n_in))
            if p.functional:
                v1, v2 = Var("V1"), Var("V2")
                self.rule(f"{p.pkg}.{p.name}.functional", Atom(p.name, (*xs, v2), True),
                          [Pos(Atom(p.name, (*xs, v1))), Pos(Atom(p.name, (*xs, v2))),
                           Compare("!=", v1, v2)], p.span)
            elif len(p.outputs) > 1:
                ys = tuple(Var(f"Y{i}") for i in range(len(p.outputs)))
                for i in range(len(ys) - 1):
                    sw = list(ys)
                    sw[i], sw[i + 1] = sw[i + 1], sw[i]
                    self.rule(f"{p.pkg}.{p.name}.unordered", Atom(p.name, (*xs, *sw)),
                              [Pos(Atom(p.name, (*xs, *ys)))], p.span)
        guards: dict[str, list[tuple[A.Lit, ...]]] = {}
        for pkg, c in env.controllers:
            if pkg in pkgs:
                for n in {n for g in (*c.pipes, *c.branches) for n in g}:
                    guards.setdefault(n, []).append(c.guards)
        for pkg, ax in env.axioms:
            if pkg in pkgs:
                for g in guards.get(ax.name, [()]) if ax.kind == "transformation" else [()]:
                    self.axiom(pkg, ax, g)

    def axiom(self, pkg: str, ax: A.Axiom, guard: tuple[A.Lit, ...]) -> None:
        base = f"{pkg}.{ax.name}"
        for h in ax.head:
            for head, lits, suffix in self.head(ax, h, guard):
                if not lits and is_ground_atom(head):
                    self.fact(base + suffix, head, f"axiom:{pkg}", ax.span)
                else:
                    self.rule(base + suffix, head, lits, ax.span)

    def _ctx(self, ax: A.Axiom) -> tuple[_Ctx, list[Literal]]:
        cx = _Ctx(self.env, None, {p.name: Var(f"V_{p.name}") for p in ax.params})
        cx.var_types = {p.name: p.type for p in ax.params}
        return cx, []

    def head(self, ax: A.Axiom, h: A.Lit, guard: tuple[A.Lit, ...]
             ) -> list[tuple[Atom, list[Literal], str]]:
        env = self.env

        def premises() -> tuple[_Ctx, list[Literal]]:
            cx, out = self._ctx(ax)
            body((*ax.body, *guard), cx, out)
            return cx, out

        if isinstance(h, (A.Holds, A.Not, A.Member)):
            cx, out = premises()
            if isinstance(h, A.Member):
                a = _member_atom(h, cx, True)
            else:
                inner = h.lit if isinstance(h, A.Not) else h
                a = _atom(_call(inner), cx, True)
                if isinstance(h, A.Not):
                    a = a.complement()
            cx.flush(out)
            return [(a, out, "")]
        assert isinstance(h, A.Cmp)
        # set-valued ``p(x) = {a, b}``: one conclusion per member
        for s, v in ((h.left, h.right), (h.right, h.left)):
            if isinstance(s, A.Call) and isinstance(v, A.SetLit) and s.fn in env.preds:
                res = []
                for item in v.items:
                    cx, out = premises()
                    a = _atom(A.Call(s.fn, (*s.args, item), s.span), cx, True)
                    cx.flush(out)
                    res.append((a, out, ""))
                return res
        return self.equation(ax, h, premises)

    def equation(self, ax: A.Axiom, h: A.Cmp,
                 premises: Callable[[], tuple[_Ctx, list[Literal]]]
                 ) -> list[tuple[Atom, list[Literal], str]]:
        # Find the slots by translating once with a recording hook.
        count = [0]

        def counter(_e: A.Expr, _a: Atom, v: Var) -> Term:
            count[0] += 1
            return v
        probe, _ = premises()
        term(h.left, probe, True, counter)
        term(h.right, probe, True, counter)
        if count[0] == 0:
            raise _Fail("E401", "this conclusion has nothing to derive", h.span,
                        "a conclusion equation needs a field or a functional predicate")
        res = []
        for target in range(count[0]):
            cx, out = premises()
            seen = [0]
            found: dict[str, object] = {}

            def hook(e: A.Expr, atom: Atom, v: Var, cx: _Ctx = cx, seen: list[int] = seen,
                     target: int = target, found: dict[str, object] = found) -> Term:
                i = seen[0]
                seen[0] += 1
                if i == target:
                    found["atom"], found["var"], found["expr"] = atom, v, e
                else:
                    cx.pre.append(Pos(atom))
                return v
            left = term(h.left, cx, True, hook)
            right = term(h.right, cx, True, hook)
            cx.flush(out)
            v = found["var"]
            atom = found["atom"]
            assert isinstance(v, Var) and isinstance(atom, Atom)
            solved = _solve(left, right, v)
            if solved is None:
                solved = _solve(right, left, v)
            if solved is None:
                continue
            val = _value(solved, cx, h.span)
            cx.flush(out)
            head = Atom(atom.pred, (*atom.args[:-1], val))
            res.append((head, out, f"#{_slot_label(found['expr'])}" if count[0] > 1 else ""))
        if not res:
            raise _Fail("E402", "cannot solve this equation for any of its terms", h.span,
                        "nonlinear equations need the sympy plugin (Milestone 2)")
        return res

    # ------------------------------------------------------------ scenario
    def scenario(self) -> None:
        info, env = self.info, self.env
        for name, path, file, span in env.states:   # imported OVStates (trusted loader)
            if file == info.decl.span.file:
                try:
                    for f in load_state(name, path.read_text(), span):
                        self.fact(f.id, f.atom, f.origin, f.span)
                except (StateError, ValueError) as e:
                    raise _Fail("E209", f"OVState '{name}': {e}", span) from None
        stmts = [self.hide(st) for st in _stmts(env, info.decl)]
        known: set[str] = set()
        binders: list[tuple[list[str], list[Literal], A.FactStmt | A.GenUse]] = []
        constraints: list[tuple[A.FactStmt | A.AssumeStmt, list[str]]] = []
        for st in stmts:
            if isinstance(st, A.GenUse):
                assert isinstance(st.source, A.Call)
                gd = env.gens[st.source.fn][0]
                for n in st.names:
                    cx = _Ctx(env, info)
                    args = {p.name: _value(term(a, cx, True), cx, a.span)
                            for p, a in zip(gd.params, st.source.args, strict=True)}
                    src = gd.source
                    assert isinstance(src, A.Call)
                    gx = _Ctx(env, None, args)
                    a = _atom(src, gx, True)
                    atom = Atom(a.pred, (*a.args[:-1], Var(f"U_{n}")))
                    binders.append(([n], [Pos(atom)], st))
                    known.add(n)
            elif isinstance(st, (A.FactStmt, A.AssumeStmt)):
                used = _unknowns_in(st.lit, info)
                new = [u for u in used if u not in known]
                if new and isinstance(st, A.FactStmt) and isinstance(st.lit, A.Arrow):
                    cx = _Ctx(env, info)
                    a = _atom(_arrow_call(st.lit), cx, True)
                    lits: list[Literal] = []
                    cx.flush(lits)
                    binders.append((used, [*lits, Pos(a)], st))
                    known.update(new)
                    self.stmt_items.append((st, set()))
                elif new:
                    raise _Fail("E201", f"unknown name '{new[0]}'", st.span,
                                "unknowns come from `generator X from ...` or `f(x) -> {X}`")
                elif used:
                    constraints.append((st, used))
                else:
                    self.known_fact(st)
        self.unknowns(binders, constraints)

    def hide(self, st: A.Stmt) -> A.Stmt:
        """A fact some WHAT IF retracts becomes a hidden, default-active assumption."""
        if isinstance(st, A.AssumeStmt):
            self.note(st.name, st)
        if isinstance(st, A.FactStmt) and _shape(st.lit) in self.retracted and not (
                isinstance(st.lit, A.Arrow) and _unknowns_in(st.lit, self.info)):
            name = f"{HIDDEN}{self.scn}.L{st.span.line}C{st.span.col}"
            self.note(name, st)
            return A.AssumeStmt(name, st.lit, st.confidence, st.source, st.span)
        return st

    def note(self, name: str, st: A.FactStmt | A.AssumeStmt) -> None:
        lines = self.env.sources().get(st.span.file, "").splitlines()
        text = lines[st.span.line - 1].strip() if 0 < st.span.line <= len(lines) else name
        self.assumption_info[name] = (text, frozenset(_lit_preds(st.lit, self.env)))

    def known_fact(self, st: A.FactStmt | A.AssumeStmt) -> None:
        env, info = self.env, self.info
        origin = f"assume:{st.name}" if isinstance(st, A.AssumeStmt) else f"fact:{self.scn}"
        fid = f"{self.scn}.{st.name}" if isinstance(st, A.AssumeStmt) else \
            f"{self.scn}.L{st.span.line}"
        items: set[str] = set()
        self.stmt_items.append((st, items))
        lit = st.lit
        if isinstance(lit, A.Cmp) and isinstance(lit.right, A.UnknownLit):
            return  # ``fact x = unknown``: explicitly not known, nothing is stated
        cx = _Ctx(env, info)
        atoms: list[Atom] = []
        if isinstance(lit, A.Arrow):
            outs = lit.out.items if isinstance(lit.out, A.SetLit) else (lit.out,)
            p = env.preds[_arrow_call(lit).fn]
            if len(outs) == len(p.outputs):
                atoms.append(_atom(_arrow_call(lit), cx, True))
            else:
                assert isinstance(lit.call, A.Call)
                atoms.extend(_atom(A.Call(lit.call.fn, (*lit.call.args, o), lit.span), cx, True)
                             for o in outs)
        elif isinstance(lit, A.Holds):
            atoms.append(_atom(_call(lit), cx, True))
        elif isinstance(lit, A.Not) and isinstance(lit.lit, A.Holds):
            atoms.append(_atom(_call(lit.lit), cx, True).complement())
        elif isinstance(lit, A.Member) and not isinstance(lit.coll, A.Interval):
            atoms.append(_member_atom(lit, cx, True))
        elif isinstance(lit, A.Cmp) and lit.op == "=":
            for s, v in ((lit.left, lit.right), (lit.right, lit.left)):
                if _slot_of(s, cx) and not _slot_of(v, cx):
                    atoms.append(_slot_atom(s, v, cx, True))
                    break
        if atoms and not cx.pre and all(is_ground_atom(a) for a in atoms):
            for a in atoms:
                i = self.fact(fid, a, origin, st.span)
                items.add(i)
                self.meta[i] = (st.confidence, st.source)
            return
        # Anything else is a check: its contradiction makes the scenario inconsistent.
        cid = self.uid(f"{self.scn}.check.L{st.span.line}")
        items.add(self.fact(cid, Atom(f"{OV}.consistent", (Str(cid),)), f"fact:{self.scn}",
                            st.span))
        for alt in contradiction(lit, _Ctx(env, info)):
            pre = [Pos(self.assumption(st.name))] if isinstance(st, A.AssumeStmt) else []
            items.add(self.rule(cid, Atom(f"{OV}.consistent", (Str(cid),), True), pre + alt,
                                st.span))

    def assumption(self, name: str) -> Atom:
        a = Atom(f"{OV}.assumption", (Sym(name),))
        fid = f"{self.scn}.assume.{name}"
        if fid not in self.ids:
            self.fact(fid, a, f"assume:{name}", None)
        return a

    def unknowns(self, binders: Sequence[tuple[list[str], list[Literal], object]],
                 constraints: list[tuple[A.FactStmt | A.AssumeStmt, list[str]]]) -> None:
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent.setdefault(x, x) != x:
                x = parent[x]
            return x
        for names, _, _ in binders:
            for n in names[1:]:
                parent[find(n)] = find(names[0])
            find(names[0])
        for _, names in constraints:
            for n in names[1:]:
                parent[find(n)] = find(names[0])
        order = list(dict.fromkeys(n for names, _, _ in binders for n in names))
        comps: dict[str, list[str]] = {}
        for n in order:
            comps.setdefault(find(n), []).append(n)
        for members in comps.values():
            self.component(members, [b for b in binders if find(b[0][0]) == find(members[0])],
                           [c for c in constraints if find(c[1][0]) == find(members[0])])

    def component(self, members: list[str],
                  binders: Sequence[tuple[list[str], list[Literal], object]],
                  constraints: list[tuple[A.FactStmt | A.AssumeStmt, list[str]]]) -> None:
        k = "_".join(members)
        us = tuple(Var(f"U_{n}") for n in members)
        p = {x: f"{OV}.{x}.{self.scn}.{k}" for x in ("cand0", "elim", "cand", "some")}
        self.closed.update(p.values())
        span = self.info.decl.span
        self.rule(p["cand0"], Atom(p["cand0"], us), [lit for _, ls, _ in binders for lit in ls],
                  span)
        for st, _ in constraints:
            items: set[str] = set()
            self.stmt_items.append((st, items))
            pre = [Pos(self.assumption(st.name))] if isinstance(st, A.AssumeStmt) else []
            for alt in contradiction(st.lit, _Ctx(self.env, self.info)):
                items.add(self.rule(f"{self.scn}.L{st.span.line}", Atom(p["elim"], us),
                                    [Pos(Atom(p["cand0"], us)), *pre, *alt], st.span))
        self.rule(p["cand"], Atom(p["cand"], us), [Pos(Atom(p["cand0"], us)),
                                                    Naf(Atom(p["elim"], us))], span)
        us2 = tuple(Var(f"{u.name}_2") for u in us)
        for i, n in enumerate(members):
            other, value = f"{OV}.other.{self.scn}.{n}", f"{OV}.value.{self.scn}.{n}"
            self.closed.add(other)
            self.rule(other, Atom(other, (us[i],)), [Pos(Atom(p["cand"], us)),
                      Pos(Atom(p["cand"], us2)), Compare("!=", us[i], us2[i])], span)
            self.rule(value, Atom(value, (us[i],)), [Pos(Atom(p["cand"], us)),
                      Naf(Atom(other, (us[i],)))], span)
            self.candidates[n] = (p["cand"], i, len(us))
        self.rule(p["some"], Atom(p["some"]), [Pos(Atom(p["cand"], us))], span)
        ok = Atom(f"{OV}.consistent", (Str(k),))
        self.fact(f"{self.scn}.{k}.consistent", ok, f"axiom:{OV}.generators", span)
        self.rule(f"{self.scn}.{k}.none", ok.complement(), [Naf(Atom(p["some"]))], span)

    # ------------------------------------------------------------ queries
    def query(self, qy: A.Query, expect: A.Expect | None, test: str | None) -> None:
        o = qy.q
        retract: set[str] = set()
        r_assume: set[str] = set()
        add: set[str] = set()
        while isinstance(o, A.WhatIf):
            for c in o.changes:
                if isinstance(c, A.AssumeName):
                    add.add(c.name)
                    continue
                st = self.statement(c.lit, c.span)
                if isinstance(st, A.AssumeStmt):
                    r_assume.add(st.name)
                else:
                    retract |= dict((id(s), i) for s, i in self.stmt_items)[id(st)]
            o = o.then
        self.nq += 1
        pred = f"{OV}.query.{self.scn}.{self.nq}"
        cx = _Ctx(self.env, self.info)
        out: list[Literal] = []
        if isinstance(o, A.Find):
            body(o.where, cx, out)
            head_vars = tuple(term(v, cx, False) for v in o.vars)
            self.rule(pred, Atom(pred, head_vars), self.values(cx) + out, qy.span)
            unknowns = tuple(v.name for v in o.vars if v.name in self.info.unknowns)
            plan = QueryPlan(qy, "find", pred, tuple(v.name for v in o.vars), unknowns)
        else:
            assert isinstance(o, A.Prove)
            body((o.lit,), cx, out)
            direct = out[0].atom if (len(out) == 1 and isinstance(out[0], Pos)
                                     and isinstance(o.lit, (A.Holds, A.Member))
                                     and not cx.used_unknowns
                                     and is_ground_atom(out[0].atom)) else None
            self.rule(pred, Atom(pred), self.values(cx) + out, qy.span)
            for alt in contradiction(o.lit, _Ctx(self.env, self.info)):
                cx2 = _Ctx(self.env, self.info)
                cx2.used_unknowns = list(cx.used_unknowns)
                self.rule(pred, Atom(pred, (), True), self.values(cx2) + alt, qy.span)
            plan = QueryPlan(qy, "prove", pred, (), (), direct)
        self.queries.append(QueryPlan(plan.query, plan.kind, plan.pred, plan.vars,
                                      plan.unknown_vars, plan.atom, frozenset(retract),
                                      frozenset(r_assume), frozenset(add), expect, test))

    def values(self, cx: _Ctx) -> list[Literal]:
        return [Pos(Atom(f"{OV}.value.{self.scn}.{n}", (Var(f"U_{n}"),)))
                for n in cx.used_unknowns]

    def statement(self, lit: A.FactLit, span: Span) -> A.FactStmt | A.AssumeStmt:
        want = _shape(lit)
        for st, _ in self.stmt_items:
            if _shape(st.lit) == want:
                return st
        raise _Fail("E201", "no fact or assumption of this scenario matches", span,
                    "RETRACT must repeat a `fact` or `assume` statement exactly")

    def program(self) -> Program:
        worlds = tuple(World(p, True) for p in sorted(self.closed))
        return Program(worlds, tuple(self.facts), tuple(self.rules))


def is_ground_atom(a: Atom) -> bool:
    return all(is_ground(t) for t in a.args)


def _slot_label(e: object) -> str:
    if isinstance(e, A.Field):
        return e.name
    return e.fn if isinstance(e, A.Call) else "value"


def _shape(x: object) -> object:
    """A node without spans, for matching RETRACT targets to statements."""
    if isinstance(x, tuple):
        return tuple(_shape(i) for i in x)
    if hasattr(x, "__dataclass_fields__"):
        return (type(x).__name__, *(_shape(getattr(x, f)) for f in x.__dataclass_fields__
                                    if f != "span"))
    return x


def _unknowns_in(x: object, info: ScenarioInfo) -> list[str]:
    out: list[str] = []

    def walk(n: object) -> None:
        if isinstance(n, A.Name) and n.name in info.unknowns and n.name not in info.entities:
            if n.name not in out:
                out.append(n.name)
        elif isinstance(n, tuple):
            for i in n:
                walk(i)
        elif hasattr(n, "__dataclass_fields__"):
            for f in n.__dataclass_fields__:
                walk(getattr(n, f))
    walk(x)
    return out


def _changes_of(o: object) -> list[A.Retract | A.AssumeName]:
    out: list[A.Retract | A.AssumeName] = []
    while isinstance(o, A.WhatIf):
        out.extend(o.changes)
        o = o.then
    return out


def _stmts(env: Env, s: A.Scenario) -> list[A.Stmt]:
    base = _stmts(env, env.scenarios[s.extends].decl) if s.extends else []
    return [x for x in base if not isinstance(x, (A.Query, A.Expect))] + list(s.stmts)


# ---------------------------------------------------------------- entry point


def lower(env: Env, files: set[str] | None = None) -> list[Lowered]:
    """Lower the scenarios of a checked Env, with the queries that run in them.

    ``files`` limits this to scenarios written in those files (default: the
    main file only; package tests run when their package file is named).
    """
    files = {env.main.file} if files is None else files
    out: list[Lowered] = []
    errors: list[Diagnostic] = []
    plans = _query_homes(env, errors, files)
    for pkg, mod in env.modules.items():
        if mod.file in files:  # lower the package's own axioms even if no scenario uses them
            stub = A.Scenario(f"<{pkg}>", (pkg,), None, (), mod.items[0].span)
            lw = _Lowering(env, ScenarioInfo(stub, (pkg,)))
            try:
                lw.packages()
            except _Fail as f:
                errors.append(f.d)
                continue
            errors.extend(_unsafe(lw.program(), stub.span))
    for name, info in env.scenarios.items():
        if info.decl.span.file not in files:
            continue
        retracted = frozenset(_shape(c.lit) for qy, _, _ in plans.get(name, [])
                              for c in _changes_of(qy.q) if isinstance(c, A.Retract))
        lw = _Lowering(env, info, retracted)
        try:
            lw.packages()
            lw.scenario()
            objs = []
            for qy, ex, test in plans.get(name, []):
                if is_object_query(qy.q):
                    objs.append((qy, ex, test))
                else:
                    lw.query(qy, ex, test)
        except _Fail as f:
            errors.append(f.d)
            continue
        prog = lw.program()
        errors.extend(_unsafe(prog, info.decl.span))
        out.append(Lowered(name, prog, lw.queries, _display(env, info), lw.candidates, lw.meta,
                           objs, lw.assumption_info))
    if errors:
        raise OVError(errors, env.sources())
    return out


def _unsafe(prog: Program, default: Span) -> list[Diagnostic]:
    spans = {r.id: r.span for r in prog.rules}
    out = []
    for msg in dict.fromkeys(validate(prog)):
        rid = msg.split("'")[1] if "'" in msg else ""
        out.append(Diagnostic("E403", f"lowered rule is unsafe: {msg}", spans.get(rid) or default,
                              "every variable must be bound by a premise before it is used in "
                              "`not`, a comparison or arithmetic"))
    return out


def _query_homes(env: Env, errors: list[Diagnostic], files: set[str]
                 ) -> dict[str, list[tuple[A.Query, A.Expect | None, str | None]]]:
    """Which scenario each query runs in, paired with the ``expect`` after it."""
    homes: dict[str, list[tuple[A.Query, A.Expect | None, str | None]]] = {}

    def place(seq: Iterable[object], default: str | None, test: str | None) -> None:
        last: tuple[A.Query, str | None] | None = None
        pending: list[tuple[A.Query, str | None]] = []
        expects: dict[int, A.Expect] = {}
        for x in seq:
            if isinstance(x, A.Query):
                home = _qualified(x, env) or default
                last = (x, home)
                pending.append(last)
            elif isinstance(x, A.Expect):
                if last is None:
                    errors.append(Diagnostic("E206", "`expect` must follow a `query`", x.span))
                    continue
                expects[id(last[0])] = x
                last = None
        for qy, home in pending:
            if home is None:
                errors.append(Diagnostic("E206", "cannot tell which scenario this query is "
                                         "about", qy.span, "name it, e.g. `t.block.mass`"))
                continue
            homes.setdefault(home, []).append((qy, expects.get(id(qy)), test))

    mods = (env.main, *(m for m in env.modules.values() if m is not env.main))
    for mod in (m for m in mods if m.file in files):
        top_scs = [i for i in mod.items if isinstance(i, A.Scenario)]
        for it in mod.items:
            if isinstance(it, A.Scenario):
                place(it.stmts, it.name, None)
            elif isinstance(it, A.Test):
                scs = [s for s in it.stmts if isinstance(s, A.Scenario)]
                for s in scs:
                    place(s.stmts, s.name, it.name)
                place(it.stmts, scs[0].name if len(scs) == 1 else None, it.name)
        place(mod.items, top_scs[0].name if len(top_scs) == 1 else None, None)
    return homes


def _qualified(qy: A.Query, env: Env) -> str | None:
    found: list[str] = []

    def walk(n: object) -> None:
        if isinstance(n, A.Field) and isinstance(n.obj, A.Name) and n.obj.name in env.scenarios:
            found.append(n.obj.name)
        if isinstance(n, tuple):
            for i in n:
                walk(i)
        elif hasattr(n, "__dataclass_fields__"):
            for f in n.__dataclass_fields__:
                walk(getattr(n, f))
    walk(qy.q)
    return found[0] if found else None


def _display(env: Env, info: ScenarioInfo) -> dict[Term, str]:
    out: dict[Term, str] = {}
    for ent in (*env.ents.values(), *info.entities.values()):
        if ent.value is not None:
            with contextlib.suppress(_Fail):
                out.setdefault(_name(ent.name, _Ctx(env, info), ent.span), ent.name)
    return out
