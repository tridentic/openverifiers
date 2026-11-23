"""Run a ``.ov`` file: check, lower, evaluate, check the trace, answer its queries.

    python -m openverifiers.runner examples/chem/q11.ov [--verbose]

This is the Milestone-1 runner. The ``ov run`` command (Milestone 3) wraps it,
and OKQL (Milestone 4) replaces its small query set (PROVE, FIND, WHAT IF).
Every answer comes from a model the checker accepted.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from .checker import Inconsistent, Proven, Refuted, Unknown, Verdict, verdict
from .checker.objects import check_records
from .checker.verdict import default_context
from .engine import Run, ask, find_all, run, without
from .kernel.evaluate import Budget
from .lang import ast as A
from .lang.check import DRAFTS, Env, load
from .lang.errors import Diagnostic, OVError
from .lang.units import show_quantity
from .lower.lower import Lowered, QueryPlan, _Ctx, _value, is_hidden, lower, term
from .objects.engine import ObjAnswer, Settings, check_classes, show
from .objects.engine import answer as obj_answer
from .raw.canon import term_to_json
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
    def trust_base(self) -> frozenset[str]:
        """Rule verdicts come from a trace the independent checker accepted."""
        return frozenset() if self.verdict == "UNKNOWN" else frozenset({"kernel"})

    @property
    def assumptions(self) -> frozenset[tuple[str, bool]]:
        v = self.detail
        if isinstance(v, (Proven, Refuted)):
            return frozenset(x for x in v.assumptions if not is_hidden(x[0]))
        return frozenset()


@dataclass
class FileResult:
    env: Env
    lowered: list[Lowered]
    answers: list[Answer]
    runs: dict[str, Run]
    objects: list[ObjAnswer] = field(default_factory=list)     # object-layer queries
    classes: list[ObjAnswer] = field(default_factory=list)     # class and theorem checks

    @property
    def draft_packages(self) -> list[str]:
        """Packages loaded from drafts/: every result of this file is provisional."""
        return sorted(n for n, m in self.env.modules.items()
                      if Path(m.file).resolve().is_relative_to(DRAFTS))

    @property
    def failed(self) -> list[Answer | ObjAnswer]:
        both: list[Answer | ObjAnswer] = [*self.answers, *self.objects]
        return [a for a in both if a.expect_ok is False]

    @property
    def class_errors(self) -> list[ObjAnswer]:
        """Refuted theorems and empty classes: errors for `ov check`."""
        return [a for a in self.classes if a.verdict in ("REFUTED", "INCONSISTENT")]


def run_file(path: str | Path, *, source: str | None = None, budget: Budget | None = None,
             files: set[str] | None = None, settings: Settings | None = None) -> FileResult:
    drafts = settings is not None and settings.drafts and not settings.strict
    env = load(path, source=source, search=(DRAFTS,) if drafts else ())
    if settings is not None and settings.strict:
        undeclared = [d for d in env.warnings if d.code == "W201"]
        if undeclared:
            raise OVError([Diagnostic("E208", d.message + " (an error under --strict)", d.span,
                                      d.hint) for d in undeclared], env.sources())
    lowered = lower(env, files)
    answers: list[Answer] = []
    runs: dict[str, Run] = {}
    objs: list[ObjAnswer] = []
    for lw in lowered:
        for qy, ex, test in lw.objects:
            oa = obj_answer(env.objects.plans[qy.span], settings)
            oa.title = (f"[test {test}] " if test else "") + oa.title
            if ex is not None:
                _check_obj_expect(oa, ex)
            objs.append(oa)
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
    files_ = {env.main.file} if files is None else files
    mine = {n for n, d in env.class_decls.items() if d.span.file in files_}
    classes = check_classes(env.objects, mine, settings) if mine else []
    recheck_records([*classes, *objs], env.objects.defs)
    return FileResult(env, lowered, answers, runs, objs, classes)


def recheck_records(answers: Sequence[ObjAnswer], defs: Mapping[str, Any]) -> None:
    """Condition B: re-check every object record from JSON with the trusted checker
    (checker/objects.py), in order (lemma certificates before their uses). An answer
    with a rejected record loses its verdict: that would be an engine bug."""
    for a in answers:                    # a uniqueness claim's givens: from the plan
        for r in a.records:
            if "goal" in r and a.plan is not None:
                r["givens"] = {k: term_to_json(t) for k, t in a.plan.props.items()
                               if isinstance(t, Num) and not t.dims}
    flat = [(a, r) for a in answers for r in a.records]
    bad = {int(m.split()[1]) for m in check_records([r for _, r in flat], defs)}
    for i in sorted(bad):
        a = flat[i][0]
        a.steps.append("BUG: a record behind this verdict was rejected by the checker")
        a.verdict, a.reason, a.trust_base = "UNKNOWN", "plugin_unknown", frozenset()


def _check_obj_expect(a: ObjAnswer, ex: A.Expect) -> None:
    problems = []
    if a.verdict != ex.verdict:
        problems.append(f"verdict {a.verdict}")
    if ex.values:
        try:
            want = [_obj_value(e) for e in ex.values]
        except ValueError as e:
            want, problems = [], [*problems, str(e)]
        if a.count is not None:
            got = [Num(Fraction(a.count))]
            if got != want:
                problems.append(f"count {a.count}")
        elif want and a.plan is not None:
            got_rows = {tuple(b[q] for q in a.plan.unknowns) for b in a.bindings}
            if got_rows != {tuple(want)}:
                problems.append("values " + "; ".join(
                    ", ".join(show(t) for t in r) for r in sorted(got_rows, key=str)))
    a.expect_ok = not problems
    a.expect_msg = "" if not problems else "got " + ", ".join(problems)


def _obj_value(e: A.Expr) -> Term:
    if isinstance(e, A.Quantity):
        return Num(e.value, e.dims)
    if isinstance(e, A.Neg) and isinstance(e.arg, A.Quantity):
        return Num(-e.arg.value, e.arg.dims)
    if isinstance(e, A.TupleLit):
        return Compound("f.tuple", tuple(_obj_value(x) for x in e.items))
    raise ValueError("expected values are numbers or tuples")


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
    return "{" + ", ".join(("" if s else "not ") + n for n, s in sorted(env)
                           if not is_hidden(n)) + "}"


def missing_text(a: Atom, lw: Lowered) -> str:
    """A missing-facts entry: `assume(n)` / `retract(n)` shown as n's statement."""
    if a.pred in ("assume", "retract") and a.args and isinstance(a.args[0], Sym):
        info = lw.assumption_info.get(a.args[0].name)
        if info is not None:
            return f"{'' if a.pred == 'assume' else 'not '}{info[0]}"
    return _atom(a, lw)


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
        out.append("  " + _line(a, lw) + ("  trust {kernel}" if a.trust_base else ""))
        if a.expect_ok is not None:
            mark = "ok" if a.expect_ok else f"FAILED ({a.expect_msg})"
            out.append(f"  expect {a.plan.expect.verdict if a.plan.expect else ''}: {mark}")
        mode = getattr(q.q, "mode", "prove")
        if verbose or mode != "prove":
            out.extend("    " + s for s in explain(a, res.runs[a.scenario], lw, mode))
    for oa in res.objects:
        out.extend(_obj_lines(oa, verbose))
    for ca in res.classes:
        out.extend(_obj_lines(ca, verbose, check=True))
    both: list[Answer | ObjAnswer] = [*res.answers, *res.objects]
    n_exp = sum(1 for a in both if a.expect_ok is not None)
    if n_exp:
        out.append(f"{n_exp - len(res.failed)}/{n_exp} expectations met")
    return "\n".join(out)


