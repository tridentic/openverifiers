"""The trusted checker: ``check(initial_facts, requirements, proof, pack) -> Verdict``.

Rules, in order (each has a passing and a failing test in tests/kernel):

1. Structure. Fact ids are unique across initial facts, their children, and
   every claimed output (an output may only fill an initial ``target`` or
   ``unknown`` slot). Step ids are unique. Every fact type is registered and
   passes its validator. Every transformation exists. Every input id is an
   initial fact or some step's output. The step graph is acyclic.
2. Steps, in topological order. A step is skipped if a step it depends on
   failed. Otherwise: its roles match the transformation's signature; its
   inputs exist, are established (not ``target``/``unknown``) and have the
   declared types; its preconditions hold; if the transformation has an
   effect, the recomputed outputs equal the claimed ones; its checker accepts;
   and a grounded step's outputs cite a source the pack actually has.
   Only then are its outputs (the recomputed ones when available) added.
3. Requirements over the final state: each selector matches exactly one fact,
   that fact is established, and the predicate holds.

Nothing the proposer says about a step's result is taken on trust: results
are either recomputed by the effect or must pass the checker. Hook exceptions
fail closed. The kernel imports only the standard library.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from .model import (
    FACT_STATUSES,
    DomainPack,
    Fact,
    FactStatus,
    Failure,
    Proof,
    Provenance,
    Requirement,
    Step,
    TraceEvent,
    TrustGrade,
    Verdict,
)

_OPEN_SLOTS = ("target", "unknown")
_UNDETERMINED_CODES = frozenset(
    {"input_unknown", "requirement_unknown", "dependency_failed", "requirement_not_reached"}
)


def flatten(facts: Iterable[Fact]) -> list[Fact]:
    """Facts and all their children, depth first, in declaration order."""
    out: list[Fact] = []
    for f in facts:
        out.append(f)
        out.extend(flatten(f.children))
    return out


def facts_equal(pack: DomainPack, a: Fact, b: Fact) -> bool:
    """Pack-defined equality for ``a``'s type, else same type/unit/owner/value."""
    ftype = pack.fact_types.get(a.type)
    if ftype is not None and ftype.equal is not None:
        return ftype.equal(a, b)
    return a.type == b.type and a.unit == b.unit and a.owner == b.owner and values_equal(
        a.value, b.value
    )


def values_equal(x: Any, y: Any) -> bool:
    if _is_number(x) and _is_number(y):
        return math.isclose(float(x), float(y), rel_tol=1e-9, abs_tol=1e-12)
    return bool(x == y)


def _is_number(x: Any) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def _validate_fact(pack: DomainPack, f: Fact, where: str, *, initial: bool) -> list[Failure]:
    if f.type not in pack.fact_types:
        return [Failure("unknown_fact_type", f"{where}: type {f.type!r} is not registered by "
                        f"pack {pack.name!r}", facts=(f.id,))]
    problem: str | None = None
    if f.status not in FACT_STATUSES:
        problem = f"status {f.status!r} is not one of {FACT_STATUSES}"
    elif initial and f.status == "derived":
        problem = "an initial fact cannot claim to be derived; use truth or unverified"
    elif f.status == "unknown" and not f.why_unknown:
        problem = "an unknown fact must say why_unknown"
    else:
        validate = pack.fact_types[f.type].validate
        try:
            problem = validate(f) if validate is not None and f.status not in _OPEN_SLOTS else None
        except Exception as exc:  # fail closed
            problem = f"validator raised {type(exc).__name__}: {exc}"
    if problem:
        return [Failure("invalid_fact", f"{where}: fact {f.id!r}: {problem}", facts=(f.id,))]
    return []


