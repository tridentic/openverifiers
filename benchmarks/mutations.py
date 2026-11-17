"""Corrupt valid proofs in labeled ways.

Every operator works on the JSON-level case (facts, requirements, steps), so
it is domain-agnostic. Value perturbations (``sign_error``, ``wrong_effect``)
ask a per-domain hook how to corrupt a fact's value; a domain without a hook
for a fact type simply yields no mutant of that kind ("n/a" in the report).

Each mutant records which failure codes count as the *right diagnosis*, so
the benchmark can report "caught for the right reason" separately from
"caught".
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from typing import Any

from openverifiers.case import Case
from openverifiers.domains.math import units
from openverifiers.kernel import DomainPack, Fact, Proof, Requirement, Selector, Step

MUTATIONS = (
    "unit_mismatch",
    "sign_error",
    "dropped_step",
    "missing_precondition",
    "wrong_effect",
    "unreachable_target",
    "duplicated_fact_id",
    "circular_dependency",
    "misread_given",
)

# Failure codes that count as diagnosing each mutation correctly.
EXPECTED_CODES: dict[str, frozenset[str]] = {
    "unit_mismatch": frozenset({"precondition_failed", "output_mismatch", "checker_rejected"}),
    "sign_error": frozenset({"output_mismatch", "checker_rejected"}),
    "dropped_step": frozenset({"missing_input", "requirement_not_reached",
                               "requirement_unmatched"}),
    "missing_precondition": frozenset({"missing_input"}),
    "wrong_effect": frozenset({"output_mismatch", "checker_rejected"}),
    "unreachable_target": frozenset({"requirement_not_reached", "requirement_unmatched"}),
    "duplicated_fact_id": frozenset({"duplicate_fact_id"}),
    "circular_dependency": frozenset({"cycle"}),
    "misread_given": frozenset({"requirement_failed"}),
}

# fact type -> value perturbation (None when it cannot be perturbed)
Perturb = Callable[[Fact], Any]


@dataclass(frozen=True)
class Mutant:
    case: Case
    base_id: str
    kind: str
    note: str

    @property
    def expected_codes(self) -> frozenset[str]:
        return EXPECTED_CODES[self.kind]


def _with_steps(c: Case, steps: list[Step]) -> Case:
    return replace(c, proof=Proof(tuple(steps)))


def _consumers(c: Case) -> dict[str, list[Step]]:
    out: dict[str, list[Step]] = {}
    for s in c.proof.steps:
        for ref in s.inputs.values():
            out.setdefault(ref, []).append(s)
    return out


def _replace_output(s: Step, role: str, f: Fact) -> Step:
    return replace(s, outputs={**s.outputs, role: f})


def unit_mismatch(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    used = _consumers(c)
    for f in c.facts:
        if f.id in used and f.unit not in (None, "1"):
            dim = units.dimension(f.unit)
            other = next(u for u in ("kg", "s", "m") if units.dimension(u) != dim)
            facts = tuple(replace(g, unit=other) if g.id == f.id else g for g in c.facts)
            yield replace(c, facts=facts), f"unit of {f.id} {f.unit!r} -> {other!r}"


def sign_error(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    for i, s in enumerate(c.proof.steps):
        for role, f in s.outputs.items():
            if isinstance(f.value, int | float) and not isinstance(f.value, bool) and f.value:
                steps = list(c.proof.steps)
                steps[i] = _replace_output(s, role, replace(f, value=-f.value))
                yield _with_steps(c, steps), f"negated {f.id} in {s.id}"


def wrong_effect(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    if perturb is None:
        return
    for i, s in enumerate(c.proof.steps):
        for role, f in s.outputs.items():
            new = perturb(f)
            if new is not None and new != f.value:
                steps = list(c.proof.steps)
                steps[i] = _replace_output(s, role, replace(f, value=new))
                yield _with_steps(c, steps), f"changed claimed {f.id} in {s.id}"


def dropped_step(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    used = _consumers(c)
    targets = {r.selector.fact_id for r in c.requirements}
    for s in c.proof.steps:
        outs = {f.id for f in s.outputs.values()}
        if outs & (set(used) | targets):
            yield _with_steps(c, [t for t in c.proof.steps if t.id != s.id]), f"dropped {s.id}"


def missing_precondition(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    used = _consumers(c)
    for f in c.facts:
        if f.id in used:
            facts = tuple(g for g in c.facts if g.id != f.id)
            yield replace(c, facts=facts), f"removed premise {f.id} used by {used[f.id][0].id}"


def unreachable_target(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    for i, r in enumerate(c.requirements):
        if r.selector.fact_id is not None:
            ghost = f"{r.selector.fact_id}__unreached"
            sel = Selector(ghost)
        else:
            k = next(iter(r.selector.where))
            ghost = f"{r.selector.where[k]}__unreached"
            sel = Selector(where={**r.selector.where, k: ghost})
        reqs = list(c.requirements)
        reqs[i] = Requirement(r.id, sel, r.predicate, r.args)
        yield replace(c, requirements=tuple(reqs)), f"requirement {r.id} now asks for {ghost}"


def duplicated_fact_id(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    established = [f for f in c.facts if f.status not in ("target", "unknown")]
    if not established:
        return
    for i, s in enumerate(c.proof.steps):
        role, f = next(iter(s.outputs.items()))
        steps = list(c.proof.steps)
        steps[i] = _replace_output(s, role, replace(f, id=established[0].id))
        yield _with_steps(c, steps), f"{s.id} output renamed to existing {established[0].id}"


def circular_dependency(c: Case, perturb: Perturb | None) -> Iterator[tuple[Case, str]]:
    steps = list(c.proof.steps)
    producer = {f.id: s for s in steps for f in s.outputs.values()}
    for s in steps:
        for ref in s.inputs.values():
            if ref in producer:  # s depends on producer[ref]; make producer depend on s
                p = producer[ref]
                j = steps.index(p)
                if not p.inputs:
                    continue
                prole = next(iter(p.inputs))
                back = next(iter(s.outputs.values())).id
                steps2 = list(steps)
                steps2[j] = replace(p, inputs={**p.inputs, prole: back})
                yield _with_steps(c, steps2), f"{p.id}.{prole} now reads {back} from {s.id}"
                return
    for i, s in enumerate(steps):  # no dependent pair: make a step read its own output
        if s.inputs:
            role = next(iter(s.inputs))
            own = next(iter(s.outputs.values())).id
            steps2 = list(steps)
            steps2[i] = replace(s, inputs={**s.inputs, role: own})
            yield _with_steps(c, steps2), f"{s.id}.{role} now reads its own output {own}"
            return


def misread_given(c: Case, perturb: Perturb | None,
                  pack: DomainPack | None = None) -> Iterator[tuple[Case, str]]:
    """Beyond the eight requested labels: a proposer misreads one given number
    and then reasons *correctly* from it, so every step is internally valid.
    Only a requirement that pins the answer can catch this."""
    if perturb is None or pack is None:
        return
    used = _consumers(c)
    for f in c.facts:
        new = perturb(f) if f.id in used and f.status == "truth" else None
        if new is None:
            continue
        facts = tuple(replace(g, value=new) if g.id == f.id else g for g in c.facts)
        values = {g.id: g for g in facts}
        steps: list[Step] = []
        for s in c.proof.steps:  # base cases list steps in dependency order
            t = pack.transformations[s.transformation]
            outs = dict(s.outputs)
            if t.effect is not None:
                try:
                    fresh = t.effect({r: values[ref] for r, ref in s.inputs.items()}, s.params)
                except Exception:
                    break
                outs = {r: replace(fresh[r], id=o.id, attributes=o.attributes)
                        for r, o in s.outputs.items()}
            values.update({o.id: o for o in outs.values()})
            steps.append(replace(s, outputs=outs))
        else:
            yield replace(c, facts=facts, proof=Proof(tuple(steps))), (
                f"given {f.id} {f.value} -> {new}, rest recomputed consistently")


OPERATORS: dict[str, Callable[[Case, Perturb | None], Iterator[tuple[Case, str]]]] = {
    "unit_mismatch": unit_mismatch,
    "sign_error": sign_error,
    "dropped_step": dropped_step,
    "missing_precondition": missing_precondition,
    "wrong_effect": wrong_effect,
    "unreachable_target": unreachable_target,
    "duplicated_fact_id": duplicated_fact_id,
    "circular_dependency": circular_dependency,
}


def mutate(c: Case, perturb: Perturb | None = None,
           pack: DomainPack | None = None) -> list[Mutant]:
    """All labeled mutants of a valid case."""
    out: list[Mutant] = []
    for kind in MUTATIONS:
        ops = (misread_given(c, perturb, pack) if kind == "misread_given"
               else OPERATORS[kind](c, perturb))
        for n, (mc, note) in enumerate(ops):
            mid = f"{c.id}~{kind}~{n}"
            out.append(Mutant(replace(mc, id=mid, expected={"valid": False}), c.id, kind, note))
    return out
