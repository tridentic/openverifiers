"""OpenVerifiers — declared-path engine. No search.

The engine runs Transformations that controllers produced, in the order and
with the inputs the caller declared. It records a JSON-auditable trace and
never searches a registry for alternate ways to reach a target — there is no
registry and no target-matching logic here by construction.
"""

from __future__ import annotations

from typing import Any

from .model import Transformation, VerificationResult


def _unit_token(unit) -> str:
    from .domains.units_si import (Meter, Kilogram, Second, MeterPerSecond,
                                   MeterPerSecondSquared, Newton, Joule,
                                   KilogramMeterPerSecond)
    table = {Meter(): "m", Kilogram(): "kg", Second(): "s",
             MeterPerSecond(): "m/s", MeterPerSecondSquared(): "m/s^2",
             Newton(): "N", Joule(): "J", KilogramMeterPerSecond(): "kg m/s"}
    return table.get(unit, str(unit.dimension))


def _fmt(value: Any) -> str:
    return str(value)


class Engine:
    """Runs one Transformation (or an explicit chain) over declared inputs."""

    def run(self, transformation: Transformation, inputs: dict,
            target: str = "?") -> VerificationResult:
        trace: list[dict] = []
        reason = transformation.precond(inputs)
        if reason:
            trace.append({"type": "reject", "rule": transformation.name,
                          "reason": reason, "inputs": sorted(inputs)})
            return VerificationResult(target, "UNRESOLVED", None, trace)
        try:
            out = transformation.apply(inputs)
        except Exception as exc:  # noqa: BLE001
            trace.append({"type": "reject", "rule": transformation.name,
                          "reason": f"relation error: {exc}",
                          "inputs": sorted(inputs)})
            return VerificationResult(target, "UNRESOLVED", None, trace)
        trace.append({"type": "derive", "rule": transformation.name,
                      "fact_id": out.id, "value": _fmt(out.value),
                      "unit": getattr(out, "unit", None) and _unit_token(out.unit) or "",
                      "inputs": sorted(inputs)})
        return VerificationResult(target, "RESOLVED", out, trace)

    def run_chain(self, steps: list[tuple[Transformation, dict]],
                  target: str = "?") -> VerificationResult:
        """Run an explicitly declared chain in order; first failure stops."""
        trace: list[dict] = []
        for transformation, inputs in steps:
            result = self.run(transformation, inputs, target=target)
            trace.extend(result.trace)
            if result.status != "RESOLVED":
                return VerificationResult(target, "UNRESOLVED", None, trace)
        return VerificationResult(target, "RESOLVED", result.answer, trace)