def check(
    initial_facts: Sequence[Fact],
    requirements: Sequence[Requirement],
    proof: Proof,
    pack: DomainPack,
) -> Verdict:
    """Check ``proof`` against ``pack``. Pure given pure pack hooks."""
    events: list[TraceEvent] = []
    failures: list[Failure] = []

    # ---- 1. structure ---------------------------------------------------
    structural: list[Failure] = []
    step_fail: dict[str, list[Failure]] = {}  # failures pinned on a step before it runs

    def pin(step_id: str, failure: Failure) -> None:
        step_fail.setdefault(step_id, []).append(failure)

    initial: dict[str, Fact] = {}
    for f in flatten(initial_facts):
        if f.id in initial:
            structural.append(Failure("duplicate_fact_id", f"initial fact id {f.id!r} is "
                                      "declared more than once", facts=(f.id,)))
            continue
        initial[f.id] = f
        structural.extend(_validate_fact(pack, f, "initial fact", initial=True))

    steps: dict[str, Step] = {}
    for s in proof.steps:
        if s.id in steps:
            structural.append(Failure("duplicate_step_id", f"step id {s.id!r} is used more "
                                      "than once", step_id=s.id))
        else:
            steps[s.id] = s
    order = list(steps)

    producer: dict[str, str] = {}
    for sid in order:
        s = steps[sid]
        if s.transformation not in pack.transformations:
            pin(sid, Failure("unknown_transformation", f"{s.transformation!r} is not "
                             f"registered by pack {pack.name!r}", step_id=sid))
        for out in flatten(s.outputs.values()):
            prior = initial.get(out.id)
            if out.id in producer or (prior is not None and prior.status not in _OPEN_SLOTS):
                first = producer.get(out.id, "the initial facts")
                pin(sid, Failure("duplicate_fact_id", f"output {out.id!r} is already "
                                 f"defined by {first}", step_id=sid, facts=(out.id,)))
                continue
            producer[out.id] = sid
            for fl in _validate_fact(pack, out, f"output of step {sid!r}", initial=False):
                pin(sid, replace(fl, step_id=sid))

    deps: dict[str, set[str]] = {sid: set() for sid in order}
    for sid in order:
        for ref in steps[sid].inputs.values():
            if ref in producer:
                deps[sid].add(producer[ref])
            elif ref not in initial:
                pin(sid, Failure("missing_input", f"input {ref!r} is neither an initial fact "
                                 "nor produced by any step", step_id=sid, facts=(ref,)))

    ordered, cyclic, downstream = _toposort(order, deps)
    topo = ordered + cyclic + downstream
    if cyclic:
        structural.append(Failure("cycle", f"steps {cyclic} form or sit between dependency "
                                  "cycles", facts=()))
        for sid in cyclic:
            pin(sid, Failure("cycle", f"step {sid!r} is part of a dependency cycle", step_id=sid))

    failures.extend(structural)
    events.append(TraceEvent(
        "structure", "proof", "rejected" if structural or step_fail else "accepted",
        checks=(("fact ids unique and types valid", not structural, ""),
                ("steps well-formed and acyclic", not step_fail and not cyclic, "")),
        failures=tuple(structural)))

    # ---- 2. steps -------------------------------------------------------
    state: dict[str, Fact] = dict(initial)
    failed: set[str] = set()
    for sid in topo:
        s = steps[sid]
        pinned = step_fail.get(sid, [])
        upstream = sorted({producer[r] for r in s.inputs.values()
                           if r in producer and producer[r] in failed})
        if upstream and not pinned:
            fl = Failure("dependency_failed", f"depends on failed step(s) {upstream}",
                         step_id=sid, facts=tuple(r for r in s.inputs.values()
                                                  if producer.get(r) in failed))
            failed.add(sid)
            failures.append(fl)
            events.append(TraceEvent("step", sid, "skipped", failures=(fl,)))
            continue
        if pinned:
            failed.add(sid)
            failures.extend(pinned)
            events.append(TraceEvent("step", sid, "rejected", failures=tuple(pinned)))
            continue
        checks, step_failures, produced = _run_step(s, state, pack)
        if step_failures:
            failed.add(sid)
            failures.extend(step_failures)
            events.append(TraceEvent("step", sid, "rejected", tuple(checks),
                                     tuple(step_failures)))
            continue
        for f in flatten(produced):
            state[f.id] = f
        events.append(TraceEvent("step", sid, "accepted", tuple(checks)))

    # ---- 3. requirements --------------------------------------------------
    support: set[str] = set()
    unverified: set[str] = set()
    for req in requirements:
        rfail, fact = _check_requirement(req, state, pack)
        if rfail is not None:
            failures.append(rfail)
            events.append(TraceEvent("requirement", req.id, "rejected", failures=(rfail,)))
            continue
        assert fact is not None
        _collect_support(fact.id, producer, steps, failed, initial, support, unverified)
        events.append(TraceEvent("requirement", req.id, "accepted",
                                 checks=((f"{req.predicate} on {fact.id}", True, ""),)))

    tiers = {pack.transformations[steps[sid].transformation].tier for sid in support}
    soft = tuple(sid for sid in order if sid in support
                 and pack.transformations[steps[sid].transformation].tier == "soft")
    grade: TrustGrade
    if failures:
        codes = {f.code for f in failures}
        unknown = bool(codes & {"input_unknown", "requirement_unknown"})
        grade = "undetermined" if unknown and codes <= _UNDETERMINED_CODES else "invalid"
    elif soft:
        grade = "conditional_on_soft_steps"
    elif unverified:
        grade = "conditional_on_unverified_facts"
    elif "grounded" in tiers:
        grade = "grounded"
    else:
        grade = "fully_hard"
    return Verdict(
        valid=not failures, trust_grade=grade, failures=tuple(failures), soft_steps=soft,
        unverified_facts=tuple(sorted(unverified)),
        support=tuple(sid for sid in order if sid in support), trace=tuple(events))


