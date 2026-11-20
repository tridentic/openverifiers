"""Answer object-layer queries and check classes, with every model re-checked.

The pattern for every answer (brief §3.7):

1. solve: expand the invariants and ask z3 (untrusted);
2. re-check: substitute the model and decide every invariant with the exact
   evaluator in ``raw.formula`` (trusted). A model that fails is never
   reported; the answer becomes UNKNOWN(plugin_unknown);
3. for UNIQUE and COUNT: block the solutions found and solve again. Unsat
   ends the search. Unsat cannot be checked by substitution, so it is
   confirmed by a second, fresh solver run, and the trace says so.

Each step is recorded in ``ObjAnswer.steps``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction

from ..raw.formula import ClassDef, Unsupported, failing, holds
from ..raw.terms import Compound, Num, Str, Term, Var, substitute
from .compile import Classes, ObjPlan, conj, generic, size_invariants
from .expand import (
    CF,
    FALSE,
    Expander,
    Poly,
    SSeq,
    and_,
    atom,
    cases,
    expand,
    not_,
    or_,
    seq_items,
)
from .solve import Result, solve

DEFAULT_LIMIT = {"find": 16, "unique": 2, "count": 64}


@dataclass
class ObjAnswer:
    title: str
    verdict: str                                   # PROVEN | REFUTED | UNKNOWN | INCONSISTENT
    reason: str = ""
    bindings: list[dict[str, Term]] = field(default_factory=list)
    names: tuple[str, ...] = ()                    # failing invariants / conflict set
    witness: dict[str, Term] | None = None         # an instance (counterexample, model)
    count: int | None = None
    complete: bool = True
    steps: list[str] = field(default_factory=list)
    plan: ObjPlan | None = None
    expect_ok: bool | None = None
    expect_msg: str = ""


@dataclass
class Settings:
    symmetry: bool = True
    timeout_ms: int = 20_000


def _vars(t: Term, out: dict[str, None]) -> None:
    if isinstance(t, Var):
        out[t.name] = None
    elif isinstance(t, Compound):
        for a in t.args:
            _vars(a, out)


def _ground(props: Mapping[str, Term], model: Mapping[str, Fraction]) -> dict[str, Term]:
    s = {k: Num(v) for k, v in model.items()}
    return {k: substitute(v, s) for k, v in props.items()}


def show(t: Term) -> str:
    if isinstance(t, Num):
        v = t.value
        return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"
    if isinstance(t, Compound) and t.functor == "f.tuple":
        return "(" + ", ".join(show(a) for a in t.args) + ")"
    if isinstance(t, Compound) and t.functor in ("f.set", "f.list"):
        o, c = ("{", "}") if t.functor == "f.set" else ("[", "]")
        return o + ", ".join(show(a) for a in t.args) + c
    if isinstance(t, Str):
        return t.value
    return str(t)


def _instance(props: Mapping[str, Term]) -> str:
    return ", ".join(f"{k} = {show(v)}" for k, v in props.items())


class _Run:
    def __init__(self, st: Settings, steps: list[str]) -> None:
        self.st, self.steps = st, steps

    def solve(self, what: str, cons: list[CF], names: list[str]) -> Result:
        r = solve(cons, names, self.st.timeout_ms)
        self.steps.append(f"solve [z3] {what}: {r.status}" + (f" ({r.reason})" if r.reason else ""))
        return r

    def confirm_unsat(self, what: str, cons: list[CF], names: list[str]) -> bool:
        r = solve(cons, names, self.st.timeout_ms)
        self.steps.append(f"re-solve [z3, fresh solver] {what}: {r.status}")
        return r.status == "unsat"

    def recheck(self, cls: ClassDef, props: Mapping[str, Term]) -> tuple[str, ...] | None:
        try:
            bad = failing(cls, props)
        except Unsupported as e:
            self.steps.append(f"re-check [checker] {_instance(props)}: cannot decide ({e})")
            return None
        self.steps.append(f"re-check [checker] {_instance(props)}: "
                          + ("every invariant holds" if not bad else "fails " + ", ".join(bad)))
        return bad

    def core(self, cls: ClassDef, props: Mapping[str, Term], names: list[str],
             fixed: tuple[str, ...] = ()) -> tuple[str, ...]:
        """A minimal set of invariants with no common instance (deletion-based).

        ``fixed`` invariants stay in: a generic instance's collection sizes come from
        them, so the instance already assumes them."""
        keep = list(cls.invariants)
        for inv in list(keep):
            if inv[0] in fixed:
                continue
            trial = [x for x in keep if x is not inv]
            if trial and solve([_expand(trial, props, self.st)], names,
                               self.st.timeout_ms).status == "unsat":
                keep = trial
        ok = self.confirm_unsat("the core alone", [_expand(keep, props, self.st)], names)
        return tuple(n for n, _ in keep) if ok else ()


def _expand(invs: list[tuple[str, Term]] | tuple[tuple[str, Term], ...],
            props: Mapping[str, Term], st: Settings) -> CF:
    return expand(conj([f for _, f in invs]), props, st.symmetry)


# ---------------------------------------------------------------- queries


def answer(plan: ObjPlan, st: Settings | None = None) -> ObjAnswer:
    st = st or Settings()
    ans = ObjAnswer(plan.query.text, "UNKNOWN", plan=plan)
    r = _Run(st, ans.steps)
    try:
        if plan.kind == "check":
            bad = r.recheck(plan.cls, plan.props)
            if bad is None:
                ans.reason = "plugin_unknown"
            else:
                ans.verdict, ans.names = ("REFUTED", bad) if bad else ("PROVEN", ())
            return ans
        if plan.kind == "counterexample":
            assert plan.theorem is not None
            v, why, wit, names = theorem(plan.cls, plan.theorem, r, ans.steps,
                                         plan.note or plan.props)
            ans.witness, ans.names = wit, names
            if v == "REFUTED":
                ans.verdict = "PROVEN"           # a counterexample exists, and it was checked
            elif v == "PROVEN":
                ans.verdict = "REFUTED"          # no instance violates the theorem
            else:
                ans.reason = why
            return ans
        return _search(plan, r, ans)
    except Unsupported as e:
        ans.steps.append(f"cannot expand: {e}")
        ans.reason = "plugin_unknown"
        return ans


def _search(plan: ObjPlan, r: _Run, ans: ObjAnswer) -> ObjAnswer:
    limit = plan.limit or DEFAULT_LIMIT[plan.kind]
    names: dict[str, None] = {}
    for v in plan.props.values():
        _vars(v, names)
    base = _expand(plan.cls.invariants, plan.props, r.st)
    blocks: list[CF] = []
    while True:
        what = f"invariants of {plan.cls.name}" + (f" minus {len(blocks)} found" if blocks
                                                   else "")
        res = r.solve(what, [base, *blocks], list(names))
        if res.status == "unknown":
            ans.reason, ans.complete = res.reason, False
            break
        if res.status == "unsat":
            if not r.confirm_unsat(what, [base, *blocks], list(names)):
                ans.reason, ans.complete = "plugin_unknown", False
            break
        assert res.model is not None
        g = _ground(plan.props, res.model)
        bad = r.recheck(plan.cls, g)
        if bad is None or bad:
            ans.steps.append("the solver's model is rejected")
            ans.reason, ans.complete = "plugin_unknown", False
            break
        model = {k: Num(v) for k, v in res.model.items()}
        binding: dict[str, Term] = {}
        for q, coords in plan.unknowns.items():
            vals = tuple(model[c.name] for c in coords)
            binding[q] = Compound("f.tuple", vals) if plan.is_tuple[q] else vals[0]
        ans.bindings.append(binding)
        if len(ans.bindings) >= limit:
            more = r.solve("for more solutions", [base, *blocks, _block(plan, binding)],
                           list(names))
            ans.complete = more.status == "unsat"
            if more.status == "sat":
                ans.reason = "budget"
            break
        blocks.append(_block(plan, binding))
        r.steps.append("block " + ", ".join(f"?{q} = {show(v)}" for q, v in binding.items()))
    return _verdict(plan, r, ans, list(names))


def _block(plan: ObjPlan, binding: Mapping[str, Term]) -> CF:
    parts = []
    for q, coords in plan.unknowns.items():
        v = binding[q]
        vals = v.args if isinstance(v, Compound) else (v,)
        for c, x in zip(coords, vals, strict=True):
            assert isinstance(x, Num)
            parts.append(atom("!=", Poly.var(c.name) - Poly.const(x.value)))
    return or_(parts)


def _verdict(plan: ObjPlan, r: _Run, ans: ObjAnswer, names: list[str]) -> ObjAnswer:
    n = len(ans.bindings)
    if ans.reason == "plugin_unknown" and not (plan.kind == "unique" and n >= 2):
        ans.verdict = "UNKNOWN"
        return ans
    if plan.kind == "count":
        if ans.complete:
            ans.verdict, ans.count = "PROVEN", n
        else:
            ans.verdict, ans.reason = "UNKNOWN", ans.reason or "budget"
        return ans
    if plan.kind == "unique":
        if n >= 2:
            ans.verdict, ans.reason = "REFUTED", ""
        elif n == 1 and ans.complete:
            ans.verdict = "PROVEN"
        elif n == 0 and ans.complete:
            ans.verdict = "REFUTED"
            ans.names = r.core(plan.cls, plan.props, names)
        else:
            ans.verdict = "UNKNOWN"
        return ans
    if n:
        ans.verdict = "PROVEN"
    elif ans.complete:
        ans.verdict = "REFUTED"
        ans.names = r.core(plan.cls, plan.props, names)
    else:
        ans.verdict = "UNKNOWN"
    return ans


# ---------------------------------------------------------------- classes


def _items(t: Term) -> tuple[Term, ...]:
    return t.args if isinstance(t, Compound) else ()


def _wlog(f: Term, gen: Mapping[str, Term]) -> tuple[str, str, Term] | None:
    """For ``none v in cycles(p): body`` over a generic set p: (v, p, body)."""
    if not (isinstance(f, Compound) and f.functor == "f.not"):
        return None
    ex = f.args[0]
    if not (isinstance(ex, Compound) and ex.functor == "f.exists" and isinstance(ex.args[0], Str)):
        return None
    coll = ex.args[1]
    if not (isinstance(coll, Compound) and coll.functor in ("f.cycles", "f.orderings")):
        return None
    src = coll.args[0]
    if not (isinstance(src, Compound) and src.functor == "f.p" and isinstance(src.args[0], Str)):
        return None
    prop = src.args[0].value
    val = gen.get(prop)
    if not (isinstance(val, Compound) and val.functor == "f.set"):
        return None
    return ex.args[0].value, prop, ex.args[2]


def theorem(cls: ClassDef, th: tuple[str, Term], r: _Run, steps: list[str],
            gen: Mapping[str, Term] | str
            ) -> tuple[str, str, dict[str, Term] | None, tuple[str, ...]]:
    """(PROVEN | REFUTED | UNKNOWN, reason, counterexample, ())."""
    if isinstance(gen, str):
        steps.append(f"no bounded instance: {gen}")
        return "UNKNOWN", "budget", None, ()
    names: dict[str, None] = {}
    for v in gen.values():
        _vars(v, names)
    inv = conj([f for _, f in cls.invariants])
    st = r.st
    wlog = _wlog(th[1], gen) if st.symmetry else None
    parts = []
    for p, cond in cases(gen, st.symmetry):
        ex = Expander(p, st.symmetry)
        holds_inv = ex.formula(inv)
        if holds_inv == FALSE:
            continue
        if wlog is not None and len(_items(p[wlog[1]])) == len(_items(gen[wlog[1]])):
            # The vertices are fresh, interchangeable unknowns and these are all distinct,
            # so a counterexample's ordering can be taken to be the listed order.
            var, _, body = wlog
            ex.env[var] = SSeq("list", seq_items(ex.value(p[wlog[1]])))
            bad = ex.formula(body)
        else:
            bad = not_(ex.formula(th[1]))
        parts.append(and_([cond, holds_inv, bad]))
    if wlog is not None:
        steps.append(f"symmetry: the counterexample's ordering of {wlog[1]} is fixed (its "
                     "elements are interchangeable unknowns)")
    cons = or_(parts)
    what = f"invariants of {cls.name} and not {th[0]}"
    res = r.solve(what, [cons], list(names))
    if res.status == "unsat":
        if r.confirm_unsat(what, [cons], list(names)):
            return "PROVEN", "", None, ()
        return "UNKNOWN", "plugin_unknown", None, ()
    if res.status == "unknown":
        return "UNKNOWN", res.reason, None, ()
    assert res.model is not None
    g = _ground(gen, res.model)
    failed = r.recheck(cls, g)
    try:
        violated = failed == () and not holds(th[1], g)
    except Unsupported:
        violated = False
    steps.append(f"re-check [checker] {th[0]} on it: " + ("fails" if violated else "holds"))
    if violated:
        return "REFUTED", "", g, ()
    return "UNKNOWN", "plugin_unknown", None, ()


def check_classes(classes: Classes, only: set[str] | None = None,
                  st: Settings | None = None) -> list[ObjAnswer]:
    """`ov check` for classes: consistency of the invariants, then every theorem."""
    st = st or Settings()
    out = []
    proven: dict[str, Term] = {}
    for name, cls in classes.defs.items():
        if only is not None and name not in only:
            continue
        try:
            gen = generic(cls, classes.prop_types[name], classes.records)
        except Unsupported as e:
            gen = str(e)
        ans = ObjAnswer(f"class {name} is consistent", "UNKNOWN")
        r = _Run(st, ans.steps)
        if isinstance(gen, str):
            ans.steps.append(f"no bounded instance: {gen}")
            ans.reason = "budget"
        else:
            out_cls = _consistency(cls, gen, r, ans)
            ans = out_cls
        out.append(ans)
        for th in cls.theorems:
            ta = ObjAnswer(f"theorem {th[0]}", "UNKNOWN")
            same = [n for n in proven if n.split(".")[0] in classes.ancestors[name]
                    and proven[n] == th[1]]
            if same:
                # Every invariant of an ancestor is an invariant here (the class is a subset),
                # so a theorem the ancestor proved, word for word, holds here too.
                ta.steps.append(f"inherited: {same[0]} states the same formula and is proven; "
                                f"{name} includes every invariant of "
                                f"{same[0].split('.')[0]}")
                ta.verdict = "PROVEN"
                proven[th[0]] = th[1]
                out.append(ta)
                continue
            v, why, wit, _ = theorem(cls, th, _Run(st, ta.steps), ta.steps, gen)
            if v == "PROVEN":
                proven[th[0]] = th[1]
            ta.verdict, ta.reason, ta.witness = v, why, wit
            out.append(ta)
    return out


def _consistency(cls: ClassDef, gen: dict[str, Term], r: _Run, ans: ObjAnswer) -> ObjAnswer:
    names: dict[str, None] = {}
    for v in gen.values():
        _vars(v, names)
    try:
        cons = _expand(cls.invariants, gen, r.st)
    except Unsupported as e:
        ans.steps.append(f"cannot expand: {e}")
        ans.reason = "plugin_unknown"
        return ans
    res = r.solve(f"invariants of {cls.name}", [cons], list(names))
    if res.status == "sat" and res.model is not None:
        g = _ground(gen, res.model)
        if r.recheck(cls, g) == ():
            ans.verdict, ans.witness = "PROVEN", g
        else:
            ans.reason = "plugin_unknown"
    elif res.status == "unsat":
        core = r.core(cls, gen, list(names), size_invariants(cls))
        if core:
            ans.verdict, ans.names = "INCONSISTENT", core
        else:
            ans.reason = "plugin_unknown"
    else:
        ans.reason = res.reason
    return ans


__all__ = ["FALSE", "ObjAnswer", "Settings", "answer", "check_classes", "show"]
