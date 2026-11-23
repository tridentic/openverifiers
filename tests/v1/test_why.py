"""OKQL WHY / WHY NOT: the kernel's verdict, with its derivation or what blocks it."""

from __future__ import annotations

from pathlib import Path

from openverifiers.runner import explain, render, run_file

CASE = Path(__file__).parent / "why.ov"


def test_why_and_why_not() -> None:
    res = run_file(CASE, files={str(CASE)})
    why, why_not, holds = res.answers
    lw = res.lowered[0]
    run = res.runs[why.scenario]
    assert why.verdict == "PROVEN"
    assert any("small: allowed(r1)" in s for s in explain(why, run, lw, "why"))
    assert why_not.verdict == "UNKNOWN"
    assert explain(why_not, run, lw, "why_not") == [
        "blocked (missing_facts): add one of: approved(r2, manager)"]
    assert explain(holds, run, lw, "why_not")[0] == "it holds after all:"
    text = render(res)                                   # WHY output needs no --verbose
    assert "blocked (missing_facts)" in text and "small: allowed(r1)" in text