def _toposort(
    order: list[str], deps: Mapping[str, set[str]]
) -> tuple[list[str], list[str], list[str]]:
    """Kahn's algorithm, ties broken by proof order.

    Returns (sorted, cyclic, downstream): ``cyclic`` are steps that lie on a
    cycle; ``downstream`` are steps that only depend on one, topologically
    sorted so they can be reported as dependency failures.
    """

    def kahn(nodes: set[str]) -> tuple[list[str], set[str]]:
        remaining = {n: deps[n] & nodes for n in nodes}
        out: list[str] = []
        while True:
            ready = next((n for n in order if n in remaining and not remaining[n]), None)
            if ready is None:
                return out, set(remaining)
            out.append(ready)
            del remaining[ready]
            for d in remaining.values():
                d.discard(ready)

    def on_cycle(start: str, within: set[str]) -> bool:
        stack, seen = list(deps[start] & within), set[str]()
        while stack:
            n = stack.pop()
            if n == start:
                return True
            if n not in seen:
                seen.add(n)
                stack.extend(deps[n] & within)
        return False

    ordered, rest = kahn(set(order))
    cyclic = [n for n in order if n in rest and on_cycle(n, rest)]
    downstream, _ = kahn(rest - set(cyclic))
    return ordered, cyclic, downstream


def _run_step(
    s: Step, state: Mapping[str, Fact], pack: DomainPack
) -> tuple[list[tuple[str, bool, str]], list[Failure], list[Fact]]:
    t = pack.transformations[s.transformation]
    checks: list[tuple[str, bool, str]] = []
    fails: list[Failure] = []

    def fail(code: str, msg: str, *, facts: tuple[str, ...] = (), pre: str | None = None) -> None:
        fails.append(Failure(code, msg, step_id=s.id, precondition=pre, facts=facts))
        checks.append((code, False, msg))

    if set(s.inputs) != set(t.inputs):
        fail("input_role_mismatch", f"{t.id} takes inputs {sorted(t.inputs)}, "
             f"step gives {sorted(s.inputs)}")
    if set(s.outputs) != set(t.outputs):
        fail("output_role_mismatch", f"{t.id} produces {sorted(t.outputs)}, "
             f"step claims {sorted(s.outputs)}")
    if fails:
        return checks, fails, []
    inputs: dict[str, Fact] = {}
    for role, ref in s.inputs.items():
        f = state[ref]
        if f.status == "target":
            fail("input_not_established", f"input {role}={ref!r} is a target, not yet derived",
                 facts=(ref,))
        elif f.status == "unknown":
            need = f"; evidence needed: {list(f.evidence_needed)}" if f.evidence_needed else ""
            fail("input_unknown", f"input {role}={ref!r} is unknown ({f.why_unknown}){need}",
                 facts=(ref,))
        elif t.inputs[role] not in ("*", f.type):
            fail("input_type_mismatch", f"input {role}={ref!r} has type {f.type!r}, "
                 f"{t.id} needs {t.inputs[role]!r}", facts=(ref,))
        inputs[role] = f
    for role, out in s.outputs.items():
        if t.outputs[role] not in ("*", out.type):
            fail("output_mismatch", f"output {role}={out.id!r} has type {out.type!r}, "
                 f"{t.id} produces {t.outputs[role]!r}", facts=(out.id,))
    if fails:
        return checks, fails, []
    checks.append(("inputs established and typed", True, ""))

    for pre in t.preconditions:
        try:
            why = pre.check(inputs, s.params)
        except Exception as exc:  # fail closed
            why = f"raised {type(exc).__name__}: {exc}"
        if why:
            fail("precondition_failed", f"precondition {pre.name!r}: {why}",
                 facts=tuple(f.id for f in inputs.values()), pre=pre.name)
        else:
            checks.append((f"precondition {pre.name}", True, ""))
    if fails:
        return checks, fails, []

    origin = Provenance(source=f"step:{s.id}")
    produced: dict[str, Fact] = {}
    if t.effect is not None:
        try:
            computed = dict(t.effect(inputs, s.params))
        except Exception as exc:  # fail closed
            fail("effect_error", f"effect raised {type(exc).__name__}: {exc}")
            return checks, fails, []
        if set(computed) != set(t.outputs):
            fail("effect_error", f"effect returned roles {sorted(computed)}, "
                 f"expected {sorted(t.outputs)}")
            return checks, fails, []
        for role, claimed in s.outputs.items():
            fresh = replace(computed[role], id=claimed.id)
            if not facts_equal(pack, fresh, claimed):
                fail("output_mismatch", f"claimed {role}={claimed.id!r} is {_show(claimed)}, "
                     f"recomputed {_show(fresh)}", facts=(claimed.id,))
            produced[role] = fresh
        if fails:
            return checks, fails, []
        checks.append(("claimed outputs match recomputation", True, ""))
    else:
        produced = dict(s.outputs)
    for role, f in produced.items():
        claim_prov = s.outputs[role].provenance
        cite = claim_prov.citation if claim_prov is not None else None
        status: FactStatus = "unknown" if f.status == "unknown" else "derived"
        produced[role] = replace(f, status=status, provenance=replace(origin, citation=cite))

    if t.checker is not None:
        try:
            why = t.checker(inputs, s.params, produced)
        except Exception as exc:  # fail closed
            fail("checker_error", f"checker raised {type(exc).__name__}: {exc}")
            return checks, fails, []
        if why:
            fail("checker_rejected", f"{t.tier} checker: {why}",
                 facts=tuple(f.id for f in produced.values()))
            return checks, fails, []
        checks.append((f"{t.tier} checker", True, ""))

    if t.tier == "grounded":
        for f in produced.values():
            cite = f.provenance.citation if f.provenance else None
            if cite is None or cite not in pack.sources:
                fail("citation_missing", f"grounded output {f.id!r} cites {cite!r}, which is "
                     f"not a source in pack {pack.name!r}", facts=(f.id,))
        if fails:
            return checks, fails, []
        checks.append(("citations exist", True, ""))
    return checks, fails, list(produced.values())


