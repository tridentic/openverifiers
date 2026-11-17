"""Repair-loop demo: a (scripted) model proposes a proof with a sign error,
the kernel rejects it with structured reasons, the model's second proof is
accepted. Run with ``ov demo repair``.

The model is ``ScriptedModel``: its two replies are fixed in advance. What
the demo shows is the loop and the feedback, not model quality. The demo
asserts that the second prompt actually carried the kernel's failures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openverifiers.case import load_case
from openverifiers.domains import load
from openverifiers.proposers import LLMProposer, RepairResult, ScriptedModel, repair

CASE = Path(__file__).resolve().parents[1] / "benchmarks" / "cases" / "math" / \
    "math_braking_force.json"


def _reply(a: float, force: float) -> str:
    steps = [
        {"id": "s1", "transformation": "kinematics.velocity.solve_a",
         "inputs": {"v": "v", "u": "u", "t": "t"},
         "outputs": {"a": {"id": "a", "type": "quantity", "value": a, "unit": "m/s^2",
                           "attributes": {"symbol": "a"}}}},
        {"id": "s2", "transformation": "dynamics.newton2.solve_F",
         "inputs": {"m": "m", "a": "a"},
         "outputs": {"F": {"id": "F", "type": "quantity", "value": force, "unit": "N",
                           "attributes": {"symbol": "F"}}}},
    ]
    return "```json\n" + json.dumps({"steps": steps}) + "\n```"


def run_repair_demo(log_path: str | None = None) -> tuple[RepairResult, list[str]]:
    case = load_case(CASE)
    pack = load(case.domain)
    # attempt 1 forgets that braking makes acceleration negative
    model = ScriptedModel([_reply(5.0, 6000.0), _reply(-5.0, -6000.0)])
    records: list[dict[str, Any]] = []
    result = repair(LLMProposer(model), case.facts, case.requirements, pack,
                    max_attempts=3, log=records.append)
    if log_path:
        Path(log_path).write_text("".join(json.dumps(r) + "\n" for r in records))
    lines = [f"Case: {case.description}", ""]
    for att in result.attempts:
        v = att.verdict
        assert v is not None
        lines.append(f"Attempt {att.number}: valid={v.valid} trust_grade={v.trust_grade}")
        for f in v.failures:
            where = f"step {f.step_id}" if f.step_id else f"requirement {f.requirement_id}"
            lines.append(f"  - {f.code} at {where}: {f.message}")
    fed_back = len(model.prompts) > 1 and "output_mismatch" in model.prompts[1] \
        and '"step_id": "s1"' in model.prompts[1]
    lines += ["", f"Second prompt carried the kernel's structured failures: {fed_back}",
              f"Accepted after {len(result.attempts)} attempt(s): {result.accepted}"]
    return result, lines