def _obj_lines(a: ObjAnswer, verbose: bool, check: bool = False) -> list[str]:
    if a.plan is not None:
        q = a.plan.query
        head = f"{Path(q.span.file).name}:{q.span.line}  query {a.title}"
    else:
        head = f"check {a.title}"
    v = a.verdict
    if check and v == "UNKNOWN" and a.title.startswith("theorem"):
        v = "UNPROVEN"
    parts = [v]
    if a.reason:
        parts.append(f"({a.reason})")
    for b in a.bindings:
        parts.append(", ".join(f"?{k} = {show(t)}" for k, t in b.items()))
    if a.count is not None:
        parts.append(f"count = {a.count}")
    if a.trust_base:
        parts.append("trust {" + ", ".join(sorted(a.trust_base)) + "}")
    if a.names:
        parts.append(("conflicting invariants: " if v == "INCONSISTENT" else "fails: ")
                     + ", ".join(a.names))
    if a.witness is not None and (v != "PROVEN" or a.plan is not None):
        parts.append("instance: " + ", ".join(f"{k} = {show(t)}" for k, t in a.witness.items()))
    if not a.complete and a.bindings and not (a.plan and a.plan.kind == "unique"):
        parts.append("(more solutions exist)")
    out = [head, "  " + "  ".join(parts)]
    if a.expect_ok is not None:
        out.append("  expect: " + ("ok" if a.expect_ok else f"FAILED ({a.expect_msg})"))
    if verbose:
        out.extend("    " + s for s in a.steps)
    return out


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
        parts.append("missing: " + "; ".join(", ".join(missing_text(x, lw) for x in m)
                                             for m in v.missing[:3]))
    return "  ".join(parts)