def _show(f: Fact) -> str:
    return f"{f.value!r}" + (f" {f.unit}" if f.unit else "")


def select(req: Requirement, state: Mapping[str, Fact]) -> list[Fact]:
    """All facts the requirement's selector matches."""
    sel = req.selector
    pool = [state[sel.fact_id]] if sel.fact_id is not None and sel.fact_id in state else (
        [] if sel.fact_id is not None else list(state.values()))
    own = {"type", "owner", "unit"}
    return [f for f in pool if all(
        (getattr(f, k) if k in own else f.attributes.get(k, _MISSING)) == v
        for k, v in sel.where.items())]


_MISSING = object()


def _check_requirement(
    req: Requirement, state: Mapping[str, Fact], pack: DomainPack
) -> tuple[Failure | None, Fact | None]:
    def fl(code: str, msg: str, facts: tuple[str, ...] = ()) -> tuple[Failure, None]:
        return Failure(code, msg, requirement_id=req.id, facts=facts), None

    hits = select(req, state)
    if not hits:
        return fl("requirement_unmatched", f"no fact matches {_describe(req)}")
    if len(hits) > 1:
        return fl("requirement_ambiguous", f"{_describe(req)} matches {len(hits)} facts; "
                  "a requirement must identify exactly one", tuple(f.id for f in hits))
    f = hits[0]
    if f.status == "target":
        return fl("requirement_not_reached", f"target {f.id!r} was never derived", (f.id,))
    if f.status == "unknown":
        return fl("requirement_unknown", f"{f.id!r} is unknown: {f.why_unknown}", (f.id,))
    if req.predicate == "exists":
        return None, f
    why: str | None
    if req.predicate == "equals":
        if "value" not in req.args:
            return fl("requirement_failed", "equals needs args.value", (f.id,))
        expected = replace(f, value=req.args["value"], unit=req.args.get("unit", f.unit))
        why = None if facts_equal(pack, f, expected) else (
            f"{f.id!r} is {_show(f)}, required {_show(expected)}")
    elif req.predicate in pack.predicates:
        try:
            why = pack.predicates[req.predicate](f, req.args)
        except Exception as exc:  # fail closed
            why = f"predicate raised {type(exc).__name__}: {exc}"
    else:
        return fl("unknown_predicate", f"predicate {req.predicate!r} is not built in or "
                  f"registered by pack {pack.name!r}")
    if why:
        return fl("requirement_failed", f"{req.predicate}: {why}", (f.id,))
    return None, f


def _describe(req: Requirement) -> str:
    parts = ([f"id={req.selector.fact_id!r}"] if req.selector.fact_id else []) + [
        f"{k}={v!r}" for k, v in req.selector.where.items()]
    return f"requirement {req.id!r} ({', '.join(parts) or 'any fact'})"


def _collect_support(
    fact_id: str, producer: Mapping[str, str], steps: Mapping[str, Step], failed: set[str],
    initial: Mapping[str, Fact], support: set[str], unverified: set[str],
) -> None:
    stack = [fact_id]
    seen: set[str] = set()
    while stack:
        fid = stack.pop()
        if fid in seen:
            continue
        seen.add(fid)
        sid = producer.get(fid)
        if sid is not None and sid not in failed:
            support.add(sid)
            stack.extend(steps[sid].inputs.values())
        elif fid in initial and initial[fid].status == "unverified":
            unverified.add(fid)
