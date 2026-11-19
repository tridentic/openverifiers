"""Two search proposers built only on a pack's own transformations.

* ``ForwardChainer`` (induction, facts -> target): repeatedly applies every
  transformation whose preconditions hold to the facts known so far, until
  the requirements are met or nothing new can be derived.
* ``BackwardDecomposer`` (deduction, target -> subgoals): starts from each
  target slot, picks a transformation that outputs it, and recursively
  turns that transformation's inputs into subgoals.

Both bind roles to facts by name: a fact fills role ``r`` when its
``attributes.symbol`` (or its id) is ``r``; if no fact is named ``r``, any
fact of the right type may fill it. Both only use transformations with an
effect (they cannot invent the output of a soft or grounded step), and both
prune the result to the steps the requirements actually depend on.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from openverifiers.m1.kernel import DomainPack, Fact, Proof, Requirement, Step, check

from .base import Feedback, ProposalError, apply, established, prune, symbol_of, target_slot


def _candidates(known: dict[str, Fact], role: str, ftype: str) -> list[Fact]:
    typed = [f for f in known.values() if ftype in ("*", f.type)]
    named = [f for f in typed if symbol_of(f) == role]
    return named or typed


@dataclass
class ForwardChainer:
    """Breadth-first forward chaining with cheap guards against blow-up: a
    step is only kept if it derives a symbol not already known, and each
    round tries transformations that fill a declared target first, then
    those whose every input role names a known fact, then the rest (so plain
    arithmetic over arbitrary pairs is a fallback, not the first move)."""

    max_rounds: int = 4
    max_steps: int = 60

    def propose(self, state: Sequence[Fact], requirements: Sequence[Requirement],
                domain_pack: DomainPack, feedback: Feedback | None = None) -> Proof:
        known = established(state)
        steps: list[Step] = []
        tried: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
        wanted = {symbol_of(f) for f in state if f.status == "target"}
        for _ in range(self.max_rounds):
            if check(state, requirements, Proof(tuple(steps)), domain_pack).valid:
                break
            names = {symbol_of(f) for f in known.values()}
            # most specific first: fills a target, then every input has a named fact
            ordered = sorted(domain_pack.transformations.values(),
                             key=lambda t: (not set(t.outputs) & wanted,
                                            not set(t.inputs) <= names, t.id))
            grew = False
            for t in ordered:
                if t.effect is None or len(steps) >= self.max_steps:
                    continue
                roles = sorted(t.inputs)
                pools = [_candidates(known, r, t.inputs[r]) for r in roles]
                for combo in itertools.product(*pools):
                    sig = (t.id, tuple(zip(roles, (f.id for f in combo), strict=True)))
                    if sig in tried or len(steps) >= self.max_steps:
                        continue
                    tried.add(sig)
                    n = len(steps) + 1
                    ids = {r: target_slot(state, r, ft) or f"{r}_{n}"
                           for r, ft in t.outputs.items()}
                    if any(i in known for i in ids.values()):
                        ids = {r: f"{r}_{n}" for r in t.outputs}
                    step = apply(domain_pack, t.id, dict(zip(roles, combo, strict=True)), ids)
                    known_symbols = {symbol_of(f) for f in known.values()}
                    if step is None or all(
                            "symbol" in f.attributes and symbol_of(f) in known_symbols
                            for f in step.outputs.values()):
                        continue
                    step = Step(f"s{n}", step.transformation, step.inputs, step.outputs)
                    steps.append(step)
                    known.update({f.id: f for f in step.outputs.values()})
                    grew = True
                if grew and set(t.outputs) & wanted:
                    break  # re-check the goal before trying lower-priority rules
            if not grew:
                break
        if not steps:
            raise ProposalError("forward chaining derived nothing")
        return prune(state, requirements, domain_pack, steps)


@dataclass
class BackwardDecomposer:
    max_depth: int = 4

    def propose(self, state: Sequence[Fact], requirements: Sequence[Requirement],
                domain_pack: DomainPack, feedback: Feedback | None = None) -> Proof:
        known = established(state)
        steps: list[Step] = []
        slots = {f.id: f for f in state if f.status == "target"}
        goals = [slots[r.selector.fact_id] for r in requirements
                 if r.selector.fact_id in slots]
        if not goals:
            raise ProposalError("no requirement points at a declared target fact")

        def solve(symbol: str, ftype: str, depth: int, out_id: str | None,
                  open_goals: frozenset[str]) -> str | None:
            if out_id is None:
                hit = next((f for f in known.values()
                            if symbol_of(f) == symbol and ftype in ("*", f.type)), None)
                if hit is not None:
                    return hit.id
            if depth > self.max_depth or symbol in open_goals:
                return None
            for tid in sorted(domain_pack.transformations):
                t = domain_pack.transformations[tid]
                if t.effect is None or symbol not in t.outputs:
                    continue
                if ftype not in ("*", t.outputs[symbol]) or set(t.inputs) & open_goals:
                    continue
                bound: dict[str, Fact] = {}
                for role in sorted(t.inputs):
                    rid = solve(role, t.inputs[role], depth + 1, None, open_goals | {symbol})
                    if rid is None:
                        break
                    bound[role] = known[rid]
                else:
                    n = len(steps) + 1
                    ids = {r: (out_id if r == symbol and out_id else f"{r}_{n}")
                           for r in t.outputs}
                    step = apply(domain_pack, tid, bound, ids)
                    if step is None:
                        continue
                    steps.append(Step(f"s{n}", tid, step.inputs, step.outputs))
                    known.update({f.id: f for f in step.outputs.values()})
                    return ids[symbol]
            return None

        for g in goals:
            if solve(symbol_of(g), g.type, 0, g.id, frozenset()) is None:
                raise ProposalError(f"no decomposition reaches target {g.id!r}")
        return prune(state, requirements, domain_pack, steps)
