"""OpenVerifiers — coding domain: agent action traces and declared invariants,
expressed as typed data (Action/ActionFact) and plain Python predicates.

This module is the domain content ONLY: every function here takes facts/actions
and returns verdict strings. `ConditionController` (core) wraps these same
predicates without knowing what they mean — the domain-agnostic/domain-content
boundary is the point of the split.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from openverifiers.facts import ActionFact
from openverifiers.conditions import PASS, FAIL, INAPPLICABLE, aggregate
from openverifiers.conditions import apply_conditions as _apply_conditions

Verdict = str              # literally one of PASS/FAIL/INAPPLICABLE
Condition = Callable[[tuple["Action", ...], "Action"], Optional[tuple[str, str]]]


@dataclass(frozen=True)
class Action:
    seq: int
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    pre_facts: tuple[ActionFact, ...] = ()


# -- the four declared invariants (default rule-set) -------------------------

def _has_pre(action: Action, kind: str, of: Any) -> list[ActionFact]:
    return [f for f in action.pre_facts if f.kind == kind and f.of == of]


def auth_before_db_write(performed: tuple[Action, ...], act: Action):
    if act.type != "db_write":
        return None  # condition does not apply to this action type
    if any(a.type == "auth_check" for a in performed):
        return (PASS, "")
    return (FAIL, "auth_check must precede db_write — no auth check executed")


def tests_pass_before_deploy(performed: tuple[Action, ...], act: Action):
    if act.type != "deploy":
        return None
    if any(a.type == "run_tests" and a.params.get("result") == "pass"
           for a in performed):
        return (PASS, "")
    return (FAIL, "run_tests(result=pass) must precede deploy")


def read_before_write_same_file(performed: tuple[Action, ...], act: Action):
    if act.type != "write_file":
        return None
    fname = act.params.get("file")
    if any(a.type == "read_file" and a.params.get("file") == fname
           for a in performed):
        return (PASS, "")
    return (FAIL, f"read_file({fname}) must precede write_file({fname})")


def no_delete_with_active_dependency(performed: tuple[Action, ...], act: Action):
    if act.type != "delete_record":
        return None
    rec = act.params.get("record")
    hits = _has_pre(act, "has_active_dependency", rec)
    if not hits:
        return (PASS, "")  # absent != established (open world: not coerced)
    if any(f.status == "unknown" for f in hits):
        unknown = [f.id for f in hits if f.status == "unknown"]
        return (INAPPLICABLE,
                f"state fact(s) {unknown} for {rec!r} are unknown — cannot "
                f"evaluate without guessing, inapplicable not fail")
    if any(f.value is True for f in hits):
        return (FAIL, f"record {rec!r} has an active dependency")
    return (PASS, "")


def default_conditions() -> list[tuple[str, Condition]]:
    return [
        ("auth_before_db_write", auth_before_db_write),
        ("tests_pass_before_deploy", tests_pass_before_deploy),
        ("read_before_write_same_file", read_before_write_same_file),
        ("no_delete_with_active_dependency", no_delete_with_active_dependency),
    ]


# -- pure application logic (core engine, re-exported for compatibility) -----


def apply_conditions(conditions, performed, act):
    return _apply_conditions(conditions, performed, act)


def check_trace(actions, conditions=None) -> tuple[list[dict], list[dict]]:
    """Check a declared action trace in forward order.

    Returns (per_action, inapplicable_claims). Per-action entries are
    {seq, type, verdict, rule_checks: [(name, verdict, reason)]}."""
    conditions = conditions if conditions is not None else default_conditions()
    per_action = []
    inapplicable: list[dict] = []
    for i, act in enumerate(actions):
        results = apply_conditions(conditions, actions[:i], act)
        verdict = aggregate([r[1] for r in results]) if results else PASS
        for name, vd, reason in results:
            if vd == INAPPLICABLE:
                inapplicable.append({"condition": name, "reason": reason,
                                     "action": act.seq})
        per_action.append({
            "seq": act.seq, "type": act.type, "verdict": verdict,
            "rule_checks": results,
        })
    return per_action, inapplicable