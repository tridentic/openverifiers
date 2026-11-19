"""The proposer interface. Proposers are untrusted: anything they return is
checked by the kernel, so they may use heuristics, search, or a model."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from openverifiers.m1.kernel import DomainPack, Fact, Failure, Proof, Requirement, Step, check


@dataclass(frozen=True)
class Feedback:
    """What the kernel said about the previous attempt."""

    attempt: int
    failures: tuple[Failure, ...]


class ProposalError(Exception):
    """The proposer could not produce a proof (e.g. unparseable model output)."""


class Proposer(Protocol):
    def propose(
        self,
        state: Sequence[Fact],
        requirements: Sequence[Requirement],
        domain_pack: DomainPack,
        feedback: Feedback | None = None,
    ) -> Proof: ...


def established(facts: Iterable[Fact]) -> dict[str, Fact]:
    return {f.id: f for f in facts if f.status in ("truth", "unverified", "derived")}


def symbol_of(f: Fact) -> str:
    sym = f.attributes.get("symbol")
    return sym if isinstance(sym, str) else f.id


def target_slot(facts: Sequence[Fact], role: str, ftype: str) -> str | None:
    """Id of a declared target fact the role naturally fills, if any."""
    for f in facts:
        if f.status == "target" and symbol_of(f) == role and f.type in (ftype, "*"):
            return f.id
    return None


def apply(pack: DomainPack, tid: str, inputs: Mapping[str, Fact],
          ids: Mapping[str, str]) -> Step | None:
    """Run a transformation's preconditions and effect the way a proposer
    would (untrusted: the kernel re-checks). None if it does not apply."""
    t = pack.transformations[tid]
    if t.effect is None:
        return None
    try:
        if any(p.check(inputs, {}) for p in t.preconditions):
            return None
        out = t.effect(inputs, {})
    except Exception:
        return None
    return Step(id="", transformation=tid, inputs={r: f.id for r, f in inputs.items()},
                outputs={r: replace(out[r], id=ids[r]) for r in t.outputs})


def prune(state: Sequence[Fact], requirements: Sequence[Requirement], pack: DomainPack,
          steps: Sequence[Step]) -> Proof:
    """Keep only the steps the requirements depend on (as the kernel sees it)."""
    proof = Proof(tuple(steps))
    support = set(check(state, requirements, proof, pack).support)
    return Proof(tuple(s for s in steps if s.id in support)) if support else proof
