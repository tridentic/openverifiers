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
    translation_invariant,
)
from .solve import Result, small_scope, solve

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
    #: What the verdict rests on, like Lean's `#print axioms`: "kernel" (the exact
    #: evaluator re-checked an instance) and/or "z3_unsat" (an unsat answer that only
    #: the solver vouches for). Empty for UNKNOWN.
    trust_base: frozenset[str] = frozenset()
    kind: str = ""                                 # find unique count check counterexample
                                                   # consistency theorem


@dataclass
class Settings:
    symmetry: bool = True
    timeout_ms: int = 20_000
    #: Verdicts resting on an unchecked solver unsat become UNKNOWN(plugin_unknown).
    strict: bool = False


KERNEL, Z3_UNSAT = "kernel", "z3_unsat"


def settle(ans: ObjAnswer, st: Settings) -> ObjAnswer:
    """Record the trust base of a finished answer, then apply --strict."""
    v, k = ans.verdict, ans.kind
    base: set[str] = set()
    if v == "UNKNOWN":
        pass
    elif k in ("check", "consistency") and v == "PROVEN":
        base = {KERNEL}
    elif k in ("theorem", "counterexample"):
        base = {KERNEL} if v == "REFUTED" else {Z3_UNSAT}
    elif k == "consistency":                       # INCONSISTENT: the invariants are unsat
        base = {Z3_UNSAT}
    elif k in ("find", "unique"):
        base = {KERNEL} if ans.bindings else set()
        if (v == "PROVEN" and k == "unique") or not ans.bindings:
            base.add(Z3_UNSAT)                     # no other / no solution: solver unsat
    elif k == "count":
        base = {KERNEL, Z3_UNSAT} if ans.bindings else {Z3_UNSAT}
    else:
        base = {KERNEL}
    ans.trust_base = frozenset(base)
    if st.strict and k == "find" and v == "PROVEN" and ans.complete:
        ans.complete = False                       # "no more solutions" is solver unsat
        ans.steps.append("strict: completeness of the list rests on z3 unsat; not claimed")
    elif st.strict and Z3_UNSAT in base:
        ans.steps.append(f"strict: {v} rests on an unchecked z3 unsat, so UNKNOWN")
        ans.verdict, ans.reason, ans.trust_base = "UNKNOWN", "plugin_unknown", frozenset()
    return ans


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

    def solve(self, what: str, cons: list[CF], names: list[str], *, seek: bool = False
              ) -> Result:
        r = solve(cons, names, self.st.timeout_ms, seek=seek)
        self.steps.append(f"solve [{r.via}] {what}: {r.status}"
                          + (f" ({r.reason})" if r.reason else ""))
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
    return settle(_answer(plan, st), st)


def _answer(plan: ObjPlan, st: Settings) -> ObjAnswer:
    ans = ObjAnswer(plan.query.text, "UNKNOWN", plan=plan, kind=plan.kind)
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
                                         plan.note or plan.props, seek=True)
            # The verdict is the theorem's: REFUTED with the checked counterexample,
            # PROVEN when its negation is unsat, UNKNOWN otherwise.
            ans.witness, ans.names, ans.verdict, ans.reason = wit, names, v, why
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
        res = r.solve(what, [base, *blocks], list(names), seek=True)
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
                           list(names), seek=True)
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


def _coordinate_groups(gen: Mapping[str, Term]) -> list[list[str]]:
    """Variables of the generic instance's points, grouped by coordinate (all x, all y)."""
    groups: dict[tuple[int, int], list[str]] = {}

    def walk(t: Term) -> None:
        if isinstance(t, Compound) and t.functor == "f.tuple" and t.args and all(
                isinstance(a, Var) for a in t.args):
            for j, a in enumerate(t.args):
                assert isinstance(a, Var)
                groups.setdefault((len(t.args), j), []).append(a.name)
        elif isinstance(t, Compound):
            for a in t.args:
                walk(a)
    for v in gen.values():
        walk(v)
    return [g for _, g in sorted(groups.items())]


def _pin(cons: list[CF], gen: Mapping[str, Term], steps: list[str]) -> list[CF]:
    """Translation symmetry: pin one point to 0 in each coordinate that every constraint
    is invariant under shifting. Checked exactly on the polynomials, so it loses no model."""
    pins = []
    for g in _coordinate_groups(gen):
        if len(g) > 1 and translation_invariant(cons, set(g)):
            pins.append(atom("=", Poly.var(g[0])))
            steps.append(f"symmetry: every constraint is invariant under shifting "
                         f"{', '.join(g)} together, so {g[0]} = 0")
    return [*cons, *pins]


def _implied(inv: Term, coll: Term, order: SSeq, props: Mapping[str, Term], bad: CF,
             st: Settings) -> bool:
    if not (isinstance(inv, Compound) and inv.functor == "f.exists" and inv.args[1] == coll
            and isinstance(inv.args[0], Str)):
        return False
    ex = Expander(props, st.symmetry)
    ex.env[inv.args[0].value] = order
    need = ex.formula(inv.args[2])
    return _conj_parts(need) <= _conj_parts(bad)


def _conj_parts(f: CF) -> set[object]:
    if f[0] == "and":
        parts = f[1]
        assert isinstance(parts, (frozenset, tuple))
        return set(parts)
    return {f}


