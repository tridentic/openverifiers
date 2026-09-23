"""DomainIR -> v2 Grammar. The ONLY place IR meets runtime objects.

Compiled outputs are ordinary v2 constructs — Registry dispatch, provenance
tiers, the proof/discharge runner, owner/frame reification — with zero
runtime changes besides the judged tier + Quantity.frame added to facts.py.

OOP model, as compiled:

  * `type X = entity` / `type X extends Y` become nominal PhysicalObject
    subclasses (polymorphism: a role typed `PointObject` accepts any
    subtype instance via isinstance).
  * `object` declarations become instances of those classes.
  * quantity subtypes become unit-dimension typed roles: a bound input
    fact must be a Quantity with the declared dimension (scale-free check).
  * `framed` quantity subtypes require a reference frame on the fact; a
    relation whose output type is framed inherits the common input frame.
  * typed transform/judge inputs auto-generate guards (kind/unit/owner/
    framed) BEFORE any explicit guard, all engine-evaluated.

The precondition for a transform with guards is generated FROM the guard
records and the declared types (never authored as Python).
"""
from __future__ import annotations

import re

import sympy as sp

from openverifiers.facts import (Fact, Quantity, ActionFact, ExpressionFact,
                                 as_number)
from openverifiers.model import Transformation, ParamTransformation, InputSpec
from openverifiers.objects import PhysicalObject
from openverifiers.units import Unit
from openverifiers.v2 import Grammar

from .builtins import make_builtin
from .judged import JudgedTransformation
from .units import from_record, resolve_token

_ENTITY_CLASSES: dict[str, type] = {"entity": PhysicalObject}


def entity_class(name: str, base: str) -> type:
    if name in _ENTITY_CLASSES:
        return _ENTITY_CLASSES[name]
    parent = _ENTITY_CLASSES.get(base) or PhysicalObject
    cls = type(name, (parent,), {"__module__": "kerscript.types"})
    _ENTITY_CLASSES[name] = cls
    return cls


# ---------------------------------------------------------------------------
# relation engine (v2 Primitive semantics: all-bound consistency check
# returns the bound output; one-free numeric solve with positive-root
# preference; two-or-more free / chained -> ExpressionFact)
# ---------------------------------------------------------------------------
class RelationPrimitive(ParamTransformation):
    def __init__(self, *, name: str, vars_: tuple[str, ...], out: str,
                 expr: sp.Expr, units: dict[str, "Unit"], doc: str = "",
                 params: tuple[str, ...] = (), out_framed: bool = False):
        self.rule = {"name": name, "vars": vars_, "out": out,
                     "units": units, "doc": doc}
        self.out_framed = out_framed
        super().__init__(name=name, doc=doc,
                         param_names=("axis", "theta") + params,
                         inputs=tuple(InputSpec(v, required=False)
                                      for v in vars_))
        self._syms = {v: sp.Symbol(v) for v in vars_}
        self._expr = expr
        self.out = out

    @staticmethod
    def _num(fact: Fact, axis: int = 0) -> float | None:
        if fact is None:
            return None
        value = fact.value
        if value is None:
            return None
        if hasattr(value, "component"):          # Vector3
            comp = [value.x, value.y, value.z][axis]
            from openverifiers.units import to_canonical
            return float(to_canonical(comp, fact.unit))
        return as_number(value, getattr(fact, "unit", None))

    def _common_frame(self, inputs: dict) -> "PhysicalObject | None":
        frames = {id(f.frame): f.frame for f in inputs.values()
                  if getattr(f, "frame", None) is not None}
        if len(frames) == 1:
            return next(iter(frames.values()))
        return None

    def apply(self, inputs: dict, params: dict | None = None) -> Fact:
        params = params or {}
        axis = int(params.get("axis", 0) or 0)
        bound: dict[str, float] = {}
        chained: dict[sp.Symbol, sp.Expr] = {}
        for v in self.rule["vars"]:
            if v in inputs:
                f = inputs[v]
                if isinstance(f, ExpressionFact):
                    chained[self._syms[v]] = sp.sympify(f.expression)
                    continue
                num = self._num(f, axis)
                if num is None:
                    raise ValueError(f"input {v!r} has no numeric value")
                bound[v] = num
            elif v in params:
                bound[v] = float(params[v])

        subs = {self._syms[v]: b for v, b in bound.items()}
        subs.update(chained)
        out = self.rule["out"]
        out_unit = self.rule["units"][out]
        remaining = [v for v in self.rule["vars"]
                     if v not in bound and self._syms[v] not in chained]

        if len(remaining) == 0:
            err = abs(float(sp.N(self._expr.subs(subs))))
            scale = max(1.0, abs(float(sp.N(subs.get(self._syms[out],
                                                     1.0)))))
            if err > 1e-6 * scale:
                raise ValueError(
                    f"relation {self.rule['name']} not satisfied by the "
                    f"bound values (residual {err:g})")
            return Quantity(value=float(bound[out]), unit=out_unit,
                            frame=self._common_frame(inputs)
                            if self.out_framed else None)

        if len(remaining) >= 2 or chained:
            expr = sp.solve(sp.Eq(self._expr, 0), self._syms[out])[0]
            expr = sp.simplify(expr.subs(subs))
            free = tuple(sorted({str(sv) for sv in expr.free_symbols}))
            return ExpressionFact(id="?", expression=str(expr),
                                  variables=free, unit=out_unit,
                                  source=self.rule["name"])

        target = self._syms[remaining[0]]
        roots = sp.solve(sp.Eq(self._expr.subs(subs), 0), target)
        vals = []
        for root in roots:
            try:
                n = complex(sp.N(root))
            except Exception:
                continue
            if abs(n.imag) > 1e-9:
                continue
            vals.append(n.real)
        if not vals:
            raise ValueError(f"no real solution for {remaining[0]!r} in "
                             f"{self.rule['name']}")
        pos = [v for v in vals if v > 0]
        val = pos[0] if pos else vals[0]
        return Quantity(value=float(val),
                        unit=self.rule["units"][remaining[0]],
                        frame=self._common_frame(inputs)
                        if self.out_framed else None)


