"""Run a ``.ov`` file: check, lower, evaluate, check the trace, answer its queries.

    python -m openverifiers.runner examples/chem/q11.ov [--verbose]

This is the Milestone-1 runner. The ``ov run`` command (Milestone 3) wraps it,
and OKQL (Milestone 4) replaces its small query set (PROVE, FIND, WHAT IF).
Every answer comes from a model the checker accepted.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .checker import Inconsistent, Proven, Refuted, Unknown, Verdict, verdict
from .checker.verdict import default_context
from .engine import Run, ask, find_all, run, without
from .kernel.evaluate import Budget
from .lang import ast as A
from .lang.check import Env, load
from .lang.errors import OVError
from .lang.units import show_quantity
from .lower.lower import Lowered, QueryPlan, _Ctx, _value, lower, term
from .raw.program import Atom
from .raw.terms import Compound, Num, Str, Sym, Term


@dataclass
class Answer:
    plan: QueryPlan
    scenario: str
    verdict: str                                   # PROVEN | REFUTED | UNKNOWN | INCONSISTENT
    bindings: list[tuple[dict[str, Term], Verdict]] = field(default_factory=list)
    detail: Verdict | None = None
    candidates: dict[str, list[Term]] = field(default_factory=dict)
    expect_ok: bool | None = None
    expect_msg: str = ""

    @property
    def assumptions(self) -> frozenset[tuple[str, bool]]:
        v = self.detail
        if isinstance(v, (Proven, Refuted)):
            return v.assumptions
        return frozenset()


@dataclass
class FileResult:
    env: Env
    lowered: list[Lowered]
    answers: list[Answer]
    runs: dict[str, Run]

    @property
    def failed(self) -> list[Answer]:
        return [a for a in self.answers if a.expect_ok is False]


def run_file(path: str | Path, *, source: str | None = None, budget: Budget | None = None,
             files: set[str] | None = None) -> FileResult:
    env = load(path, source=source)
    lowered = lower(env, files)
    answers: list[Answer] = []
    runs: dict[str, Run] = {}
    for lw in lowered:
        base = run(lw.program, budget)
        runs[lw.scenario] = base
        for plan in lw.queries:
            r = base
            if plan.retract_items:
                r = run(without(lw.program, set(plan.retract_items)), budget)
            ctx = (default_context(r.model) - plan.retract_assumptions) | plan.add_assumptions
            ans = answer(plan, lw, r, ctx)
            if plan.expect is not None:
                _check_expect(ans, plan.expect, env, lw)
            answers.append(ans)
    return FileResult(env, lowered, answers, runs)


def answer(plan: QueryPlan, lw: Lowered, r: Run, ctx: frozenset[str]) -> Answer:
    if plan.kind == "prove":
        v = ask(r, plan.atom or Atom(plan.pred), ctx)
        return Answer(plan, lw.scenario, _name(v), detail=v)
    pattern = Atom(plan.pred, tuple(_var(n) for n in plan.vars))
    found = find_all(r, pattern, ctx)
    proven: list[tuple[dict[str, Term], Verdict]] = [
        (s, v) for s, v in found if isinstance(v, Proven)]
    if proven:
        return Answer(plan, lw.scenario, "PROVEN", proven, proven[0][1])
    # Nothing proven: report why, using the verdict of an instance nobody derived.
    probe = Atom(plan.pred, tuple(Sym("?") for _ in plan.vars))
    v = verdict(r.model, probe, ctx)
    ans = Answer(plan, lw.scenario, _name(v), found, v)
    if isinstance(v, Unknown):
        for n in plan.unknown_vars:
            pred, i, k = lw.candidates[n]
            pat = Atom(pred, tuple(_var(f"C{j}") for j in range(k)))
            vals = {s[f"C{i}"] for s, cv in find_all(r, pat, ctx) if isinstance(cv, Proven)}
            ans.candidates[n] = sorted(vals, key=lambda t: _show(t, lw))
        if any(len(c) > 1 for c in ans.candidates.values()):
            ans.detail = Unknown(v.atom, v.missing, "missing_facts")
    return ans


def _var(n: str) -> Term:
    from .raw.terms import Var
    return Var(n)


def _name(v: Verdict) -> str:
    return {Proven: "PROVEN", Refuted: "REFUTED", Unknown: "UNKNOWN",
            Inconsistent: "INCONSISTENT"}[type(v)]


def _check_expect(ans: Answer, ex: A.Expect, env: Env, lw: Lowered) -> None:
    problems = []
    if ans.verdict != ex.verdict:
        problems.append(f"verdict {ans.verdict}")
    if ex.values:
        cx = _Ctx(env, env.scenarios[lw.scenario])
        want = tuple(_value(term(e, cx, True), cx, e.span) for e in ex.values)
        if ans.verdict == "PROVEN" and ans.plan.kind == "find":
            got = {tuple(s[n] for n in ans.plan.vars) for s, _ in ans.bindings}
            if got != {want}:
                problems.append("values " + "; ".join(
                    ", ".join(_show(t, lw) for t in g) for g in sorted(got, key=str)))
        elif ans.candidates:
            got_c = {t for c in ans.candidates.values() for t in c}
            if got_c != set(want):
                problems.append("candidates " + ", ".join(_show(t, lw) for t in got_c))
        else:
            problems.append("no values to compare")
    if ex.assuming is not None:
        got_a = {n for n, s in ans.assumptions if s}
        if got_a != set(ex.assuming):
            problems.append("assumptions {" + ", ".join(sorted(got_a)) + "}")
    ans.expect_ok = not problems
    ans.expect_msg = "" if not problems else "got " + ", ".join(problems)


# ---------------------------------------------------------------- printing


def _show(t: Term, lw: Lowered) -> str:
    if t in lw.names:
        return lw.names[t]
    if isinstance(t, Num):
        return show_quantity(t.value, t.dims)
    if isinstance(t, Sym):
        return t.name
    if isinstance(t, Str):
        return repr(t.value)
    if isinstance(t, Compound):
        return f"{t.functor}({', '.join(_show(a, lw) for a in t.args)})"
    return str(t)


def _assumptions(env: frozenset[tuple[str, bool]]) -> str:
    return "{" + ", ".join(("" if s else "not ") + n for n, s in sorted(env)) + "}"


def render(res: FileResult, verbose: bool = False) -> str:
    out: list[str] = []
    by_scn = {lw.scenario: lw for lw in res.lowered}
    for w in res.env.warnings:
        out.append(w.render(res.env.sources().get(w.span.file)))
    for a in res.answers:
        lw = by_scn[a.scenario]
        q = a.plan.query
        where = f"{Path(q.span.file).name}:{q.span.line}"
        test = f" [test {a.plan.test}]" if a.plan.test else ""
        out.append(f"{where}{test}  query {q.text}")
        out.append("  " + _line(a, lw))
        if a.expect_ok is not None:
            mark = "ok" if a.expect_ok else f"FAILED ({a.expect_msg})"
            out.append(f"  expect {a.plan.expect.verdict if a.plan.expect else ''}: {mark}")
        if verbose:
            out.extend("    " + s for s in _proof_lines(a, res.runs[a.scenario], lw))
    n_exp = sum(1 for a in res.answers if a.expect_ok is not None)
    if n_exp:
        out.append(f"{n_exp - len(res.failed)}/{n_exp} expectations met")
    return "\n".join(out)


def _line(a: Answer, lw: Lowered) -> str:
    v = a.detail
    if a.verdict == "PROVEN" and a.bindings:
        rows = []
        for s, bv in a.bindings:
            vals = ", ".join(f"{n} = {_show(s[n], lw)}" for n in a.plan.vars)
            env = bv.assumptions if isinstance(bv, Proven) else frozenset()
            rows.append(f"PROVEN  {vals}  assumptions {_assumptions(env)}")
        return "\n  ".join(rows)
    if isinstance(v, (Proven, Refuted)):
        extra = "  (closed world)" if isinstance(v, Refuted) and v.closed_world else ""
        return (f"{a.verdict}  assumptions {_assumptions(v.assumptions)}  "
                f"proof: {len(v.proof)} steps{extra}")
    if isinstance(v, Inconsistent):
        return f"INCONSISTENT  conflict: {', '.join(v.conflict_set) or '(base theory)'}"
    assert isinstance(v, Unknown)
    parts = [f"UNKNOWN ({v.reason})"]
    for n, cs in a.candidates.items():
        parts.append(f"{n} in {{{', '.join(_show(c, lw) for c in cs)}}}")
    if v.missing:
        parts.append("missing: " + "; ".join(", ".join(str(x) for x in m) for m in v.missing[:3]))
    return "  ".join(parts)


def _proof_lines(a: Answer, r: Run, lw: Lowered) -> list[str]:
    v = a.bindings[0][1] if a.bindings else a.detail
    if not isinstance(v, (Proven, Refuted)):
        return []
    steps = {s.id: s for s in r.trace.steps}
    out = []
    for i in sorted(v.proof):
        s = steps[i]
        where = f"  ({Path(s.span.file).name}:{s.span.line})" if s.span else ""
        out.append(f"#{i} {s.rule_id}: {_atom(s.conclusion, lw)}{where}")
    return out


def _atom(a: Atom, lw: Lowered) -> str:
    args = ", ".join(_show(t, lw) for t in a.args)
    return f"{'not ' if a.neg else ''}{a.pred}({args})" if a.args else \
        f"{'not ' if a.neg else ''}{a.pred}"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    verbose = "--verbose" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print("usage: python -m openverifiers.runner FILE.ov [--verbose]", file=sys.stderr)
        return 2
    code = 0
    for p in paths:
        try:
            res = run_file(p, files={str(p)})
        except OVError as e:
            print(e.render(), file=sys.stderr)
            code = 1
            continue
        print(render(res, verbose))
        if res.failed:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
