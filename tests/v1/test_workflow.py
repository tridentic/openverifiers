"""C5: agent.workflow (draft): plan verification naming the failing steps, the
gate's verdicts, and bounded plan synthesis."""

from __future__ import annotations

from pathlib import Path

from openverifiers.objects.engine import Settings
from openverifiers.runner import run_file

CASE = Path(__file__).parent / "workflow_repo.ov"


def test_plans_are_checked_and_synthesised() -> None:
    res = run_file(CASE, files={str(CASE)}, settings=Settings(drafts=True))
    assert res.draft_packages == ["agent.workflow"]
    valid, steps, refused, permitted, human, plan = res.answers
    assert valid.verdict == "REFUTED"
    assert sorted(str(s["i"].value) for s, _ in steps.bindings) == ["2", "3"]  # type: ignore[union-attr]
    assert (refused.verdict, permitted.verdict, human.verdict) == ("PROVEN",) * 3
    assert plan.verdict == "PROVEN" and len(plan.bindings) == 1
    found = str(plan.bindings[0][0]["p"])
    assert "push" not in found and "open_pr" in found and "merge" in found
    assert all(a.trust_base == {"kernel"} for a in res.answers if a.verdict == "PROVEN")