_CONST_OR_FN = {"pi", "e", "sqrt", "sin", "cos", "tan", "exp", "log", "ln",
                "Rational", "oo", "abs", "floor", "ceiling"}


def _sympify(expr_text: str) -> sp.Expr:
    text = expr_text.strip().replace("^", "**")
    if "=" in text:
        lhs, _, rhs = text.partition("=")
        text = f"{lhs.strip()} - ({rhs.strip()})"
    # sympy's global namespace shadows bare identifiers (Q, E, I, O, N, S...)
    # with singletons; map every identifier to a fresh Symbol unless it is a
    # function/constant we want resolved globally.
    locals_ = {name: sp.Symbol(name)
               for name in re.findall(r"[A-Za-z_]\w*", text)
               if name not in _CONST_OR_FN}
    expr = sp.sympify(text, locals=locals_)
    # portable constants: bare names resolve to sympy constants
    return expr.subs({sp.Symbol("pi"): sp.pi, sp.Symbol("e"): sp.E})


# ---------------------------------------------------------------------------
# type system: resolved type records + compiled role guards
# ---------------------------------------------------------------------------
def _resolve_type(types: dict, name: str) -> dict | None:
    return types.get(name)


def _role_guard(rec: dict) -> callable:
    base = rec["base"]

    def check(fact: Fact, role: str) -> str | None:
        if base == "quantity":
            if not isinstance(fact, Quantity):
                return f"{role} must be a Quantity, got " \
                       f"{type(fact).__name__}"
            if rec.get("framed") and getattr(fact, "frame", None) is None:
                return f"{role} is typed framed but carries no reference frame"
        elif base == "action":
            if not isinstance(fact, ActionFact):
                return f"{role} must be an ActionFact, got " \
                       f"{type(fact).__name__}"
            kind = rec.get("kind")
            if kind and getattr(fact, "kind", None) != kind:
                return f"{role} kind {fact.kind!r} does not match " \
                       f"declared {kind!r}"
        return None
    return check


