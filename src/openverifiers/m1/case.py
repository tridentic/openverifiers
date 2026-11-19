"""Case files: one JSON document holding a full verification problem.

    {
      "id": "car_distance",
      "domain": "math",                      # a name in openverifiers.m1.domains.PACKS
      "description": "...",                  # optional
      "facts": [ <fact>, ... ],
      "requirements": [ <requirement>, ... ],
      "candidate_proof": {"steps": [ <step>, ... ]},
      "expected_verdict": {"valid": true, "trust_grade": "fully_hard",
                           "failure_codes": [...]}   # optional, for benchmarks
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openverifiers.m1.kernel import (
    Fact,
    FormatError,
    Proof,
    Requirement,
    fact_from_dict,
    fact_to_dict,
    proof_from_dict,
    proof_to_dict,
    requirement_from_dict,
    requirement_to_dict,
)

_KEYS = {"id", "domain", "description", "facts", "requirements", "candidate_proof",
         "expected_verdict"}


@dataclass(frozen=True)
class Case:
    id: str
    domain: str
    facts: tuple[Fact, ...]
    requirements: tuple[Requirement, ...]
    proof: Proof
    expected: dict[str, Any] = field(default_factory=dict)
    description: str = ""


def case_from_dict(d: Any) -> Case:
    if not isinstance(d, dict):
        raise FormatError("case: expected an object")
    if missing := {"id", "domain", "facts", "requirements", "candidate_proof"} - set(d):
        raise FormatError(f"case: missing keys {sorted(missing)}")
    if extra := set(d) - _KEYS:
        raise FormatError(f"case: unknown keys {sorted(extra)}")
    return Case(
        id=d["id"], domain=d["domain"], description=d.get("description", ""),
        facts=tuple(fact_from_dict(f, f"facts[{i}]") for i, f in enumerate(d["facts"])),
        requirements=tuple(requirement_from_dict(r, f"requirements[{i}]")
                           for i, r in enumerate(d["requirements"])),
        proof=proof_from_dict(d["candidate_proof"]),
        expected=dict(d.get("expected_verdict", {})),
    )


def case_to_dict(c: Case) -> dict[str, Any]:
    d: dict[str, Any] = {"id": c.id, "domain": c.domain}
    if c.description:
        d["description"] = c.description
    d["facts"] = [fact_to_dict(f) for f in c.facts]
    d["requirements"] = [requirement_to_dict(r) for r in c.requirements]
    d["candidate_proof"] = proof_to_dict(c.proof)
    if c.expected:
        d["expected_verdict"] = c.expected
    return d


def load_case(path: str | Path) -> Case:
    return case_from_dict(json.loads(Path(path).read_text()))
