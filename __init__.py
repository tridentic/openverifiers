"""OpenVerifiers — SDK entry points.

Public surface (ARCHITECTURE.md §7.1):
    Engine, Fact, Transformation, VerificationResult
    verify_physics(problem) -> VerificationResult   (domain driver)
    get_physics_rules(), parse_problem()
"""

from __future__ import annotations

from .model import Fact, Transformation, VerificationResult, Unknown
from .engine import Engine
from .trace import render_view

__all__ = [
    "Engine", "Fact", "Transformation", "VerificationResult", "Unknown",
    "verify_physics", "render_view",
    "get_physics_rules", "parse_problem",
]

# --- domain driver --------------------------------------------------------
def get_physics_rules():
    from .grammars.physics import build_physics_rules
    return build_physics_rules()


def parse_problem(text: str, explicit=None, explicit_target=None):
    from .grammars.input import parse_problem as _p
    return _p(text, explicit=explicit, explicit_target=explicit_target)


def verify_physics(problem: str, *, explicit=None, explicit_target: str | None = None,
                   view: str = "success-path") -> VerificationResult:
    """Full pipeline: extract -> deduce -> trace views.

    Returns a VerificationResult (status, answer, success_path, failure_trail, full).
    """
    givens, target_kind = parse_problem(problem, explicit=explicit, explicit_target=explicit_target)
    if target_kind is None:
        # no target identifiable — treat as unresolved-unknown
        from .model import TARGET
        from .grammars.physics import KIND_META
        fake = Fact(id="?target", value=None, status=TARGET,
                    attributes={"fact_kind": ""}, source="?")
        from .trace import build_views
        from .model import VerificationResult
        return VerificationResult(target="?", status="UNKNOWN", answer=None,
                                  success_path=[{"type": "unknown", "fact_id": "target",
                                                 "reason": "no target kind identified in problem",
                                                 "evidence": "phrase your target as 'find the "
                                                             "<quantity>"}],
                                  failure_trail=[], full=[])

    engine = Engine(get_physics_rules())
    from .grammars.input import make_target_fact
    target = make_target_fact(target_kind)
    result = engine.deduce(givens, target)
    return result