def _compile_guards(guards: list[dict], resolver=None) -> callable:
    def precond(inputs: dict) -> str | None:
        for g in guards:
            args = g["args"]
            op = g["op"]
            if op == "same_owner":
                a, b = (inputs.get(x) for x in args)
                if a is None or b is None:
                    return f"guard same_owner({args[0]},{args[1]}): " \
                           f"missing input"
                if getattr(a, "owner", None) != getattr(b, "owner", None):
                    return (f"guard same_owner({args[0]},{args[1]}): "
                            f"owners differ")
            elif op == "frame_eq":
                a, b = (inputs.get(x) for x in args)
                if a is None or b is None:
                    return f"guard frame_eq({args[0]},{args[1]}): " \
                           f"missing input"
                fa, fb = getattr(a, "frame", None), getattr(b, "frame", None)
                if fa != fb:
                    return (f"guard frame_eq({args[0]},{args[1]}): "
                            f"frames differ")
            elif op == "kind":
                role, kind = args
                f = inputs.get(role)
                if f is None:
                    return f"guard kind({role},{kind}): missing input"
                if kind == "quantity" and not isinstance(f, Quantity):
                    return f"guard kind({role},quantity): {role} is " \
                           f"{type(f).__name__}"
                if kind == "action" and not isinstance(f, ActionFact):
                    return f"guard kind({role},action): {role} is " \
                           f"{type(f).__name__}"
            elif op == "unit":
                role, token = args
                f = inputs.get(role)
                if f is None:
                    return f"guard unit({role},{token}): missing input"
                want = (resolver or resolve_token)(token)
                if not isinstance(f, Quantity) or \
                        f.unit.dimension != want.dimension:
                    return f"guard unit({role},{token}): unit mismatch"
            elif op == "framed":
                role = args[0]
                f = inputs.get(role)
                if f is None:
                    return f"guard framed({role}): missing input"
                if getattr(f, "frame", None) is None:
                    return f"guard framed({role}): carries no frame"
            elif op == "owner_of_type":
                role, tname = args
                f = inputs.get(role)
                if f is None:
                    return f"guard owner_of_type({role},{tname}): " \
                           f"missing input"
                owner = getattr(f, "owner", None)
                cls = _ENTITY_CLASSES.get(tname, PhysicalObject)
                if not isinstance(owner, cls):
                    return (f"guard owner_of_type({role},{tname}): owner "
                            f"is not an instance of {tname}")
            elif op == "positive":
                role = args[0]
                f = inputs.get(role)
                if f is None:
                    return f"guard positive({role}): missing input"
                num = as_number(getattr(f, "value", None),
                                getattr(f, "unit", None))
                if num is None or num <= 0:
                    return f"guard positive({role}): non-positive"
        return None
    return precond