def _wlog(f: Term, gen: Mapping[str, Term]) -> tuple[str, str, Term, Term] | None:
    """A theorem ``none v in cycles(p): body`` or ``all v in cycles(p): body`` over a
    generic set p: (v, p, what a counterexample's ordering v must satisfy)."""
    if isinstance(f, Compound) and f.functor == "f.not":
        ex = f.args[0]
        if not (isinstance(ex, Compound) and ex.functor == "f.exists"):
            return None
        bad: Term | None = ex.args[2] if len(ex.args) == 3 else None
    elif isinstance(f, Compound) and f.functor == "f.forall":
        ex = f
        bad = Compound("f.not", (f.args[2],))
    else:
        return None
    if bad is None or not isinstance(ex.args[0], Str):
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
    return ex.args[0].value, prop, bad, coll


def theorem(cls: ClassDef, th: tuple[str, Term], r: _Run, steps: list[str],
            gen: Mapping[str, Term] | str, *, seek: bool = False
            ) -> tuple[str, str, dict[str, Term] | None, tuple[str, ...]]:
    """(PROVEN | REFUTED | UNKNOWN, reason, counterexample, ()).

    ``seek`` (COUNTEREXAMPLE): try small integer points before z3. Otherwise (a
    theorem check) z3 goes first, and the small-scope search runs only if z3 can
    neither prove nor refute it: never on a proof that succeeds."""
    if isinstance(gen, str):
        steps.append(f"no bounded instance: {gen}")
        return "UNKNOWN", "budget", None, ()
    names: dict[str, None] = {}
    for v in gen.values():
        _vars(v, names)
    st = r.st
    wlog = _wlog(th[1], gen) if st.symmetry else None
    full, alone = [], []
    dropped: set[str] = set()
    for p, cond in cases(gen, st.symmetry):
        ex = Expander(p, st.symmetry)
        invs = [(n, ex.formula(f)) for n, f in cls.invariants]
        if any(c == FALSE for _, c in invs):
            continue
        if wlog is not None and len(_items(p[wlog[1]])) == len(_items(gen[wlog[1]])):
            # The vertices are fresh, interchangeable unknowns and these are all distinct,
            # so a counterexample's ordering can be taken to be the listed order.
            var, _, body, coll = wlog
            order = SSeq("list", seq_items(ex.value(p[wlog[1]])))
            ex.env[var] = order
            bad = ex.formula(body)
            # An invariant `exists w in <same collection>: B` whose B, at that ordering, is
            # already among the counterexample's conditions is implied: leave it out.
            kept = []
            for (n, f), (_, c) in zip(cls.invariants, invs, strict=True):
                if _implied(f, coll, order, p, bad, st):
                    dropped.add(n)
                else:
                    kept.append(c)
            invs_cf = kept
        else:
            bad = not_(ex.formula(th[1]))
            invs_cf = [c for _, c in invs]
        full.append(and_([cond, *invs_cf, bad]))
        alone.append(and_([cond, bad]))
    if wlog is not None:
        steps.append(f"symmetry: the counterexample's ordering of {wlog[1]} is fixed (its "
                     "elements are interchangeable unknowns)")
    if dropped:
        steps.append("implied by the counterexample's conditions, so left out: "
                     + ", ".join(sorted(dropped)))
    # Cheap first: if the theorem's negation is unsat even without the invariants,
    # the theorem holds for every instance (a stronger, sound result).
    quick = Settings(st.symmetry, max(1, st.timeout_ms // 10))
    what0 = f"not {th[0]} (without the invariants)"
    alone_c = _pin([or_(alone)], gen, steps)
    res0 = _Run(quick, steps).solve(what0, alone_c, list(names))
    if res0.status == "unsat" and r.confirm_unsat(what0, alone_c, list(names)):
        return "PROVEN", "", None, ()
    cons = _pin([or_(full)], gen, steps)
    what = f"invariants of {cls.name} and not {th[0]}"
    res = r.solve(what, cons, list(names), seek=seek)
    if res.status == "unknown" and not seek:
        fallback = small_scope(cons, list(names))
        steps.append(f"solve [{fallback.via}] {what}: {fallback.status}")
        if fallback.status == "sat":
            res = fallback
    if res.status == "unsat":
        if r.confirm_unsat(what, cons, list(names)):
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
        ans = ObjAnswer(f"class {name} is consistent", "UNKNOWN", kind="consistency")
        r = _Run(st, ans.steps)
        if isinstance(gen, str):
            ans.steps.append(f"no bounded instance: {gen}")
            ans.reason = "budget"
        else:
            ans = _consistency(cls, gen, r, ans)
        out.append(settle(ans, st))
        for th in cls.theorems:
            ta = ObjAnswer(f"theorem {th[0]}", "UNKNOWN", kind="theorem")
            same = [n for n in proven if n.split(".")[0] in classes.ancestors[name]
                    and proven[n] == th[1]]
            if same:
                # Every invariant of an ancestor is an invariant here (the class is a subset),
                # so a theorem the ancestor proved, word for word, holds here too.
                ta.steps.append(f"inherited: {same[0]} states the same formula and is proven; "
                                f"{name} includes every invariant of "
                                f"{same[0].split('.')[0]}")
                ta.verdict = "PROVEN"
            else:
                v, why, wit, _ = theorem(cls, th, _Run(st, ta.steps), ta.steps, gen)
                ta.verdict, ta.reason, ta.witness = v, why, wit
            settle(ta, st)
            if ta.verdict == "PROVEN":
                proven[th[0]] = th[1]
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
    res = r.solve(f"invariants of {cls.name}", _pin([cons], gen, ans.steps), list(names),
                  seek=True)
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
