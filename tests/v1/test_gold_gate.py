"""The gold-diff gate rejects unapproved gold edits (change order v1.1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from openverifiers.bench.gold_gate import approved_by, check_range, main

PKG = "src/openverifiers/packages/math/g.ov"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def commit(repo: Path, files: dict[str, str | None], msg: str) -> str:
    for name, text in files.items():
        p = repo / name
        if text is None:
            p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    commit(tmp_path, {
        PKG: "test a {\n  query PROVE p\n  expect PROVEN\n}\n",
        "benchmarks/physics/c1/case.ov": "x\n",
        "benchmarks/physics/c1/expected.json": '{"verdict": "PROVEN"}\n',
    }, "base")
    return tmp_path


def messages(repo: Path, base: str) -> list[str]:
    return [v.message for v in check_range(repo, base, "HEAD")]


def test_unapproved_package_expect_edit_is_rejected(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {PKG: "test a {\n  query PROVE p\n  expect REFUTED\n}\n"}, "flip it")
    [m] = messages(repo, base)
    assert "without a human 'Gold-Change-Approved-By:'" in m and "expect PROVEN" in m


def test_unapproved_benchmark_gold_edit_or_delete_is_rejected(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"benchmarks/physics/c1/expected.json": '{"verdict": "UNKNOWN"}\n'}, "edit")
    commit(repo, {"benchmarks/physics/c1/expected.json": None}, "delete")
    ms = messages(repo, base)
    assert len(ms) == 2 and "modified" in ms[0] and "deleted" in ms[1]


def test_unapproved_theorem_weakening_is_rejected(repo: Path) -> None:
    commit(repo, {PKG: "fact type T {\n  theorem t: none v in cycles(p): a\n}\n"}, "add")
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {PKG: "fact type T {\n  theorem t: exists v in cycles(p): a\n}\n"}, "weaken")
    [m] = messages(repo, base)
    assert "theorem t: none" in m


def test_approved_edit_passes_and_ai_approvers_do_not(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    edit: dict[str, str | None] = {PKG: "test a {\n  query PROVE p\n  expect REFUTED\n}\n"}
    commit(repo, edit, "flip it\n\nGold-Change-Approved-By: Claude Opus 5.5")
    assert len(messages(repo, base)) == 1
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {PKG: "test a {\n  query PROVE p\n  expect UNKNOWN\n}\n"},
           "flip again\n\nGold-Change-Approved-By: A. Reviewer")
    assert messages(repo, base) == []
    assert approved_by("x\n\nGold-Change-Approved-By: dependabot[bot]") is None
    assert approved_by("x\n\nGold-Change-Approved-By: ") is None


def test_new_gold_is_free_but_must_come_first_and_alone(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"benchmarks/physics/c2/case.ov": "y\n",
                  "benchmarks/physics/c2/expected.json": "{}\n"}, "gold for c2")
    commit(repo, {PKG: "test a {\n  query PROVE p\n  expect PROVEN\n}\ntest b {\n"
                       "  expect PROVEN\n}\n"}, "new package test")
    assert messages(repo, base) == []
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"benchmarks/physics/c3/expected.json": "{}\n",
                  "reports/bench/results.jsonl": "{}\n"}, "gold and results together")
    [m] = messages(repo, base)
    assert "gold must be committed first" in m and "reports/bench/results.jsonl" in m


def test_cli_exit_codes(repo: Path, monkeypatch: pytest.MonkeyPatch,
                        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(repo)
    base = git(repo, "rev-parse", "HEAD")
    assert main([base, "HEAD"]) == 0
    commit(repo, {"benchmarks/physics/c1/expected.json": "{}\n"}, "edit")
    assert main([base, "HEAD"]) == 1
    assert "gold gate:" in capsys.readouterr().out
    assert main([]) == 2