# ---------------------------------------------------------------------------
# compiler
# ---------------------------------------------------------------------------
def compile_ir(doc: dict) -> Grammar:
    if doc.get("kind") != "domain" or doc.get("ir_version") != 1:
        raise ValueError(f"not a DomainIR v1 document: {doc.get('kind')!r}")
    name = doc["name"]
    types: dict = doc.get("types", {})
    doc_units: dict = doc.get("units", {})

    def resolver(token: str) -> "Unit":
        rec = doc_units.get(token)
        if rec is not None:
            return from_record(rec)
        return resolve_token(token)

    # entity classes (nominal OOP: PhysicalObject subclasses, lenient order)
    for tname, rec in sorted(types.items()):
        if rec["base"] == "entity":
            entity_class(tname, "entity")
            rec["__name__"] = tname

    # object instances
    objects: dict[str, PhysicalObject] = {}
    for o in doc.get("objects", []):
        cls = _ENTITY_CLASSES.get(o["type"], PhysicalObject)
        objects[o["id"]] = cls(id=o["id"])

    transforms: dict[str, Transformation] = {}
    rel_by_name = {rel["name"]: rel for rel in doc["relations"]}
    for rel in doc["relations"]:
        units = {v: resolver(tok) for v, tok in rel["units"].items()}
        out_rec = types.get(rel.get("types", {}).get(rel["out"], ""), {})
        transforms[rel["name"]] = RelationPrimitive(
            name=rel["name"], vars_=tuple(units), out=rel["out"],
            expr=_sympify(rel["expr"]), units=units,
            params=tuple(rel.get("param") or ()),
            out_framed=bool(out_rec.get("framed")),
            doc=rel.get("doc", ""))
        # input type guards -> precondition (quantity dimension / framed)
        var_types = rel.get("types") or {}
        guards = []
        for var, tname in var_types.items():
            rec = _resolve_type(types, tname)
            if rec and rec["base"] == "quantity":
                guards.append({"op": "unit",
                               "args": [var, rec["unit"] or "dimless"]})
                if rec.get("framed"):
                    guards.append({"op": "framed", "args": [var]})
        if guards:
            p = _compile_guards(guards, resolver)
            transforms[rel["name"]]._pre = p  # noqa: SLF001

    for tr in doc["transforms"]:
        explicit = tr.get("guard") or []
        if tr.get("relation"):
            src = rel_by_name[tr["relation"]]
            units = {v: resolver(tok) for v, tok in src["units"].items()}
            base = RelationPrimitive(
                name=tr["name"], vars_=tuple(units), out=src["out"],
                expr=_sympify(src["expr"]), units=units,
                params=tuple(src.get("param") or ()),
                out_framed=bool(types.get(src.get("types", {}).get(
                    src["out"], ""), {}).get("framed")),
                doc=tr.get("doc", ""))
            if explicit:
                base._pre = _compile_guards(explicit, resolver)  # noqa: SLF001
            transforms[tr["name"]] = base
            continue
        base = make_builtin(tr["builtin"])
        auto = _auto_guards(tr.get("input") or [], types)
        if auto or explicit:
            orig = base.precond
            gpre = _compile_guards(auto + explicit, resolver)
            def precond(inputs: dict, _orig=orig, _gpre=gpre) -> str | None:
                reason = _gpre(inputs)
                return reason or _orig(inputs)
            base._pre = precond  # noqa: SLF001 — compiler owns its objects
        transforms[tr["name"]] = base

    for jg in doc["judgements"]:
        inputs = tuple(InputSpec(i["role"]) for i in jg["input"])
        jt = JudgedTransformation(
            jg["name"], model=jg["model"], inputs=inputs,
            schema=jg.get("schema", {}), doc=jg.get("doc", ""))
        auto = _auto_guards(jg["input"], types)
        if auto:
            jt._pre = _compile_guards(auto, resolver)  # noqa: SLF001
        transforms[jg["name"]] = jt

    facts: dict[str, Fact] = {}
    for f in doc.get("facts", []):
        owner = objects.get(f.get("owner")) if f.get("owner") else None
        frame = objects.get(f.get("frame")) if f.get("frame") else None
        if f["kind"] == "quantity":
            facts[f["id"]] = Quantity(
                id=f["id"], value=f["value"], unit=resolver(f.get("unit")),
                owner=owner, frame=frame, source=f.get("source", ""))
        else:
            facts[f["id"]] = ActionFact(
                id=f["id"], kind=f["kind_name"], value=f["value"],
                of=f.get("of"), owner=owner, source=f.get("source", ""))

    exclusive = tuple(frozenset(pair) for pair in doc.get("exclusive", []))
    return Grammar(name=name, transformations=transforms, facts=facts,
                   exclusive=exclusive, doc=doc.get("doc", ""))


def _auto_guards(typed_inputs: list[dict], types: dict) -> list[dict]:
    guards = []
    for item in typed_inputs:
        tname = item["type"]
        rec = _resolve_type(types, tname)
        if rec is None:
            continue
        if rec["base"] == "quantity":
            guards.append({"op": "unit", "args": [item["role"], tname]})
            if rec.get("framed"):
                guards.append({"op": "framed", "args": [item["role"]]})
        elif rec["base"] == "action":
            guards.append({"op": "kind", "args": [item["role"],
                                                  rec.get("kind") or
                                                  "action"]})
        elif rec["base"] == "entity":
            guards.append({"op": "owner_of_type",
                           "args": [item["role"], tname]})
            _ENTITY_CLASSES.setdefault(tname, PhysicalObject)
    return guards


def compile_text(text: str) -> Grammar:
    from .domain_parser import parse_domain
    return compile_ir(parse_domain(text))


def load_grammar(path: str) -> Grammar:
    from .domain_parser import load_domain
    return compile_ir(load_domain(path))