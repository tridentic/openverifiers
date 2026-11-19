from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from openverifiers.m1.case import Case, load_case
from openverifiers.m1.domains import load
from openverifiers.m1.domains.code_requirements import run_suite
from openverifiers.m1.kernel import Proof, Verdict, check
from tests.m1 import M1_CASES

PACK = load("code_requirements")
CASES = M1_CASES / "code_requirements"
CLAMP = load_case(CASES / "code_clamp.json")

NO_RANGE_CHECK = "def clamp(x, lo, hi):\n    return min(max(x, lo), hi)\n"


def with_source(c: Case, source: str, report: dict[str, object] | None = None) -> Case:
    s1, s2 = c.proof.steps
    s1 = replace(s1, outputs={"source": replace(s1.outputs["source"], value=source)})
    if report is not None:
        s2 = replace(s2, outputs={"report": replace(s2.outputs["report"], value=report)})
    return replace(c, proof=Proof((s1, s2)))


def verdict(c: Case) -> Verdict:
    return check(c.facts, c.requirements, c.proof, PACK)


@pytest.mark.parametrize("path", sorted(CASES.glob("*.json")), ids=lambda p: p.stem)
def test_benchmark_cases_verify(path: Path) -> None:
    v = verdict(load_case(path))
    assert v.valid and v.trust_grade == "fully_hard", v.failures


def test_buggy_code_with_a_false_report_is_caught_by_rerunning_checks() -> None:
    v = verdict(with_source(CLAMP, NO_RANGE_CHECK))
    f = v.failures[0]
    assert (f.code, f.step_id) == ("output_mismatch", "s2")
    assert "'R3': 'failed'" in f.message


def test_buggy_code_with_an_honest_report_fails_the_requirement_only() -> None:
    honest = {"passed": False, "results": {"R1": "passed", "R2": "passed", "R3": "failed",
                                           "R4": "passed"}}
    v = verdict(with_source(CLAMP, NO_RANGE_CHECK, honest))
    assert {(f.code, f.requirement_id) for f in v.failures} == {
        ("requirement_failed", "all"), ("requirement_failed", "R3")}


def test_static_policy() -> None:
    for src, why in [("import os\ndef clamp(x, lo, hi):\n    return x\n", "denied module"),
                     ("def clmp(x, lo, hi):\n    return x\n", "no top-level function"),
                     ("def clamp(x, lo, hi):\n    return eval('x')\n", "denied builtin"),
                     ("def clamp(x, lo, hi) return x\n", "does not parse")]:
        v = verdict(with_source(CLAMP, src))
        assert v.failures[0].code == "checker_rejected" and why in v.failures[0].message


def test_suite_must_cover_every_requirement() -> None:
    spec = CLAMP.facts[0]
    reqs = {**spec.value["requirements"], "R5": "an extra requirement with no test"}
    c = replace(CLAMP, facts=(replace(spec, value={**spec.value, "requirements": reqs}),
                              *CLAMP.facts[1:]))
    v = verdict(c)
    assert v.failures[0].precondition == "suite_covers_spec" and "R5" in v.failures[0].message


def test_timeout_is_reported_not_hung() -> None:
    report = run_suite("def f():\n    while True:\n        pass\n",
                       "from solution import f\n\ndef test_R1_halts():\n    f()\n", ["R1"],
                       timeout=3)
    assert report == {"passed": False, "results": {"R1": "timeout"}}


def test_crashing_import_is_an_error_for_every_requirement() -> None:
    report = run_suite("raise SystemExit(3)\n",
                       "from solution import f\n\ndef test_R1_x():\n    f()\n", ["R1"])
    assert report["passed"] is False and report["results"]["R1"] in {"error", "missing"}


def test_runs_are_deterministic() -> None:
    src = load_case(CASES / "code_parse_duration.json")
    tests = src.facts[1].value["tests"]
    code = src.proof.steps[0].outputs["source"].value
    assert run_suite(code, tests, ["R1", "R2", "R3", "R4"]) == run_suite(
        code, tests, ["R1", "R2", "R3", "R4"])
