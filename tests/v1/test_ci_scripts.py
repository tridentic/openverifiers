"""The report placeholder check and the D-034 CI streak count."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod                     # dataclasses look their module up here
    spec.loader.exec_module(mod)
    return mod


def test_placeholders_are_caught_and_quoted_text_is_not() -> None:
    cr = _load("check_reports")
    assert [n for n, _ in cr.hits("## 3. Numbers\n\nNUMBERS\n")] == [3]
    assert cr.hits("value {{ tcb_total }} here\n") and cr.hits("CI: filled in below\n")
    assert cr.hits("TODO: write this\n") and cr.hits("| TBD |\n")
    assert cr.hits("labels `{{a}}` are special\n") == []          # not a template slot
    assert cr.hits("```\nTODO inside a quoted reply\n```\n") == []
    assert cr.hits("The TCB is 2,091 lines.\n") == []


def test_every_committed_report_is_filled() -> None:
    cr = _load("check_reports")
    root = SCRIPTS.parent
    files = [*(root / "reports").rglob("*.md"), *(root / "approvals").glob("*.md")]
    assert files and not [f for f in files if cr.hits(f.read_text())]


def test_streak_counts_first_attempts_and_distinct_commits() -> None:
    cs = _load("ci_streak")
    R = cs.Run
    rs = [R(9, "e", "push", "9", "in_progress", ""),
          R(8, "d", "push", "8", "completed", "success"),
          R(7, "n", "schedule", "7", "completed", "success"),
          R(6, "c", "push", "6", "completed", "success"),
          R(5, "c", "push", "5", "completed", "success"),     # the same commit again
          R(4, "b", "push", "4", "completed", "failure"),     # first attempt failed;
          R(3, "a", "push", "3", "completed", "success")]     # a re-run does not count
    counted, broke, pending = cs.streak(rs)
    assert [r.id for r in counted] == [8, 7, 6] and broke.id == 4 and [p.id for p in pending] == [9]