def explain(a: Answer, r: Run, lw: Lowered, mode: str = "prove") -> list[str]:
    """WHY: the checked derivation, leaves first (facts with their origins).
    WHY NOT: for REFUTED the refutation; for UNKNOWN what blocks it (the missing
    facts, each alternative re-checked against the model); if it holds after all,
    the derivation."""
    lines = _proof_lines(a, r, lw)
    if mode != "why_not":
        return lines if lines or mode == "prove" else ["no derivation: " + a.verdict]
    v = a.detail
    if isinstance(v, Unknown):
        alts = [" and ".join(_atom(x, lw) for x in alt) for alt in v.missing]
        return [f"blocked ({v.reason}): add one of: " + " | ".join(alts)] if alts else \
            [f"blocked ({v.reason}): nothing derives it and no single missing fact would"]
    head = {"REFUTED": "refuted by:", "PROVEN": "it holds after all:"}.get(a.verdict,
                                                                         a.verdict)
    return [head, *lines]


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


def summary(res: FileResult) -> str:
    """One line for `ov check`: what was checked and what failed."""
    both: list[Answer | ObjAnswer] = [*res.answers, *res.objects]
    exp = [a for a in both if a.expect_ok is not None]
    bad = len(res.failed) + len(res.class_errors)
    return (f"{res.env.main.file}: {'FAIL' if bad else 'ok'} "
            f"({len(res.runs)} scenario(s), {len(res.answers) + len(res.objects)} queries, "
            f"{len(exp) - len(res.failed)}/{len(exp)} expectations, "
            f"class checks: {sum(a.verdict == 'PROVEN' for a in res.classes)} proven, "
            f"{sum(a.verdict == 'UNKNOWN' for a in res.classes)} unknown, "
            f"{len(res.class_errors)} failed)")


def main(argv: Sequence[str] | None = None, *, check: bool = False) -> int:
    """`ov run` (full output) or, with check=True, `ov check` (one line per file)."""
    args = list(sys.argv[1:] if argv is None else argv)
    verbose = "--verbose" in args
    settings = Settings(strict="--strict" in args, reductions="--no-reductions" not in args,
                        drafts="--drafts" in args)
    if settings.strict and settings.drafts:
        print("ov: --drafts loads unapproved library lines; it cannot be combined with "
              "--strict", file=sys.stderr)
        return 2
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print(f"usage: ov {'check' if check else 'run'} FILE.ov [FILE.ov ...] "
              "[--verbose] [--strict]", file=sys.stderr)
        return 2
    code = 0
    for p in paths:
        try:
            res = run_file(p, files={str(p)}, settings=settings)
        except OVError as e:
            print(e.render(), file=sys.stderr)
            code = 1
            continue
        print(summary(res) if check else render(res, verbose))
        if res.draft_packages:
            print("PROVISIONAL: uses unapproved draft packages "
                  + ", ".join(res.draft_packages), file=sys.stderr)
        if check and verbose:
            for a in (*res.failed, *res.class_errors):
                print(f"  {a.verdict}: {getattr(a, 'title', '')} {a.expect_msg}".rstrip())
        if res.failed or res.class_errors:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
