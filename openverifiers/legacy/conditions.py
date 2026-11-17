"""OpenVerifiers — generic condition evaluation (core, domain-agnostic).

The pass/fail/inapplicable condition engine. This module contains ZERO domain
content: predicates are opaque callables `(performed, candidate) -> (verdict,
reason)` operating over whatever the domain supplies. `domains.coding` builds
on this; a formal-logic or contract domain builds on this too — the engine is
core, not trapped in a domain module.
"""

from __future__ import annotations

from typing import Callable, Optional

PASS = "pass"
FAIL = "fail"
INAPPLICABLE = "inapplicable"

VERDICTS = (PASS, FAIL, INAPPLICABLE)

Condition = Callable[[tuple, object], Optional[tuple[str, str]]]


def aggregate(verdicts: list[str]) -> str:
    """fail > inapplicable > pass over a list of verdict strings."""
    if FAIL in verdicts:
        return FAIL
    if INAPPLICABLE in verdicts:
        return INAPPLICABLE
    return PASS


def apply_conditions(conditions, performed, act) -> list[tuple[str, str, str]]:
    """Evaluate every condition against one proposed candidate.

    Returns [(condition_name, verdict, reason), ...] for applicable
    conditions. `performed` is the domain's executed-context; `act` the
    candidate being checked — both opaque to this engine.
    """
    out = []
    for name, fn in conditions:
        result = fn(performed, act)
        if result is None:
            continue
        verdict, reason = result
        out.append((name, verdict, reason))
    return out