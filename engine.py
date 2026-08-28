"""OpenVerifiers — DAG reasoning engine.

Implements ARCHITECTURE.md §2 (induction / deduction) and §3 (DAG, no loops).

Deduction is backward chaining with memoization: to resolve a target fact kind,
find a rule that can produce it, resolve that rule's input kinds recursively, then
fire the rule forward on concrete inputs. Induction is forward closure: apply every
applicable rule until no new fact appears.

Loop guarantees (by construction):
  * deduction carries a `visiting` set of kinds on the current path; a rule whose
    input kind is already being derived on this path is rejected as circular,
  * induction dedups fact identity and never derives a fact that is an ancestor of
    any of its inputs,
  * memoization bounds total work.

Trace policy (ARCHITECTURE.md §4): every derive, reject, dead end, join, and
unknown is appended to one verbose store. Render views project from that store.
"""

from __future__ import annotations

from typing import Optional

from .model import (
    Fact, Transformation, VerificationResult,
    TRUTH, UNVERIFIED_TRUTH, DERIVED, TARGET, UNKNOWN,
)
from .solvers import get_solver


# ---------------------------------------------------------------------------
# trace events
# ---------------------------------------------------------------------------
def ev_derive(fact: Fact, rule: str, inputs: list[Fact]) -> dict:
    return {"type": "derive", "fact_id": fact.id, "fact_value": str(fact.value),
            "rule": rule, "inputs": [f.id for f in inputs]}


def ev_reject(rule: str, inputs: list[Fact], reason: str) -> dict:
    return {"type": "reject", "rule": rule, "inputs": [f.id for f in inputs], "reason": reason}


def ev_deadend(kind: str, reason: str) -> dict:
    return {"type": "deadend", "fact_kind": kind, "reason": reason}


def ev_join(fact_id: str, sources: list[str]) -> dict:
    return {"type": "join", "fact_id": fact_id, "sources": sources}


