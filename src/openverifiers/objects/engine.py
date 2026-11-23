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

import itertools
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction

from ..lang.units import show_quantity
from ..raw.canon import term_to_json
from ..raw.certificate import Certificate, check
from ..raw.formula import DEG, ClassDef, Unsupported, _Eval, failing, holds
from ..raw.interval import Iv
from ..raw.numeric import failing_numeric
from ..raw.qpi import QPi
from ..raw.qpi import from_term as qpi_from
from ..raw.qpi import to_term as qpi_term
from ..raw.surd import Surd
from ..raw.terms import Compound, Num, Str, Term, Var, substitute
from .certify import comparisons, find
from .compile import Classes, ObjPlan, conj, generic, size_invariants
from .expand import (
    CF,
    FALSE,
    RECIPS,
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
from .qpi_lift import lift
from .solve import Result, enumerate_models, small_scope, solve, variables

#: COUNT enumerates at most this many solutions (a deterministic budget, D-027);
#: past it the answer is UNKNOWN(budget), never a truncated count.
DEFAULT_LIMIT = {"find": 16, "unique": 2, "count": 4096}


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
    #: Solver-side reductions the unsat answers were computed under (see
    #: docs/SEMANTICS.md §7). Listed in trust_base as ``red:<name>`` when the verdict
    #: rests on z3_unsat; a kernel-checked instance needs none of them.
    reductions: frozenset[str] = frozenset()
    #: proven theorems this proof used as hypotheses (a theorem check that z3 could not
    #: settle from the invariants alone is retried with them)
    lemmas: tuple[str, ...] = ()
    #: the verdict is proven by a certificate the trusted checker (raw/certificate.py)
    #: verified: its trust base is {kernel}, and --strict keeps it
    certified: bool = False
    #: JSON records behind kernel verdicts (accepted models, certificates), re-checked
    #: from JSON by the trusted checker/objects.py (Condition B)
    records: list[dict[str, object]] = field(default_factory=list)
    #: the hypotheses (invariants, laws, lemmas) a certificate used: the theorem's exact
    #: statement closure (OV-Paper); empty when not certified
    used_hyps: tuple[str, ...] = ()
    kind: str = ""                                 # find unique count check counterexample
                                                   # consistency theorem


@dataclass
class Settings:
    symmetry: bool = True
    timeout_ms: int = 20_000
    #: Verdicts resting on an unchecked solver unsat become UNKNOWN(plugin_unknown).
    strict: bool = False
    #: The theorem-proving reductions (fix_order, no_invariants, drop_implied,
    #: translate, inherit). Off: every unsat is computed on the full problem.
    reductions: bool = True
    #: Also load draft packages from drafts/packages/: library lines an AI drafted
    #: that the founder has not approved (MP-DOL). Never under --strict. Results that use
    #: them are provisional (FileResult.draft_packages lists them).
    drafts: bool = False


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
        base = {KERNEL} if v == "REFUTED" or ans.certified else {Z3_UNSAT}
    elif k == "consistency":                       # INCONSISTENT: the invariants are unsat
        base = {Z3_UNSAT}
    elif k in ("find", "unique"):
        base = {KERNEL} if ans.bindings else set()
        if (v == "PROVEN" and k == "unique" and not ans.certified) or not ans.bindings:
            base.add(Z3_UNSAT)                     # no other / no solution: solver unsat
    elif k == "count":
        base = {KERNEL, Z3_UNSAT} if ans.bindings else {Z3_UNSAT}
    else:
        base = {KERNEL}
    if Z3_UNSAT in base and not ans.certified:
        base |= {f"red:{x}" for x in ans.reductions}
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


def term_of(v: Fraction | Surd | QPi) -> Term:
    """A solver value as a term: a rational, f.surd(k1, c1, k2, c2, ...) for
    c1 sqrt(k1) + c2 sqrt(k2) + ..., or f.qpi for an element of Q(pi) (exact; the
    evaluator re-checks it)."""
    if isinstance(v, Fraction):
        return Num(v)
    if isinstance(v, QPi):
        return qpi_term(v)
    r = v.rational()
    if r is not None:
        return Num(r)
    return Compound("f.surd", tuple(x for k, c in v.terms
                                    for x in (Num(Fraction(k)), Num(c))))


def _ground(props: Mapping[str, Term], model: Mapping[str, Fraction | Surd | QPi]
            ) -> dict[str, Term]:
    s = {k: term_of(v) for k, v in model.items()}
    return {k: substitute(v, s) for k, v in props.items()}


def show(t: Term) -> str:
    if isinstance(t, Num) and t.dims and t.dims != DEG:
        return show_quantity(t.value, t.dims)
    if isinstance(t, Num):
        v = t.value
        return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"
    if isinstance(t, Compound) and t.functor == "f.iv" and len(t.args) == 2:
        lo, hi = (x for x in t.args if isinstance(x, Num))
        mid, half = float((lo.value + hi.value) / 2), float((hi.value - lo.value) / 2)
        unit = show_quantity(Fraction(1), lo.dims).removeprefix("1") if lo.dims else ""
        return f"{mid:.10g}{unit} (± {half:.1e})"
    if isinstance(t, Compound) and t.functor == "f.surd":
        nums = [x.value for x in t.args if isinstance(x, Num)]
        parts = []
        for rad, coef in zip(nums[0::2], nums[1::2], strict=True):
            cs = show(Num(coef))
            lead = "" if coef == 1 else "-" if coef == -1 else cs
            parts.append(cs if rad == 1 else f"{lead}√{rad}")
        return " + ".join(parts).replace("+ -", "- ")
    if isinstance(t, Compound) and t.functor == "f.qpi":
        k = int(t.args[0].value) if isinstance(t.args[0], Num) else 0
        coefs = [x.value for x in t.args[1:] if isinstance(x, Num)]

        def in_pi(c: list[Fraction]) -> str:
            ts = [show(Num(x)) + ("" if i == 0 else "π" if i == 1 else f"π^{i}")
                  for i, x in enumerate(c) if x]
            return " + ".join(ts).replace("+ -", "- ").replace("1π", "π") or "0"
        top, bottom = in_pi(coefs[:k]), in_pi(coefs[k:])
        return top if bottom == "1" else f"({top})/({bottom})"
    if isinstance(t, Compound) and t.functor == "f.tuple":
        return "(" + ", ".join(show(a) for a in t.args) + ")"
    if isinstance(t, Compound) and t.functor in ("f.set", "f.list"):
        o, c = ("{", "}") if t.functor == "f.set" else ("[", "]")
        return o + ", ".join(show(a) for a in t.args) + c
    if isinstance(t, Str):
        return t.value
    return str(t)


def _poly_text(p: Poly) -> str:
    """A solver polynomial for a step line (variable names as the solver has them)."""
    parts = []
    for mono, c in p.terms:
        vs = "*".join(v if k == 1 else f"{v}^{k}" for v, k in mono)
        parts.append(vs if c == 1 and vs else f"{show(Num(c))}*{vs}" if vs else show(Num(c)))
    return " + ".join(parts) or "0"


def _instance(props: Mapping[str, Term]) -> str:
    return ", ".join(f"{k} = {show(v)}" for k, v in props.items())


class _Run:
    def __init__(self, st: Settings, steps: list[str],
                 records: list[dict[str, object]] | None = None) -> None:
        self.st, self.steps = st, steps
        #: JSON records of accepted models, re-checked by checker/objects.py
        self.records = records if records is not None else []

    def solve(self, what: str, cons: list[CF], names: list[str], *, seek: bool = False
              ) -> Result:
        divs = sorted({v for c in cons for v in variables(c) if v in RECIPS})
        note = "side condition (division, multiplied through): " + ", ".join(
            f"{_poly_text(RECIPS[v])} != 0" for v in divs)
        if divs and note not in self.steps:
            self.steps.append(note)
        r = solve(cons, names, self.st.timeout_ms, seek=seek)
        self.steps.append(f"solve [{r.via}] {what}: {r.status}"
                          + (f" ({r.reason})" if r.reason else ""))
        return r

    def confirm_unsat(self, what: str, cons: list[CF], names: list[str]) -> bool:
        r = solve(cons, names, self.st.timeout_ms)
        self.steps.append(f"re-solve [z3, fresh solver] {what}: {r.status}")
        return r.status == "unsat"

    def recheck_model(self, cls: ClassDef, props: Mapping[str, Term],
                      model: Mapping[str, Fraction | Surd]
                      ) -> tuple[dict[str, Term], tuple[str, ...] | None,
                                 Mapping[str, Fraction | Surd | QPi]]:
        """Ground the model and re-check it. If the check fails and the class mentions
        pi, try the untrusted lift into Q(pi) (objects/qpi_lift.py) and re-check that."""
        g = _ground(props, model)
        bad = self.recheck(cls, g)
        if bad == ():
            return g, bad, model
        lifted = lift(cls, props, model)
        if lifted is None:
            return g, bad, model
        self.steps.append("lift the model into Q(pi) [untrusted search]")
        g2 = _ground(props, lifted)
        bad2 = self.recheck(cls, g2)
        return (g2, bad2, lifted) if bad2 == () else (g, bad, model)

    def recheck(self, cls: ClassDef, props: Mapping[str, Term]) -> tuple[str, ...] | None:
        try:
            bad = failing(cls, props)
        except Unsupported as e:
            self.steps.append(f"re-check [checker] {_instance(props)}: cannot decide ({e})")
            return None
        self.steps.append(f"re-check [checker] {_instance(props)}: "
                          + ("every invariant holds" if not bad else "fails " + ", ".join(bad)))
        if not bad:
            self.records.append({"kind": "model", "class": cls.name,
                                 "props": {k: term_to_json(v) for k, v in props.items()}})
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
    r = _Run(st, ans.steps, ans.records)
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
            used: set[str] = set()
            try:
                v, why, wit, names = theorem(plan.cls, plan.theorem, r, ans.steps,
                                             plan.note or plan.props, seek=True, used=used)
            except Unsupported as e:
                ans.steps.append(f"cannot expand: {e}")
                small = _small_naturals(plan.cls, plan.theorem, plan.note or plan.props,
                                        ans.steps)
                v, why, wit, names = ("REFUTED", "", small, ()) if small is not None else \
                    ("UNKNOWN", "plugin_unknown", None, ())
            ans.reductions = frozenset(used)
            # The verdict is the theorem's: REFUTED with the checked counterexample,
            # PROVEN when its negation is unsat, UNKNOWN otherwise.
            ans.witness, ans.names, ans.verdict, ans.reason = wit, names, v, why
            certify(ans, plan.cls, plan.theorem, {})
            return ans
        if _transcendental(plan.cls) and plan.kind in ("find", "unique") \
                and _numeric(plan, r, ans):
            return ans
        return _search(plan, r, ans)
    except Unsupported as e:
        ans.steps.append(f"cannot expand: {e}")
        ans.reason = "plugin_unknown"
        return ans


def _numeric(plan: ObjPlan, r: _Run, ans: ObjAnswer) -> bool:
    """Numeric mode, for classes exact solving cannot settle (exp, ln, pi):
    each unknown property gets its value from its definition `p = E`, in invariant
    order, either exact or a rigorous interval. raw.numeric re-checks the whole
    instance, and enforces one definition per interval property, used in order.
    True when it answered."""
    props = dict(plan.props)
    unknown = {k for k, v in props.items() if isinstance(v, Var)}
    if not unknown or any(isinstance(v, Compound) and _has_var(v) for v in props.values()):
        return False
    for _, f in plan.cls.invariants:
        if not (isinstance(f, Compound) and f.functor == "f.cmp" and f.args[0] == Str("=")):
            continue
        lhs = f.args[1]
        key = lhs.args[0].value if isinstance(lhs, Compound) and lhs.functor == "f.p" \
            and isinstance(lhs.args[0], Str) else None
        if key not in unknown:
            continue
        try:
            v = _Eval({k: x for k, x in props.items() if k not in unknown}).expr(f.args[2])
        except Unsupported:
            continue
        if isinstance(v, Surd):
            props[key] = term_of(v)
        elif isinstance(v, Iv):
            props[key] = Compound("f.iv", (Num(v.lo), Num(v.hi)))
        elif isinstance(v, Num):
            props[key] = v
        else:
            continue
        unknown.discard(key)
    if unknown:
        return False
    try:
        bad = failing_numeric(plan.cls, props)
    except Unsupported as e:
        r.steps.append(f"numeric re-check [checker]: cannot decide ({e})")
        return False
    r.steps.append("numeric [checker]: each unknown from its definition, enclosed exactly or "
                   "by a rigorous interval: " + ("every invariant holds" if not bad
                                                 else "fails " + ", ".join(bad)))
    if bad:
        ans.verdict, ans.names = "REFUTED", bad
        return True
    binding: dict[str, Term] = {}
    for q, coords in plan.unknowns.items():
        name = next(k for k, v in plan.props.items() if v == coords[0])
        val = props[name]
        dims = plan.unknown_dims.get(q, ())
        if isinstance(val, Compound) and val.functor == "f.iv" and dims:
            val = Compound("f.iv", tuple(Num(x.value, dims) for x in val.args
                                         if isinstance(x, Num)))
        elif isinstance(val, Num) and dims:
            val = Num(val.value, dims)
        binding[q] = val
        if isinstance(val, Compound) and val.functor == "f.iv":
            lo, hi = (x.value for x in val.args if isinstance(x, Num))
            tol = plan.tolerance if plan.tolerance is not None else Fraction(1, 10**12)
            if (hi - lo) / 2 > tol * max(abs(lo), abs(hi)):
                r.steps.append(f"?{q}: the enclosure is wider than the tolerance {tol}")
                ans.reason, ans.complete = "precision", False
                return True
    ans.bindings, ans.verdict, ans.complete = [binding], "PROVEN", True
    return True


def _transcendental(cls: ClassDef) -> bool:
    def go(t: Term) -> bool:
        return isinstance(t, Compound) and (t.functor in ("f.exp", "f.ln", "f.pi")
                                            or any(go(a) for a in t.args))
    return any(go(f) for _, f in cls.invariants)


def _has_var(t: Term) -> bool:
    return isinstance(t, Var) or (isinstance(t, Compound) and any(_has_var(a) for a in t.args))


def _search(plan: ObjPlan, r: _Run, ans: ObjAnswer) -> ObjAnswer:
    limit = plan.limit or DEFAULT_LIMIT[plan.kind]
    names: dict[str, None] = {}
    for v in plan.props.values():
        _vars(v, names)
    base = _expand(plan.cls.invariants, plan.props, r.st)
    if plan.kind == "count" and _count_fast(plan, r, ans, base, list(names), limit):
        return _verdict(plan, r, ans, list(names))
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
        _, bad, exact = r.recheck_model(plan.cls, plan.props, res.model)
        if bad is None or bad:
            ans.steps.append("the solver's model is rejected")
            ans.reason, ans.complete = "plugin_unknown", False
            break
        model = {k: term_of(v) for k, v in exact.items()}
        binding: dict[str, Term] = {}
        for q, coords in plan.unknowns.items():
            vals = tuple(model[c.name] for c in coords)
            if q in plan.unknown_dims:                 # for display and expectations only
                vals = tuple(Num(x.value, plan.unknown_dims[q]) if isinstance(x, Num) else x
                             for x in vals)
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


def _count_fast(plan: ObjPlan, r: _Run, ans: ObjAnswer, base: CF, names: list[str],
                limit: int) -> bool:
    """COUNT by incremental enumeration (one solver, a blocking clause per model).
    Every model is re-checked by the kernel; the count's completeness is the
    solver's final unsat, as for the general search. False: use the general path."""
    block = [c.name for coords in plan.unknowns.values() for c in coords]
    got = enumerate_models([base], names, block, limit, r.st.timeout_ms)
    if got is None:
        return False
    models, complete = got
    r.steps.append(f"enumerate [z3, incremental] invariants of {plan.cls.name}: "
                   f"{len(models)} model(s)" + ("; then unsat" if complete else
                                                  "; budget reached"))
    for model in models:
        _, bad, exact = r.recheck_model(plan.cls, plan.props, model)
        if bad is None or bad:
            ans.steps.append("the solver's model is rejected")
            ans.reason, ans.complete = "plugin_unknown", False
            return True
        vals = {k: term_of(v) for k, v in exact.items()}
        ans.bindings.append({q: (Compound("f.tuple", tuple(vals[c.name] for c in coords))
                                 if plan.is_tuple[q] else vals[coords[0].name])
                             for q, coords in plan.unknowns.items()})
    ans.complete = complete
    if not complete:
        ans.reason = "budget"
    return True


def _block(plan: ObjPlan, binding: Mapping[str, Term]) -> CF:
    parts = []
    for q, coords in plan.unknowns.items():
        v = binding[q]
        vals = v.args if isinstance(v, Compound) and v.functor == "f.tuple" else (v,)
        for c, x in zip(coords, vals, strict=True):
            if isinstance(x, Num):
                parts.append(atom("!=", Poly.var(c.name) - Poly.const(x.value)))
                continue
            if isinstance(x, Compound) and x.functor == "f.qpi":   # c q(pi) - p(pi) != 0
                qv = qpi_from(x.args)
                at = []
                for cs in (qv.num, qv.den):
                    acc, pw = Poly.const(Fraction(0)), Poly.const(Fraction(1))
                    for k in cs:
                        acc, pw = acc + pw * Poly.const(k), pw * Poly.var("PI")
                    at.append(acc)
                parts.append(atom("!=", Poly.var(c.name) * at[1] - at[0]))
                continue
            # x = a + b sqrt(k): exclude it alone, not its conjugate a - b sqrt(k).
            assert isinstance(x, Compound) and x.functor == "f.surd"
            nums = [y.value for y in x.args if isinstance(y, Num)]
            terms = dict(zip(nums[0::2], nums[1::2], strict=True))
            a = terms.pop(Fraction(1), Fraction(0))
            assert len(terms) == 1, "a model value has one square root"
            (k, b), = terms.items()
            p = Poly.var(c.name) - Poly.const(a)
            parts.append(atom("!=", p * p - Poly.const(b * b * k)))
            parts.append(atom("<=" if b > 0 else ">=", p))
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
            certify_unique(plan, ans)
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


def _pin(cons: list[CF], gen: Mapping[str, Term], steps: list[str], st: Settings,
         used: set[str] | None = None) -> list[CF]:
    """Translation symmetry: pin one point to 0 in each coordinate that every constraint
    is invariant under shifting. Checked exactly on the polynomials, so it loses no model."""
    if not st.reductions:
        return cons
    pins = []
    for g in _coordinate_groups(gen):
        if len(g) > 1 and translation_invariant(cons, set(g)):
            pins.append(atom("=", Poly.var(g[0])))
            steps.append(f"symmetry: every constraint is invariant under shifting "
                         f"{', '.join(g)} together, so {g[0]} = 0")
    if pins and used is not None:
        used.add("translate")
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
            gen: Mapping[str, Term] | str, *, seek: bool = False,
            used: set[str] | None = None
            ) -> tuple[str, str, dict[str, Term] | None, tuple[str, ...]]:
    """(PROVEN | REFUTED | UNKNOWN, reason, counterexample, ()).

    ``seek`` (COUNTEREXAMPLE): try small integer points before z3. Otherwise (a
    theorem check) z3 goes first, and the small-scope search runs only if z3 can
    neither prove nor refute it: never on a proof that succeeds.

    ``used`` receives the reductions the returned verdict's unsat rests on."""
    used = set() if used is None else used
    if isinstance(gen, str):
        steps.append(f"no bounded instance: {gen}")
        return "UNKNOWN", "budget", None, ()
    names: dict[str, None] = {}
    for v in gen.values():
        _vars(v, names)
    st = r.st
    wlog = _wlog(th[1], gen) if st.symmetry and st.reductions else None
    fixed = False
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
            fixed = True
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
    if fixed and wlog is not None:
        steps.append(f"symmetry: the counterexample's ordering of {wlog[1]} is fixed (its "
                     "elements are interchangeable unknowns)")
    if dropped:
        steps.append("implied by the counterexample's conditions, so left out: "
                     + ", ".join(sorted(dropped)))
    # Cheap first: if the theorem's negation is unsat even without the invariants,
    # the theorem holds for every instance (a stronger, sound result).
    common = {"fix_order"} if fixed else set()
    if st.reductions:
        quick = Settings(st.symmetry, max(1, st.timeout_ms // 10))
        what0 = f"not {th[0]} (without the invariants)"
        u0 = {*common, "no_invariants"}
        alone_c = _pin([or_(alone)], gen, steps, st, u0)
        res0 = _Run(quick, steps).solve(what0, alone_c, list(names))
        if res0.status == "unsat" and r.confirm_unsat(what0, alone_c, list(names)):
            used |= u0
            return "PROVEN", "", None, ()
    used |= common | ({"drop_implied"} if dropped else set())
    cons = _pin([or_(full)], gen, steps, st, used)
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
    g, failed, _ = r.recheck_model(cls, gen, res.model)
    try:
        violated = failed == () and not holds(th[1], g)
        said = "fails" if violated else "holds"
    except Unsupported as e:
        violated, said = False, f"cannot decide ({e})"
    steps.append(f"re-check [checker] {th[0]} on it: {said}")
    if violated:
        return "REFUTED", "", g, ()
    return "UNKNOWN", "plugin_unknown", None, ()


def certify(ans: ObjAnswer, cls: ClassDef, th: tuple[str, Term],
            lemmas: Mapping[str, Term]) -> None:
    """Try to prove the theorem by a certificate (untrusted search in objects.certify,
    checked by the trusted raw.certificate). On success the verdict is PROVEN with
    trust {kernel}. A counterexample the evaluator confirmed is never overridden: a
    conflict means a bug, so it is reported, not resolved."""
    goals = comparisons(th[1], th[0])
    if not goals or len(goals) != _conjuncts_of(th[1]):
        return                                   # a part is not a plain comparison
    hyps: dict[str, Term] = {}
    for n, inv in cls.invariants:
        hyps.update(comparisons(inv, n))
    for n, f in lemmas.items():
        hyps.update(comparisons(f, f"lemma:{n}"))
    certs = []
    for _, g in goals:
        c = find(g, hyps)
        if c is None or not check(g, hyps, c):
            return
        certs.append(c)
    if ans.verdict == "REFUTED":
        ans.steps.append("BUG: a certificate proves a theorem the evaluator refuted")
        ans.verdict, ans.reason = "UNKNOWN", "plugin_unknown"
        return
    used = sorted({n for c in certs for n, _ in c.coeffs} | {n for c in certs
                                                              for n in c.factors})
    if any(c.induction for c in certs):
        ans.steps.append("certificate [kernel: raw/certificate.py]: by induction on the "
                         "natural number: F(0) = 0 and F(n) - F(n-1) = E(n), exact normal form")
    else:
        ans.steps.append("certificate [kernel: raw/certificate.py]: exact normal form of "
                         "multiplier * (lhs - rhs) - ideal part - squares is 0"
                         + (f"; hypotheses used: {', '.join(used)}" if used else
                            "; an identity"))
    for k, c in enumerate(certs):
        ans.records.append({"kind": "certificate", "class": cls.name, "theorem": th[0],
                            "part": k, "cert": cert_json(c), "lemmas": _lemmas_of(c)})
    ans.verdict, ans.reason, ans.certified = "PROVEN", "", True
    ans.used_hyps = tuple(sorted({n.split("#")[0].removeprefix("lemma:") for n in used}))


def cert_json(c: Certificate) -> dict[str, object]:
    t = term_to_json
    return {"factors": list(c.factors), "coeffs": [[n, t(x)] for n, x in c.coeffs],
            "squares": [[str(w), t(x)] for w, x in c.squares],
            "constants": [t(x) for x in c.constants],
            "wsquares": [[str(w), list(ns), t(x)] for w, ns, x in c.wsquares],
            "induction": list(c.induction) if c.induction else None}


def _lemmas_of(c: Certificate) -> list[str]:
    names = {n for n, _ in c.coeffs} | set(c.factors)
    return sorted({n.removeprefix("lemma:").split("#")[0] for n in names
                   if n.startswith("lemma:")})


def certify_unique(plan: ObjPlan, ans: ObjAnswer) -> None:
    """A uniqueness certificate (D-026): the invariants imply asked = value, by ideal
    membership with recorded nonzero multipliers, checked by raw/certificate.py. Only
    for an unknown that is a whole property and a value in Q or Q(pi)."""
    [(q, v)] = ans.bindings[0].items()
    coords = plan.unknowns[q]
    prop = next((k for k, t in plan.props.items() if len(coords) == 1 and t == coords[0]),
                None)
    if prop is None:
        return
    x: Term = Compound("f.p", (Str(prop),))
    if isinstance(v, Compound) and v.functor == "f.qpi":
        qv = qpi_from(v.args)

        def at(cs: tuple[Fraction, ...]) -> Term:
            out: Term = Num(Fraction(0))
            for i, k in enumerate(cs):
                term: Term = Num(k)
                for _ in range(i):
                    term = Compound("*", (term, Compound("f.pi", ())))
                out = Compound("+", (out, term))
            return out
        x, v = Compound("*", (x, at(qv.den))), at(qv.num)
    elif not isinstance(v, Num):
        return
    goal = Compound("f.cmp", (Str("="), x, Num(v.value) if isinstance(v, Num) else v))
    hyps: dict[str, Term] = {}
    for n, inv in plan.cls.invariants:
        hyps.update(comparisons(inv, n))
    for k, t in plan.props.items():                # values the query gives
        if isinstance(t, Num) and not t.dims:
            hyps[f"given:{k}"] = Compound("f.cmp", (Str("="), Compound("f.p", (Str(k),)), t))
    cert = find(goal, hyps)
    if cert is not None and check(goal, hyps, cert):
        ans.records.append({"kind": "certificate", "class": plan.cls.name,
                            "goal": term_to_json(goal), "cert": cert_json(cert),
                            "givens": {k[6:]: term_to_json(h.args[2])  # type: ignore[union-attr]
                                       for k, h in hyps.items() if k.startswith("given:")}})
        used = sorted({n for n, _ in cert.coeffs} | set(cert.factors))
        ans.steps.append("uniqueness certificate [kernel: raw/certificate.py]: the "
                         f"invariants imply {prop} = {show(v) if isinstance(v, Num) else 'it'}"
                         + (f"; multipliers {', '.join(cert.factors)}" if cert.factors else "")
                         + f"; hypotheses used: {', '.join(used) or 'none'}")
        ans.certified = True


def _small_naturals(cls: ClassDef, th: tuple[str, Term], gen: dict[str, Term] | str,
                    steps: list[str], top: int = 12) -> dict[str, Term] | None:
    """A counterexample among small natural numbers, for a class whose properties are
    all Integer (sums with a symbolic limit cannot be expanded for the solver). Each
    candidate is decided by the trusted evaluator: invariants hold, theorem fails."""
    if isinstance(gen, str):
        return None
    names = [k for k, v in gen.items() if isinstance(v, Var)]
    if len(names) != len(gen) or not names or (top + 1) ** len(names) > 5000 or not all(
            n in {x.split(".")[-1] for x, _ in cls.invariants if x.startswith("Integer.")}
            for n in names):
        return None
    for vals in itertools.product(range(top + 1), repeat=len(names)):
        props: dict[str, Term] = {n: Num(Fraction(v)) for n, v in zip(names, vals, strict=True)}
        try:
            if failing(cls, props) == () and not holds(th[1], props):
                steps.append(f"re-check [checker] {_instance(props)}: every invariant holds "
                             f"and {th[0]} fails (small natural numbers, exhaustive to {top})")
                return props
        except Unsupported:
            continue
    return None


def _conjuncts_of(f: Term) -> int:
    return len(f.args) if isinstance(f, Compound) and f.functor == "f.and" else 1


def check_classes(classes: Classes, only: set[str] | None = None,
                  st: Settings | None = None) -> list[ObjAnswer]:
    """`ov check` for classes: consistency of the invariants, then every theorem."""
    st = st or Settings()
    out = []
    proven: dict[str, tuple[Term, frozenset[str]]] = {}
    certified: dict[str, Term] = {}
    for name, cls in classes.defs.items():
        if only is not None and name not in only:
            continue
        try:
            gen = generic(cls, classes.prop_types[name], classes.records, classes.record_types)
        except Unsupported as e:
            gen = str(e)
        ans = ObjAnswer(f"class {name} is consistent", "UNKNOWN", kind="consistency")
        r = _Run(st, ans.steps, ans.records)
        if isinstance(gen, str):
            ans.steps.append(f"no bounded instance: {gen}")
            ans.reason = "budget"
        else:
            ans = _consistency(cls, gen, r, ans)
        out.append(settle(ans, st))
        for th in cls.theorems:
            ta = ObjAnswer(f"theorem {th[0]}", "UNKNOWN", kind="theorem")
            same = [n for n in proven if st.reductions and classes.lemma_usable(n, name)
                    and n.split(".")[0] in classes.ancestors[name] and proven[n][0] == th[1]]
            if same:
                # Every invariant of an ancestor is an invariant here (the class is a subset),
                # so a theorem the ancestor proved, word for word, holds here too.
                ta.steps.append(f"inherited: {same[0]} states the same formula and is proven; "
                                f"{name} includes every invariant of "
                                f"{same[0].split('.')[0]}")
                ta.verdict = "PROVEN"
                ta.reductions = proven[same[0]][1] | {"inherit"}
            else:
                used: set[str] = set()
                try:
                    v, why, wit, _ = theorem(cls, th, _Run(st, ta.steps, ta.records), ta.steps, gen,
                                             used=used)
                except Unsupported as e:
                    ta.steps.append(f"cannot expand: {e}")
                    v, why, wit = "UNKNOWN", "plugin_unknown", None
                    small = _small_naturals(cls, th, gen, ta.steps)
                    if small is not None:
                        v, why, wit = "REFUTED", "", small
                lemmas = tuple((n, f) for n, (f, _) in proven.items()
                               if n.split(".")[0] in (*classes.ancestors[name], name)
                               and classes.lemma_usable(n, name))
                if v == "UNKNOWN" and lemmas and not isinstance(gen, str):
                    # A proven theorem holds on every instance, so adding it as a hypothesis
                    # keeps satisfiability; it often gives z3 the step it could not find.
                    ta.steps.append("retry with the proven lemmas " + ", ".join(
                        n for n, _ in lemmas))
                    used2: set[str] = set()
                    with_lemmas = replace(cls, invariants=(*cls.invariants, *lemmas))
                    try:
                        v2, why2, wit2, _ = theorem(with_lemmas, th, _Run(st, ta.steps,
                                                                          ta.records),
                                                    ta.steps, gen, used=used2)
                    except Unsupported:
                        v2, why2, wit2 = "UNKNOWN", "plugin_unknown", None
                    if v2 != "UNKNOWN":
                        v, why, wit, used = v2, why2, wit2, used2
                        ta.lemmas = tuple(n for n, _ in lemmas)
                        for n, _ in lemmas:
                            used |= proven[n][1]
                ta.verdict, ta.reason, ta.witness = v, why, wit
                ta.reductions = frozenset(used)
            if not ta.certified:
                certify(ta, cls, th, {n: f for n, f in certified.items()
                                      if n.split(".")[0] in (*classes.ancestors[name], name)
                                      and classes.lemma_usable(n, name)})
            settle(ta, st)
            if ta.verdict == "PROVEN":
                proven[th[0]] = (th[1], ta.reductions)
            if ta.certified:
                certified[th[0]] = th[1]
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
    res = r.solve(f"invariants of {cls.name}", _pin([cons], gen, ans.steps, r.st), list(names),
                  seek=True)
    if res.status == "sat" and res.model is not None:
        g, ok, _ = r.recheck_model(cls, gen, res.model)
        if ok == ():
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
