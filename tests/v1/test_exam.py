"""W3: the exam harness, the faithfulness lint, draft packages and unit types."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.bench import exam, faithfulness
from openverifiers.lang import OVError
from openverifiers.objects.engine import Settings
from openverifiers.runner import run_file

ROOT = Path(__file__).resolve().parents[2]
JEE = ROOT / "benchmarks" / "exams" / "jee2025"


def _q(verdict: str, *values: str) -> dict[str, object]:
    return {"query": "q", "line": 1, "verdict": verdict, "values": list(values)}


def test_numeric_answers_against_official_ranges() -> None:
    prob = {"official_answer": "[10.85 to 11.1]"}
    spec = {"read": "numeric", "query": 1, "unit": "g/cm^3"}
    assert exam.judge(prob, spec, {"queries": [_q("PROVEN", "11000 kg/m^3")]})[0] == "solved"
    assert exam.judge(prob, spec, {"queries": [_q("PROVEN", "12000 kg/m^3")]})[0] == "wrong"
    assert exam.judge(prob, spec, {"queries": [_q("UNKNOWN")]})[0] == "unknown"
    # An interval must lie inside the accepted range as a whole.
    assert exam.judge(prob, spec, {"queries": [_q("PROVEN", "11000 kg/m^3 (± 2e2)")]})[0] \
        == "wrong"
    assert exam.judge({"official_answer": "-2"}, {"read": "numeric", "query": 1},
                      {"queries": [_q("PROVEN", "-2")]})[0] == "solved"
    assert exam.read_value("25/6", None) == (Fraction(25, 6), Fraction(25, 6))
    assert exam.read_value("3 m", "kg") is None                # wrong dimension
    with pytest.raises(ValueError):
        exam.judge(prob, {"read": "numeric", "query": 2}, {"queries": [_q("PROVEN", "1")]})


def test_choice_and_option_answers() -> None:
    spec = {"read": "choice", "query": 1,
            "options": {"A": "2", "B": "sqrt(2)", "C": "sqrt(5/2)", "D": "sqrt(2/5)"}}
    got = {"queries": [_q("PROVEN", "1/2√10")]}
    assert exam.judge({"official_answer": "C"}, spec, got)[0] == "solved"
    assert exam.judge({"official_answer": "B"}, spec, got)[0] == "wrong"
    lo, hi = exam.read_surd("3 - √2") or (Fraction(0), Fraction(0))
    assert (3 - hi) ** 2 < 2 < (3 - lo) ** 2 and hi - lo < Fraction(1, 2 ** 50)
    assert exam.read_surd("x") is None
    with pytest.raises(ValueError):
        exam.option_value("__import__('os')")
    opts = {"read": "options", "options": {"A": [1], "B": [2], "C": [3]}}
    got3 = {"queries": [_q("PROVEN"), _q("REFUTED"), _q("PROVEN")]}
    assert exam.judge({"official_answer": "A, C"}, opts, got3)[0] == "solved"
    undecided = {"queries": [_q("PROVEN"), _q("UNKNOWN"), _q("PROVEN")]}
    assert exam.judge({"official_answer": "A, C"}, opts, undecided)[0] == "unknown"
    # A definite error stays an error even with an undecided option.
    assert exam.judge({"official_answer": "B, C"}, opts, undecided)[0] == "wrong"


def _case(tmp_path: Path, text: str, spec: dict[str, object] | None = None) -> Path:
    d = tmp_path / "jee2025-phys-p9q9"
    d.mkdir()
    (d / "case.ov").write_text(text)
    if spec is not None:
        (d / "answer.json").write_text(json.dumps(spec))
    return d


def test_lint_catches_leaks_laws_strays_and_maps(tmp_path: Path) -> None:
    d = _case(tmp_path, "law g: x = 1\nfact type T {\n  property r: Real\n"
                        "  invariant leak: r = 3\n}\nscenario s {\n"
                        "  query PROVE UNIQUE ?r WHERE T{ r = ?r }\n"
                        "  assume a: p(x)\n}\n", {"read": "numeric", "query": 2})
    (d / "lib.ov").write_text("package lib\n")
    codes = sorted(f.code for f in faithfulness.lint_case(d))
    assert codes == ["F1", "F2", "F3", "F4", "F5", "W2"]


def test_lint_accepts_a_factor_and_the_real_cases() -> None:
    assert not [f for f in faithfulness.lint(JEE) if f.error]


def test_draft_packages_load_only_when_asked() -> None:
    case = JEE / "jee2025-phys-p2q3" / "case.ov"
    with pytest.raises(OVError) as e:
        run_file(case, files={str(case)})
    assert "E203" in str(e.value)
    with pytest.raises(OVError):              # --strict never loads drafts
        run_file(case, files={str(case)}, settings=Settings(strict=True, drafts=True))
    res = run_file(case, files={str(case)}, settings=Settings(drafts=True))
    assert res.draft_packages == ["physics.rotation"]


def test_unit_types(tmp_path: Path) -> None:
    f = tmp_path / "u.ov"
    f.write_text('package probe.u\nfact type G {\n  property s: "W/m^2/K^4"\n'
                 '  property f: "W/m^2"\n  property t: Temperature\n'
                 '  invariant law: f = s * t ^ 4\n}\n'
                 'scenario x uses probe.u {\n  query FIND ?f WHERE G{ s = 2 W/m^2/K^4, '
                 't = 1 K, f = ?f }\n}\n')
    res = run_file(f, files={str(f)})
    assert res.objects[0].verdict == "PROVEN"
    f.write_text(f.read_text().replace('"W/m^2/K^4"', '"W/m^2/furlong"'))
    with pytest.raises(OVError) as e:
        run_file(f, files={str(f)})
    assert "E201" in str(e.value)


def test_exam_harness_end_to_end_on_one_problem(tmp_path: Path) -> None:
    listing = json.loads((JEE / "list.json").read_text())
    prob = next(p for p in listing["problems"] if p["id"] == "jee2025-phys-p2q3")
    r = exam.run_problem(JEE, prob, Settings(drafts=True))
    assert r.outcome == "solved" and r.provisional == ["physics.rotation"]
    r2 = exam.run_problem(JEE, prob, Settings())
    assert r2.outcome == "error" and r2.category == "library"
    s = exam.summary([r, r2])
    assert s["outcomes"] == {"solved": 1, "error": 1} and s["wrong"] == []
    assert "PROVISIONAL" in exam.render([r])