def ev_unknown(fact_id: str, reason: str, evidence: str = "") -> dict:
    return {"type": "unknown", "fact_id": fact_id, "reason": reason, "evidence": evidence}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class Engine:
    def __init__(self, rules: list[Transformation]):
        self.rules = rules
        self.trace: list[dict] = []
        self._facts: dict[str, Fact] = {}
        self._parents: dict[str, set[str]] = {}  # output id -> input ids
        self._children: dict[str, set[str]] = {}
        self._memo: dict[str, Optional[Fact]] = {}

        # index rules by output kind
        self._by_kind: dict[str, list[Transformation]] = {}
        for r in rules:
            self._by_kind.setdefault(r.output_kind, []).append(r)

    # -- bookkeeping --------------------------------------------------------
    def add_fact(self, fact: Fact) -> Fact:
        existing = self._facts.get(fact.id)
        if existing is not None:
            return existing
        self._facts[fact.id] = fact
        self._parents.setdefault(fact.id, set())
        self._children.setdefault(fact.id, set())
        return fact

    def _record_derive(self, out: Fact, inputs: list[Fact], rule: str) -> None:
        for f in inputs:
            self._children.setdefault(f.id, set()).add(out.id)
        self._parents.setdefault(out.id, set()).update(f.id for f in inputs)
        self.trace.append(ev_derive(out, rule, inputs))

    # -- deduction -----------------------------------------------------------
    def deduce(self, givens: list[Fact], target: Fact, max_depth: int = 10) -> VerificationResult:
        for g in givens:
            self.add_fact(g)

        # reset memo each run
        self._memo = {}
        got = self._derive_kind(target.attributes.get("fact_kind", ""), target, set(), 0, max_depth)

        if got is not None:
            self.trace.append(ev_derive(got, "TARGET-REACHED", [f for f in givens if f.id in self._parents.get(got.id, set())]))
            return self._result("RESOLVED", got.value, got.id)

        reason = "no rule could derive the target from available givens"
        self.trace.append(ev_unknown(target.id, reason, "add a missing given or rule"))
        return self._result(UNKNOWN, None, target.id)

    def _derive_kind(self, kind: str, target: Fact, visiting: set, depth: int, max_depth: int) -> Optional[Fact]:
        """Backward: resolve a fact of `kind`. Returns a derived/known fact or None.

        visiting: kinds on the current path (loop guard)."""
        if kind in visiting:
            self.trace.append(ev_reject("(recursion)", [], f"circular: kind {kind} already on path"))
            return None
        if depth > max_depth:
            self.trace.append(ev_deadend(kind, "max depth exceeded"))
            return None
        memo = self._memo.get(kind)
        if memo is not None:
            return memo
        if kind in self._memo:  # memoized failure
            return None

        # 1. already-known facts of this kind with a value
        known = [f for f in self._facts.values()
                 if f.attributes.get("fact_kind") == kind and f.value is not None
                 and f.status in (TRUTH, UNVERIFIED_TRUTH, DERIVED)]
        if known:
            if len(known) > 1:
                self.trace.append(ev_join(kind, [f.id for f in known]))
            self._memo[kind] = known[0]
            return known[0]

        # 2. try rules that produce this kind
        for rule in self._by_kind.get(kind, []):
            if not rule.input_kinds:
                continue
            sub = set(visiting)
            sub.add(kind)
            inputs: list[Fact] = []
            ok = True
            for ik in rule.input_kinds:
                f = self._derive_kind(ik, target, sub, depth + 1, max_depth)
                if f is None:
                    self.trace.append(ev_deadend(ik, f"needed for rule {rule.name}"))
                    ok = False
                    break
                inputs.append(f)
            if not ok:
                continue

            reason = rule.precond(inputs)
            if reason:
                self.trace.append(ev_reject(rule.name, inputs, reason))
                continue

            try:
                out_fact, _note = rule.apply(inputs)
            except Exception as exc:
                self.trace.append(ev_reject(rule.name, inputs, f"relation error: {exc}"))
                continue

            # loop guard: out must not be ancestor of any input
            out_anc = set().union(*[self._ancestors(f.id) for f in inputs]) if inputs else set()
            if out_fact.id in out_anc and inputs:
                self.trace.append(ev_reject(rule.name, inputs, f"circular: {out_fact.id} in ancestors of inputs"))
                continue

            self.add_fact(out_fact)
            self._record_derive(out_fact, inputs, rule.name)
            self._memo[kind] = out_fact
            return out_fact

        self._memo[kind] = None
        self.trace.append(ev_deadend(kind, "no rule or known fact"))
        return None

    def _ancestors(self, fact_id: str) -> set:
        out = set()
        stack = list(self._parents.get(fact_id, set()))
        while stack:
            n = stack.pop()
            if n in out:
                continue
            out.add(n)
            stack.extend(self._parents.get(n, set()))
        return out

    # -- induction ------------------------------------------------------------
    def induce(self, givens: list[Fact], target_id: str, max_rounds: int = 8) -> VerificationResult:
        for g in givens:
            self.add_fact(g)
        frontier = list(self._facts.values())
        applied = set()

        for _ in range(max_rounds):
            produced = False
            new_derived: list[Fact] = []
            for rule in self.rules:
                for subset in self._combos(frontier, rule.input_kinds):
                    key = (rule.name, tuple(sorted(f.id for f in subset)))
                    if key in applied:
                        continue
                    applied.add(key)
                    reason = rule.precond(subset)
                    if reason:
                        self.trace.append(ev_reject(rule.name, subset, reason))
                        continue
                    out_anc = set().union(*[self._ancestors(f.id) for f in subset]) if subset else set()
                    try:
                        out_fact, _note = rule.apply(subset)
                    except Exception as exc:
                        self.trace.append(ev_reject(rule.name, subset, f"relation error: {exc}"))
                        continue
                    if path_ok := (out_fact.id not in out_anc):
                        existing = self.add_fact(out_fact)
                        if existing is out_fact:
                            self._record_derive(out_fact, subset, rule.name)
                            new_derived.append(out_fact)
                            produced = True
                        else:
                            self.trace.append(ev_join(existing.id, [f.id for f in subset]))
                        if out_fact.id == target_id:
                            return self._result("RESOLVED", out_fact.value, out_fact.id)
            frontier.extend(new_derived)
            if not produced:
                break

        tf = self._facts.get(target_id)
        if tf is not None and tf.value is not None:
            return self._result("RESOLVED", tf.value, tf.id)
        self.trace.append(ev_unknown(target_id, "no rule produced the target"))
        return self._result(UNKNOWN, None, target_id)

    @staticmethod
    def _combos(facts, kinds):
        """Yield subsets of `facts` shaped like `kinds` (one per kind, in order)."""
        by_kind: dict[str, list[Fact]] = {}
        for f in facts:
            k = f.attributes.get("fact_kind")
            by_kind.setdefault(k, []).append(f)
        lists = [ [f for f in facts if f.attributes.get("fact_kind") == k] for k in kinds ]
        if not all(lists):
            return
        def rec(i, acc):
            if i == len(kinds):
                yield list(acc)
                return
            for f in lists[i]:
                yield from rec(i + 1, acc + [f])
        yield from rec(0, [])

    # -- result ---------------------------------------------------------------
    def _result(self, status: str, answer, target_id: str) -> VerificationResult:
        from .trace import build_views
        success, failure, full = build_views(self.trace, target_id, answer)
        return VerificationResult(target=target_id, status=status, answer=answer,
                                  success_path=success, failure_trail=failure, full=full)