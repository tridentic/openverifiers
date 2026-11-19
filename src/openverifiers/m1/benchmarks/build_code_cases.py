"""Rebuild benchmarks/cases/code_requirements/*.json from benchmarks/sources/.

The JSON cases embed the solution and check sources; edit the ``.py`` files
in ``sources/`` and rerun:  python -m openverifiers.m1.benchmarks.build_code_cases
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources"
OUT = ROOT / "cases" / "code_requirements"

SPECS: dict[str, dict[str, str]] = {
    "parse_duration": {
        "R1": "single units: '90s' -> 90, '5m' -> 300, '2h' -> 7200",
        "R2": "combined units in h, m, s order: '1h30m' -> 5400",
        "R3": "malformed input (empty, no unit, unknown unit, wrong order, spaces, "
              "repeats) raises ValueError",
        "R4": "for any h, m, s in 0..99, formatting then parsing returns 3600h + 60m + s",
    },
    "clamp": {
        "R1": "a value inside [lo, hi] is returned unchanged",
        "R2": "a value outside the range returns the nearer bound",
        "R3": "lo > hi raises ValueError",
        "R4": "for any integers, the result lies within [lo, hi]",
    },
}


def build(fn: str, reqs: dict[str, str]) -> dict[str, Any]:
    tests = (SOURCES / f"{fn}_checks.py").read_text()
    solution = (SOURCES / f"{fn}_solution.py").read_text()
    report = {"passed": True, "results": dict.fromkeys(reqs, "passed")}
    return {
        "id": f"code_{fn}",
        "domain": "code_requirements",
        "description": f"Implement {fn} satisfying {len(reqs)} requirements",
        "facts": [
            {"id": "spec", "type": "spec", "value": {"function": fn, "requirements": reqs}},
            {"id": "checks", "type": "check_suite", "value": {"tests": tests}},
            {"id": "report", "type": "check_report", "status": "target"},
        ],
        "requirements": [{"id": "all", "fact_id": "report", "predicate": "all_checks_pass"}] + [
            {"id": r, "fact_id": "report", "predicate": "requirement_passes",
             "args": {"requirement": r}} for r in reqs],
        "candidate_proof": {"steps": [
            {"id": "s1", "transformation": "code.implement", "inputs": {"spec": "spec"},
             "outputs": {"source": {"id": "impl", "type": "source", "value": solution}}},
            {"id": "s2", "transformation": "code.run_checks",
             "inputs": {"spec": "spec", "source": "impl", "checks": "checks"},
             "outputs": {"report": {"id": "report", "type": "check_report", "value": report}}},
        ]},
        "expected_verdict": {"valid": True, "trust_grade": "fully_hard"},
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in SPECS.items():
        (OUT / f"code_{name}.json").write_text(json.dumps(build(name, spec), indent=2) + "\n")
