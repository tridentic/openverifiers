"""Load modules, resolve names, check types and units.

``load`` parses a file plus every package it imports or uses (from the
file's directory, then the standard library in ``openverifiers/packages``),
builds one symbol table (``Env``) and checks every declaration, axiom,
scenario and query. It raises ``OVError`` with every error found, so one run
reports them all. Lowering (``openverifiers.lower``) runs only on a checked
``Env``.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

# The object layer compiles classes during checking; it imports `lang.ast` only.
from ..objects.compile import Classes, ObjPlan, compile_classes, is_object_query, plan_query
from ..objects.compile import _Fail as ObjFail
from ..raw.program import Span
from ..raw.terms import Dims, make_dims
from . import ast as A
from .errors import Diagnostic, OVError
from .parser import parse
from .units import QUANTITY_TYPES, dims_text

STDLIB = Path(__file__).resolve().parents[1] / "packages"
#: Unapproved library drafts (MP-DOL: AI drafts, humans own meaning). Searched only
#: when asked (``ov run --drafts``); a checkout-only directory, not installed.
DRAFTS = Path(__file__).resolve().parents[3] / "drafts" / "packages"
BUILTINS = {"abs": 1, "min": 2, "max": 2, "canonical": 1}

# A type: ("q", dims) quantity, ("e", name) entity sort, ("s",) string, ("any",).
Ty = tuple[object, ...]
ANY: Ty = ("any",)
STR: Ty = ("s",)


def q(d: Dims) -> Ty:
    return ("q", d)


def show_ty(t: Ty) -> str:
    if t[0] == "q":
        d = t[1]
        assert isinstance(d, tuple)
        name = next((n for n, x in QUANTITY_TYPES.items() if x == d), None)
        return name or f"quantity [{dims_text(d)}]"
    return {"e": str(t[-1]), "s": "String"}.get(str(t[0]), "Term")


@dataclass
class PredInfo:
    name: str
    params: tuple[A.Param, ...]
    outputs: tuple[str, ...]
    functional: bool
    closed: bool
    pkg: str
    span: Span

    @property
    def n_in(self) -> int:
        return len(self.params)

    @property
    def arity(self) -> int:
        return len(self.params) + len(self.outputs)


@dataclass
class TypeInfo:
    name: str
    parent: str | None
    fields: dict[str, tuple[str, Span]]
    pkg: str


@dataclass
class EntInfo:
    name: str
    type: str
    value: A.Expr | None
    owner: str          # package or scenario name
    span: Span


@dataclass
class ScenarioInfo:
    decl: A.Scenario
    packages: tuple[str, ...]           # used packages and their imports, in load order
    entities: dict[str, EntInfo] = field(default_factory=dict)
    unknowns: dict[str, Ty] = field(default_factory=dict)
    test: str | None = None
    #: `tolerance x`: numeric answers must be enclosed within a relative half-width x
    tolerance: Fraction | None = None


@dataclass
class Env:
    main: A.Module
    modules: dict[str, A.Module] = field(default_factory=dict)        # package -> module
    imports: dict[str, tuple[str, ...]] = field(default_factory=dict)
    types: dict[str, TypeInfo] = field(default_factory=dict)
    preds: dict[str, PredInfo] = field(default_factory=dict)
    funcs: dict[str, tuple[A.FuncDecl, str]] = field(default_factory=dict)
    ents: dict[str, EntInfo] = field(default_factory=dict)
    gens: dict[str, tuple[A.GenDecl, str]] = field(default_factory=dict)
    axioms: list[tuple[str, A.Axiom]] = field(default_factory=list)
    controllers: list[tuple[str, A.Controller]] = field(default_factory=list)
    scenarios: dict[str, ScenarioInfo] = field(default_factory=dict)
    opaque: set[str] = field(default_factory=set)
    diags: list[Diagnostic] = field(default_factory=list)
    class_decls: dict[str, A.FactType] = field(default_factory=dict)
    class_pkgs: dict[str, str] = field(default_factory=dict)
    objects: Classes = field(default_factory=Classes)
    #: imported OVStates: (name, path, the importing file, span)
    states: list[tuple[str, Path, str, Span]] = field(default_factory=list)

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diags if d.warning]

    def sources(self) -> dict[str, str]:
        out = {m.file: m.source for m in self.modules.values()}
        out[self.main.file] = self.main.source
        return out

    def closure(self, pkgs: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        """The packages plus everything they import, dependencies first."""
        seen: list[str] = []

        def visit(p: str) -> None:
            if p in seen or p not in self.modules:
                return
            for d in self.imports.get(p, ()):
                visit(d)
            seen.append(p)
        for p in pkgs:
            visit(p)
        return tuple(seen)

    def ty_of(self, name: str, span: Span | None = None) -> Ty:
        if name in QUANTITY_TYPES:
            return q(QUANTITY_TYPES[name])
        if name in ("Term", "Any"):
            return ANY
        if name == "String":
            return STR
        if name not in self.types and name not in self.opaque and span is not None:
            self.opaque.add(name)
            self.diags.append(Diagnostic(
                "W201", f"type '{name}' is not declared; treated as an opaque entity type",
                span, f"declare it with `type {name}`"))
        return ("e", name)

    def subtype(self, a: str, b: str) -> bool:
        seen = set()
        while a not in seen:
            if a == b:
                return True
            seen.add(a)
            t = self.types.get(a)
            if t is None or t.parent is None:
                return False
            a = t.parent
        return False

    def field_of(self, tname: str, f: str) -> tuple[str, str] | None:
        """(field type, declaring type) for field f of tname, searching parents."""
        t = self.types.get(tname)
        while t is not None:
            if f in t.fields:
                return t.fields[f][0], t.name
            t = self.types.get(t.parent) if t.parent else None
        return None


# ---------------------------------------------------------------- loading


def load(path: str | Path, *, source: str | None = None,
         search: tuple[Path, ...] = ()) -> Env:
    """Parse and check a file and all packages it reaches. Raises OVError."""
    p = Path(path)
    text = p.read_text(encoding="utf-8") if source is None else source
    main = parse(text, str(path))
    env = Env(main)
    roots = (*search, p.parent, STDLIB)
    pkg = main.package
    if pkg is not None:
        env.modules[pkg.name] = main
    _load_deps(env, main, roots)
    for name, mod in list(env.modules.items()):
        _declare(env, mod, name)
    if pkg is None:
        _declare(env, main, "<main>")
    _Checker(env).run()
    errors = [d for d in env.diags if not d.warning]
    if errors:
        raise OVError(env.diags, env.sources())
    return env


#: Parsed packages, keyed by (file, source text). A Module is immutable, so sharing
#: one between loads is safe; an edited file has new text and is parsed again.
_PARSED: dict[tuple[str, str], A.Module] = {}


def _parse_cached(text: str, file: str) -> A.Module:
    key = (file, text)
    mod = _PARSED.get(key)
    if mod is None:
        if len(_PARSED) > 256:
            _PARSED.clear()
        mod = _PARSED[key] = parse(text, file)
    return mod


def _refs(mod: A.Module) -> list[tuple[str, Span]]:
    out = [(i.name, i.span) for i in mod.items if isinstance(i, A.ImportPkg)]
    for sc in _all_scenarios(mod):
        out.extend((u, sc.span) for u in sc.uses)
    return out


def _all_scenarios(mod: A.Module) -> list[A.Scenario]:
    out = [i for i in mod.items if isinstance(i, A.Scenario)]
    for t in (i for i in mod.items if isinstance(i, A.Test)):
        out.extend(s for s in t.stmts if isinstance(s, A.Scenario))
    return out


def _load_deps(env: Env, mod: A.Module, roots: tuple[Path, ...]) -> None:
    owner = mod.package.name if mod.package else "<main>"
    deps = []
    for name, span in _refs(mod):
        if name not in env.modules:
            found = next((r / Path(*name.split(".")).with_suffix(".ov") for r in roots
                          if (r / Path(*name.split(".")).with_suffix(".ov")).is_file()), None)
            if found is None:
                env.diags.append(Diagnostic("E203", f"package '{name}' not found", span,
                                            f"looked for {'/'.join(name.split('.'))}.ov next "
                                            "to the file and in the standard library"))
                continue
            sub = _parse_cached(found.read_text(encoding="utf-8"), str(found))
            if sub.package is None or sub.package.name != name:
                env.diags.append(Diagnostic("E203", f"{found} does not declare `package {name}`",
                                            span))
                continue
            env.modules[name] = sub
            _load_deps(env, sub, roots)
        if name != owner:
            deps.append(name)
    env.imports[owner] = tuple(dict.fromkeys(deps))


def _dup(env: Env, kind: str, name: str, span: Span, table: Mapping[str, object]) -> bool:
    if name in table:
        env.diags.append(Diagnostic("E202", f"{kind} '{name}' is declared more than once", span,
                                    "rename one of them"))
        return True
    return False


def _declare(env: Env, mod: A.Module, pkg: str) -> None:
    for it in mod.items:
        if isinstance(it, A.TypeDecl) and not _dup(env, "type", it.name, it.span, env.types):
            env.types[it.name] = TypeInfo(it.name, it.parent,
                                          {f: (t, s) for f, t, s in it.fields}, pkg)
        elif isinstance(it, A.PredDecl) and not _dup(env, "predicate", it.name, it.span,
                                                     env.preds):
            env.preds[it.name] = PredInfo(it.name, it.params, it.outputs, it.functional,
                                          it.closed, pkg, it.span)
        elif isinstance(it, A.FuncDecl) and not _dup(env, "function", it.name, it.span,
                                                     env.funcs):
            env.funcs[it.name] = (it, pkg)
        elif isinstance(it, A.EntityDecl):
            for n in it.names:
                if not _dup(env, "entity", n, it.span, env.ents):
                    env.ents[n] = EntInfo(n, it.type, it.value, pkg, it.span)
        elif isinstance(it, A.GenDecl) and not _dup(env, "generator", it.name, it.span, env.gens):
            env.gens[it.name] = (it, pkg)
        elif isinstance(it, A.Axiom):
            env.axioms.append((pkg, it))
        elif isinstance(it, A.Controller):
            env.controllers.append((pkg, it))
        elif isinstance(it, A.FactType) and not _dup(env, "class", it.name, it.span,
                                                     {**env.types, **env.class_decls}):
            env.class_decls[it.name] = it
            env.class_pkgs[it.name] = pkg
    # Fields become functional predicates ``Type.field(self) -> T``.
    for t in list(env.types.values()):
        if t.pkg != pkg:
            continue
        for f, (ft, sp) in t.fields.items():
            key = f"{t.name}.{f}"
            env.preds[key] = PredInfo(key, (A.Param("self", t.name, None, sp),), (ft,), True,
                                      False, pkg, sp)


# ---------------------------------------------------------------- checking


@dataclass
class Scope:
    vars: dict[str, Ty] = field(default_factory=dict)
    scenario: ScenarioInfo | None = None
    qvars: dict[str, Ty] | None = None      # set inside queries
    new_unknowns: bool = False              # arrow outputs may introduce unknowns


class _Checker:
    def __init__(self, env: Env) -> None:
        self.env = env
        self.last_find: ObjPlan | None = None

    def err(self, code: str, msg: str, span: Span, hint: str = "") -> Ty:
        self.env.diags.append(Diagnostic(code, msg, span, hint))
        return ANY

    # ------------------------------------------------------------ driver
    def run(self) -> None:
        env = self.env
        for t in env.types.values():
            if t.parent and t.parent not in env.types:
                self.err("E201", f"unknown parent type '{t.parent}'",
                         next(iter(t.fields.values()))[1] if t.fields else env.main.items[0].span)
            for _f, (ft, sp) in t.fields.items():
                env.ty_of(ft, sp)
        for p in env.preds.values():
            for prm in p.params:
                env.ty_of(prm.type, prm.span)
            for o in p.outputs:
                env.ty_of(o, p.span)
        for d, _ in env.funcs.values():
            env.ty_of(d.result, d.span)
            for prm in d.params:
                env.ty_of(prm.type, prm.span)
                if prm.default is not None:
                    self.assign(self.ty(prm.default, Scope()), env.ty_of(prm.type),
                                prm.default.span)
        for e in env.ents.values():
            want = env.ty_of(e.type, e.span)
            if e.value is not None:
                self.assign(self.ty(e.value, Scope()), want, e.value.span)
        for gd, _ in env.gens.values():
            self.gen_decl(gd)
        env.objects = compile_classes(env, env.class_decls)
        for pkg, ax in env.axioms:
            if pkg == "<main>":
                self.err("E206", f"{ax.kind} '{ax.name}' outside a package", ax.span,
                         "axioms and transformations belong in a `package`; "
                         "state scenario knowledge with `fact`")
            self.axiom(ax)
        names = {ax.name for _, ax in env.axioms if ax.kind == "transformation"}
        for _, c in env.controllers:
            sc = Scope({p.name: env.ty_of(p.type, p.span) for p in c.params})
            for n in {n for g in (*c.pipes, *c.branches) for n in g}:
                if n not in names:
                    self.err("E201", f"unknown transformation '{n}' in controller '{c.name}'",
                             c.span)
            for g in c.guards:
                self.lit(g, sc)
        for mod in (*env.modules.values(), *(() if env.main.package else (env.main,))):
            self.module_items(mod)

    def module_items(self, mod: A.Module) -> None:
        pkg = mod.package.name if mod.package else "<main>"
        top: list[A.Query | A.Expect] = []
        for it in mod.items:
            if isinstance(it, A.Scenario):
                self.scenario(it, pkg)
            elif isinstance(it, A.Test):
                scs = [s for s in it.stmts if isinstance(s, A.Scenario)]
                for s in scs:
                    self.scenario(s, pkg, it.name)
                default = self.env.scenarios.get(scs[0].name) if len(scs) == 1 else None
                for st in it.stmts:
                    if isinstance(st, A.Query):
                        self.query(st, default)
                    elif not isinstance(st, (A.Scenario, A.Expect)):
                        self.err("E206", "only scenarios, queries and expectations may appear "
                                 "directly in a test", st.span, "put facts inside a scenario")
            elif isinstance(it, (A.Query, A.Expect)):
                top.append(it)
            elif isinstance(it, A.ImportState):
                path = Path(it.span.file).parent / it.path
                if not path.is_file():
                    self.err("E203", f"OVState file '{it.path}' not found", it.span)
                else:
                    self.env.states.append((it.alias, path, it.span.file, it.span))
            elif isinstance(it, A.Target):
                for c in (*it.must, *it.prefer):
                    for lit in c:
                        self.lit(lit, Scope())
        infos = [s for s in self.env.scenarios.values() if s.decl in _all_scenarios(mod)]
        for t in top:
            if isinstance(t, A.Query):
                self.query(t, infos[0] if len(infos) == 1 else None)

    # ------------------------------------------------------------ declarations
    def gen_decl(self, g: A.GenDecl) -> None:
        env = self.env
        src = g.source
        p = env.preds.get(src.fn) if isinstance(src, A.Call) else None
        if p is None or p.functional or len(p.outputs) != 1 or not p.closed:
            self.err("E404", f"generator '{g.name}' must draw from a closed predicate with one "
                     "set-valued output", g.source.span,
                     "declare e.g. `predicate p(x: T) -> {U} world closed`")
            return
        assert isinstance(src, A.Call)
        sc = Scope({prm.name: env.ty_of(prm.type, prm.span) for prm in g.params})
        if len(src.args) != p.n_in:
            self.err("E205", f"'{p.name}' takes {p.n_in} inputs", src.span)
        for a, prm in zip(src.args, p.params, strict=False):
            self.assign(self.ty(a, sc), env.ty_of(prm.type), a.span)
        if p.outputs[0] != g.yields:
            self.err("E302", f"generator yields {g.yields} but '{p.name}' gives {p.outputs[0]}",
                     g.span)

    def axiom(self, ax: A.Axiom) -> None:
        sc = Scope({p.name: self.env.ty_of(p.type, p.span) for p in ax.params})
        for prm in ax.params:
            if prm.name in self.env.funcs or prm.name in self.env.ents:
                self.err("E202", f"parameter '{prm.name}' shadows a declared name", prm.span,
                         "rename the parameter")
        for lit in (*ax.body, *ax.head):
            self.lit(lit, sc)
        for h in ax.head:
            self.head(h, sc)

    def head(self, h: A.Lit, sc: Scope) -> None:
        if isinstance(h, A.Holds) and isinstance(h.expr, A.Call):
            p = self.env.preds.get(h.expr.fn)
            if p is not None and len(h.expr.args) != p.arity:
                self.err("E205", f"a conclusion must give every argument of '{p.name}' "
                         f"({p.arity})", h.span, f"write `{p.name}(...) = value`")
        elif isinstance(h, A.Not) and isinstance(h.lit, A.Holds):
            self.head(h.lit, sc)
        elif (isinstance(h, A.Cmp) and h.op == "=") or isinstance(h, A.Member):
            return
        elif not isinstance(h, A.Holds):
            self.err("E206", "a conclusion must be an atom, `not` an atom, an equation or "
                     "`x in s`", h.span)

    # ------------------------------------------------------------ scenarios
    def scenario(self, s: A.Scenario, pkg: str, test: str | None = None) -> None:
        env = self.env
        if _dup(env, "scenario", s.name, s.span, env.scenarios):
            return
        uses = list(s.uses)
        base = env.scenarios.get(s.extends) if s.extends else None
        if s.extends and base is None:
            self.err("E201", f"unknown scenario '{s.extends}'", s.span)
        if base is not None:
            uses = [*base.packages, *uses]
        info = ScenarioInfo(s, env.closure(uses), test=test)
        if base is not None:
            info.entities.update(base.entities)
            info.unknowns.update(base.unknowns)
        env.scenarios[s.name] = info
        sc = Scope(scenario=info)
        for st in s.stmts:
            if isinstance(st, A.EntityDecl):
                want = env.ty_of(st.type, st.span)
                for n in st.names:
                    if n in info.entities or n in env.ents:
                        self.err("E202", f"entity '{n}' is declared more than once", st.span)
                    info.entities[n] = EntInfo(n, st.type, st.value, s.name, st.span)
                if st.value is not None:
                    self.assign(self.ty(st.value, sc), want, st.value.span)
            elif isinstance(st, A.GenUse):
                self.gen_use(st, info, sc)
            elif isinstance(st, (A.FactStmt, A.AssumeStmt)):
                sc.new_unknowns = True
                self.lit(st.lit, sc)
                sc.new_unknowns = False
            elif isinstance(st, A.Query):
                self.query(st, info)
            elif isinstance(st, A.Tolerance):
                if not 0 < st.value < 1:
                    self.err("E206", "tolerance is a relative half-width between 0 and 1",
                             st.span, "e.g. `tolerance 0.001` for 0.1 %")
                info.tolerance = st.value

    def gen_use(self, g: A.GenUse, info: ScenarioInfo, sc: Scope) -> None:
        src = g.source
        gen = self.env.gens.get(src.fn) if isinstance(src, A.Call) else None
        if gen is None:
            self.err("E201", "unknown generator", src.span,
                     "a generator is declared with `generator name(...) yields T from ...`")
            return
        assert isinstance(src, A.Call)
        gd = gen[0]
        if len(src.args) != len(gd.params):
            self.err("E205", f"generator '{gd.name}' takes {len(gd.params)} arguments", src.span)
        for a, prm in zip(src.args, gd.params, strict=False):
            self.assign(self.ty(a, sc), self.env.ty_of(prm.type), a.span)
        for n in g.names:
            if n in info.unknowns or n in info.entities or n in self.env.ents:
                self.err("E202", f"'{n}' is already declared", g.span)
            info.unknowns[n] = self.env.ty_of(gd.yields)

    def query(self, qy: A.Query, info: ScenarioInfo | None) -> None:
        if is_object_query(qy.q):
            try:
                plan = plan_query(qy, self.env.objects, self.last_find)
            except ObjFail as e:
                self.env.diags.append(e.d)
                return
            if info is not None and info.tolerance is not None:
                plan.tolerance = info.tolerance
            self.env.objects.plans[qy.span] = plan
            if plan.kind == "find":
                self.last_find = plan
            return
        sc = Scope(scenario=info, qvars={})
        self.okql(qy.q, sc)

    def okql(self, o: A.Okql, sc: Scope) -> None:
        if isinstance(o, A.Prove):
            self.lit(o.lit, sc)
        elif isinstance(o, A.Find):
            for w in o.where:
                self.lit(w, sc)
            unknowns = sc.scenario.unknowns if sc.scenario else {}
            for v in o.vars:
                if not o.where and v.name not in unknowns:
                    self.err("E201", f"?{v.name} names no unknown of the scenario", v.span,
                             "add `WHERE ...` to say what ?" + v.name + " is")
                elif o.where and v.name not in (sc.qvars or {}) and v.name not in unknowns:
                    self.err("E201", f"?{v.name} does not occur in WHERE", v.span)
        elif isinstance(o, A.WhatIf):
            if is_object_query(o.then):
                self.err("E206", "WHAT IF over an object query is not supported", o.span)
            for c in o.changes:
                if isinstance(c, A.Retract):
                    self.lit(c.lit, sc)
            self.okql(o.then, sc)

    # ------------------------------------------------------------ literals
    def lit(self, lit: A.FactLit, sc: Scope) -> None:
        env = self.env
        if isinstance(lit, A.Not):
            self.lit(lit.lit, sc)
        elif isinstance(lit, A.Holds):
            e = lit.expr
            if not isinstance(e, A.Call) or e.fn not in env.preds:
                if isinstance(e, A.Call) and e.fn in env.funcs:
                    self.err("E206", f"'{e.fn}' is a function, not a predicate", e.span,
                             "a statement must be a predicate, a comparison or `x in s`")
                elif isinstance(e, A.Call):
                    self.unknown_name(e.fn, e.span, "predicate")
                else:
                    self.err("E206", "a statement must be a predicate, a comparison or `x in s`",
                             lit.span)
                return
            p = env.preds[e.fn]
            if len(e.args) not in (p.n_in, p.arity):
                self.err("E205", f"'{p.name}' takes {p.n_in} argument(s)"
                         + (f" plus {len(p.outputs)} output(s)" if p.outputs else ""), e.span)
                return
            types = [*(x.type for x in p.params), *p.outputs]
            for a, t in zip(e.args, types, strict=False):
                self.assign(self.ty(a, sc), env.ty_of(t), a.span)
        elif isinstance(lit, A.Cmp) and lit.op == "=" and isinstance(lit.right, A.SetLit) \
                and isinstance(lit.left, A.Call) and lit.left.fn in env.preds:
            # ``p(x) = {a, b}`` for a set-valued p: one statement per member
            p = env.preds[lit.left.fn]
            if p.functional or len(p.outputs) != 1 or len(lit.left.args) != p.n_in:
                self.err("E206", f"`{p.name}(...) = {{...}}` needs a predicate declared "
                         "`-> {T}` with one output", lit.span)
                return
            for a, prm in zip(lit.left.args, p.params, strict=True):
                self.assign(self.ty(a, sc), env.ty_of(prm.type), a.span)
            for item in lit.right.items:
                self.assign(self.ty(item, sc), env.ty_of(p.outputs[0]), item.span)
        elif isinstance(lit, A.Cmp):
            lt = self.ty(lit.left, sc)
            rt = self.ty(lit.right, sc)
            for side, other in ((lit.left, rt), (lit.right, lt)):
                if isinstance(side, A.QVar) and sc.qvars is not None and side.name not in \
                        sc.qvars:
                    sc.qvars[side.name] = other
            if lit.op in ("<", "<=", ">", ">="):
                for ty, side in ((lt, lit.left), (rt, lit.right)):
                    if ty[0] not in ("q", "any"):
                        self.err("E303", f"'{lit.op}' needs quantities, got {show_ty(ty)}",
                                 side.span)
            self.compatible(lt, rt, lit.span)
        elif isinstance(lit, A.Member):
            it = self.ty(lit.item, sc)
            if isinstance(lit.coll, A.Interval):
                self.compatible(it, self.ty(lit.coll.lo, sc), lit.span)
                self.compatible(it, self.ty(lit.coll.hi, sc), lit.span)
                return
            mp = env.preds.get("member")
            if mp is None or mp.arity != 2:
                self.err("E201", "`x in s` needs a predicate `member(s: S, x: T)`", lit.span,
                         "declare `predicate member(s: S, x: T) world closed` in a package")
                return
            self.assign(self.ty(lit.coll, sc), env.ty_of(mp.params[0].type), lit.coll.span)
            self.assign(it, env.ty_of(mp.params[1].type if mp.n_in == 2 else mp.outputs[0]),
                        lit.item.span)
        else:
            self.arrow(lit, sc)

    def arrow(self, lit: A.Arrow, sc: Scope) -> None:
        e = lit.call
        p = self.env.preds.get(e.fn) if isinstance(e, A.Call) else None
        if p is None or not p.outputs or not isinstance(e, A.Call):
            self.err("E206", "`f(x) -> y` needs a predicate with outputs", lit.span,
                     "declare it as `predicate f(x: T) -> {U, U}`")
            return
        for a, prm in zip(e.args, p.params, strict=False):
            self.assign(self.ty(a, sc), self.env.ty_of(prm.type), a.span)
        if len(e.args) != p.n_in:
            self.err("E205", f"'{p.name}' takes {p.n_in} input(s)", e.span)
        outs = lit.out.items if isinstance(lit.out, A.SetLit) else (lit.out,)
        if len(outs) != len(p.outputs) and not (len(p.outputs) == 1 and not p.functional):
            self.err("E205", f"'{p.name}' gives {len(p.outputs)} output(s), got {len(outs)}",
                     lit.out.span)
            return
        for i, o in enumerate(outs):
            want = self.env.ty_of(p.outputs[min(i, len(p.outputs) - 1)])
            info = sc.scenario
            if (sc.new_unknowns and info is not None and isinstance(o, A.Name)
                    and self.resolve(o.name, sc) is None):
                info.unknowns[o.name] = want      # ``ozonolysis(A) -> {C, D}`` introduces C, D
                continue
            self.assign(self.ty(o, sc), want, o.span)

    # ------------------------------------------------------------ expressions
    def resolve(self, name: str, sc: Scope) -> Ty | None:
        env = self.env
        if name in sc.vars:
            return sc.vars[name]
        info = sc.scenario
        if info is not None:
            if name in info.unknowns:
                return info.unknowns[name]
            if name in info.entities:
                return env.ty_of(info.entities[name].type)
        if name in env.ents:
            return env.ty_of(env.ents[name].type)
        return None

    def unknown_name(self, name: str, span: Span, kind: str = "name") -> Ty:
        hint = ""
        if "-" in name and not name[0].isdigit():
            hint = "a hyphen inside a name joins it; write `a - b` (with spaces) to subtract"
        else:
            pool = [*self.env.ents, *self.env.preds, *self.env.funcs]
            close = difflib.get_close_matches(name, pool, n=1)
            if close:
                hint = f"did you mean '{close[0]}'?"
            else:
                hint = "declare it with `entity`, `predicate` or `function`"
        return self.err("E201", f"unknown {kind} '{name}'", span, hint)

    def ty(self, e: A.Expr, sc: Scope) -> Ty:
        if isinstance(e, A.Name):
            t = self.resolve(e.name, sc)
            return t if t is not None else self.unknown_name(e.name, e.span)
        if isinstance(e, A.QVar):
            info = sc.scenario
            if info is not None and e.name in info.unknowns:
                return info.unknowns[e.name]
            if sc.qvars is None:
                return self.err("E206", f"?{e.name} is only allowed in queries", e.span)
            return sc.qvars.setdefault(e.name, ANY)
        if isinstance(e, A.Quantity):
            return q(e.dims)
        if isinstance(e, A.StrLit):
            return STR
        if isinstance(e, (A.UnknownLit, A.SetLit, A.Interval)):
            for x in (e.items if isinstance(e, A.SetLit) else ()):
                self.ty(x, sc)
            return ANY
        if isinstance(e, A.Call):
            return self.call(e, sc)
        if isinstance(e, A.Field):
            return self.field(e, sc)
        if isinstance(e, A.Neg):
            t = self.ty(e.arg, sc)
            return t if t[0] in ("q", "any") else self.err(
                "E303", f"cannot negate {show_ty(t)}", e.span)
        if not isinstance(e, A.BinOp):
            return self.err("E206", "tuples, indexing and patterns belong to classes and object "
                            "queries", e.span, "use them inside a `fact type` or in "
                            "`FIND ... WHERE T{...}`")
        return self.binop(e, sc)

    def call(self, e: A.Call, sc: Scope) -> Ty:
        env = self.env
        if e.fn in BUILTINS:
            if len(e.args) != BUILTINS[e.fn]:
                return self.err("E205", f"'{e.fn}' takes {BUILTINS[e.fn]} argument(s)", e.span)
            ts = [self.ty(a, sc) for a in e.args]
            if e.fn in ("min", "max"):
                self.compatible(ts[0], ts[1], e.span)
            return ts[0]
        if e.fn in env.funcs:
            d = env.funcs[e.fn][0]
            need = sum(1 for p in d.params if p.default is None)
            if not need <= len(e.args) <= len(d.params):
                return self.err("E205", f"'{e.fn}' takes {len(d.params)} argument(s)", e.span)
            for a, prm in zip(e.args, d.params, strict=False):
                self.assign(self.ty(a, sc), env.ty_of(prm.type), a.span)
            return env.ty_of(d.result)
        if e.fn in env.preds:
            p = env.preds[e.fn]
            if not p.functional:
                return self.err("E206", f"predicate '{e.fn}' has no single value", e.span,
                                f"use it as a statement, or declare `-> T` on '{e.fn}'")
            if len(e.args) != p.n_in:
                return self.err("E205", f"'{e.fn}' takes {p.n_in} argument(s)", e.span)
            for a, prm in zip(e.args, p.params, strict=True):
                self.assign(self.ty(a, sc), env.ty_of(prm.type), a.span)
            return env.ty_of(p.outputs[0])
        if e.fn in env.gens:
            return self.err("E206", f"generator '{e.fn}' can only be used in "
                            "`generator X from ...`", e.span)
        return self.unknown_name(e.fn, e.span, "function or predicate")

    def field(self, e: A.Field, sc: Scope) -> Ty:
        env = self.env
        if isinstance(e.obj, A.Name) and self.resolve(e.obj.name, sc) is None \
                and e.obj.name in env.scenarios:
            other = env.scenarios[e.obj.name]     # ``t.block``: an entity of scenario t
            if e.name in other.entities:
                return env.ty_of(other.entities[e.name].type)
            if e.name in other.unknowns:
                return other.unknowns[e.name]
            return self.err("E201", f"scenario '{other.decl.name}' has no entity '{e.name}'",
                            e.span)
        t = self.ty(e.obj, sc)
        if t[0] != "e":
            if t[0] != "any":
                self.err("E204", f"{show_ty(t)} has no fields", e.span)
            return ANY
        f = env.field_of(str(t[1]), e.name)
        if f is None:
            names = sorted(env.types[str(t[1])].fields) if str(t[1]) in env.types else []
            return self.err("E204", f"type {t[1]} has no field '{e.name}'", e.span,
                            f"fields: {', '.join(names)}" if names else "")
        return env.ty_of(f[0])

    def binop(self, e: A.BinOp, sc: Scope) -> Ty:
        lt, rt = self.ty(e.left, sc), self.ty(e.right, sc)
        for t, s in ((lt, e.left), (rt, e.right)):
            if t[0] not in ("q", "any"):
                return self.err("E303", f"'{e.op}' needs quantities, got {show_ty(t)}", s.span)
        if lt == ANY or rt == ANY:
            return ANY
        ld, rd = lt[1], rt[1]
        assert isinstance(ld, tuple) and isinstance(rd, tuple)
        if e.op in "+-":
            if ld != rd:
                return self.err("E301", f"cannot {'add' if e.op == '+' else 'subtract'} "
                                f"{show_ty(lt)} and {show_ty(rt)}", e.span,
                                "both sides of + and - need the same dimension")
            return lt
        if e.op in "*/":
            k = 1 if e.op == "*" else -1
            out = dict(ld)
            for n, x in rd:
                out[n] = out.get(n, Fraction(0)) + k * x
            return q(make_dims(out))
        # ^ : the exponent must be a dimensionless constant
        if rd:
            return self.err("E301", "an exponent must be dimensionless", e.right.span)
        if not ld:
            return lt
        if not isinstance(e.right, A.Quantity):
            return self.err("E301", "a quantity with units can only be raised to a constant",
                            e.right.span)
        return q(make_dims({n: x * e.right.value for n, x in ld}))

    # ------------------------------------------------------------ compatibility
    def assign(self, got: Ty, want: Ty, span: Span) -> None:
        if ANY in (got, want):
            return
        if got[0] == "q" and want[0] == "q":
            if got != want:
                self.err("E301", f"expected {show_ty(want)}, got {show_ty(got)}", span,
                         "check the units")
            return
        if got[0] == "e" and want[0] == "e" and self.env.subtype(str(got[1]), str(want[1])):
            return
        if got != want:
            self.err("E302", f"expected {show_ty(want)}, got {show_ty(got)}", span)

    def compatible(self, a: Ty, b: Ty, span: Span) -> None:
        if ANY in (a, b):
            return
        if a[0] == "q" and b[0] == "q":
            if a != b:
                self.err("E301", f"cannot compare {show_ty(a)} with {show_ty(b)}", span,
                         "both sides need the same dimension")
            return
        if a[0] == b[0] == "e" and (self.env.subtype(str(a[1]), str(b[1]))
                                     or self.env.subtype(str(b[1]), str(a[1]))):
            return
        if a != b:
            self.err("E302", f"cannot compare {show_ty(a)} with {show_ty(b)}", span)
