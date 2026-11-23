"""The gold-diff gate rejects unapproved gold edits (change order v1.1).

Approvals count only on commits signed by a key in .approvers/allowed_signers
(D-032). The keys here are throwaway test keys made per test in a temp folder."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from openverifiers.bench.gold_gate import SIGNERS, approved_by, check_range, dry_run, main

PKG = "src/openverifiers/packages/math/g.ov"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def key(repo: Path, who: str) -> Path:
    """A throwaway ed25519 test key for ``who`` (made once per test, outside the repo)."""
    k = repo.parent / "keys" / who
    if not k.exists():
        k.parent.mkdir(exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", who, "-f", str(k)],
                       check=True)
    return k


def signer_line(repo: Path, who: str) -> str:
    return f'{who} namespaces="git" ' + key(repo, who).with_suffix(".pub").read_text()


def commit(repo: Path, files: dict[str, str | None], msg: str, sign: str = "") -> str:
    """Commit files; ``sign`` names the test key that signs the commit."""
    for name, text in files.items():
        p = repo / name
        if text is None:
            p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(repo, "add", "-A")
    if sign:
        git(repo, "-c", "gpg.format=ssh", "-c", f"user.signingkey={key(repo, sign)}",
            "commit", "-q", "-S", "-m", msg)
    else:
        git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    tmp_path = tmp_path / "r"
    tmp_path.mkdir()
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    commit(tmp_path, {SIGNERS: signer_line(tmp_path, "founder")}, "approval key", "founder")
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
    assert "without a 'Gold-Change-Approved-By: <approver>'" in m and "expect PROVEN" in m


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
    gold, meaning = messages(repo, base)          # both gates object
    assert "theorem t: none" in gold and "Meaning-Approved-By" in meaning


def test_approved_edit_passes_and_ai_approvers_do_not(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    edit: dict[str, str | None] = {PKG: "test a {\n  query PROVE p\n  expect REFUTED\n}\n"}
    commit(repo, edit, "flip it\n\nGold-Change-Approved-By: Claude Opus 5.5")
    assert len(messages(repo, base)) == 1
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {PKG: "test a {\n  query PROVE p\n  expect UNKNOWN\n}\n"},
           "flip again\n\nGold-Change-Approved-By: A. Reviewer")
    assert len(messages(repo, base)) == 1                   # not a listed approver
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {PKG: "test a {\n  query PROVE p\n  expect PROVEN\n}\n"},
           f"flip back\n\nGold-Change-Approved-By: {OK}")
    [m] = messages(repo, base)                              # the trailer alone: unsigned
    assert "not signed by a key in .approvers/allowed_signers" in m
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, {PKG: "test a {\n  query PROVE p\n  expect PROVEN\n}\n"},
           f"flip back\n\nGold-Change-Approved-By: {OK}", sign="stranger")
    assert len(messages(repo, base)) == 1                   # signed, by an unlisted key
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, {PKG: "test a {\n  query PROVE p\n  expect PROVEN\n}\n"},
           f"flip back\n\nGold-Change-Approved-By: {OK}", sign="founder")
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


# ---------------------------------------------------------------- the meaning gate (MP-DOL)

LIB = "src/openverifiers/packages/math/m.ov"
OK = "founder (reply to packet 1a2b3c4)"
CLASS = """package math.m
fact type K {
  property a: Real
  property b: Real
  invariant pos: a > 0
  theorem big: b > a
  lemma helper: b >= a
}
test k { scenario k_s uses math.m { } }
"""


def test_meaning_gate_rejects_unapproved_meaning_changes(repo: Path) -> None:
    commit(repo, {LIB: CLASS}, f"add class\n\nMeaning-Approved-By: {OK}", "founder")
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {LIB: CLASS.replace("a > 0", "a >= 0")}, "weaken an invariant")
    [m] = messages(repo, base)
    assert "Meaning-Approved-By: <approver>" in m and "- invariant pos: a > 0" in m
    assert "+ invariant pos: a >= 0" in m


def test_meaning_gate_covers_new_statements_and_continuations(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {LIB: CLASS}, "new class without approval")
    ms = messages(repo, base)
    assert len(ms) == 1 and "+ invariant pos: a > 0" in ms[0] and "+ theorem big" in ms[0]
    assert "lemma helper" not in ms[0]                      # lemmas are free (MP-DOL)
    base = git(repo, "rev-parse", "HEAD")
    multi = CLASS.replace("  invariant pos: a > 0\n", "  invariant pos:\n    a > 0\n")
    commit(repo, {LIB: multi}, f"reflow\n\nMeaning-Approved-By: {OK}", "founder")
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {LIB: multi.replace("    a > 0\n", "    a > 1\n")}, "edit a continuation")
    [m] = messages(repo, base)
    assert "+ a > 1" in m


def test_meaning_gate_ignores_tests_lemmas_and_accepts_the_founder_only(repo: Path) -> None:
    commit(repo, {LIB: CLASS}, f"add\n\nMeaning-Approved-By: {OK}", "founder")
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {LIB: CLASS.replace("b >= a", "b >= a - 1").replace("k_s", "k_t")},
           "lemma and test only")
    assert messages(repo, base) == []
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {LIB: CLASS.replace("theorem big: b > a", "theorem big: b > 2 * a")},
           f"x\n\nMeaning-Approved-By: Claude\nGold-Change-Approved-By: {OK}", "founder")
    [m] = messages(repo, base)                    # only the founder approves meaning
    assert "Meaning-Approved-By: <approver>" in m


def test_approvers_file_is_read_from_the_parent_and_is_gold(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"APPROVERS": "# roles\nfounder\n"}, "the default, written down")
    assert messages(repo, base) == []                       # same roles: no change
    base = git(repo, "rev-parse", "HEAD")
    both = signer_line(repo, "founder") + signer_line(repo, "mallory")
    commit(repo, {"APPROVERS": "founder\nmallory\n", SIGNERS: both}, "add an approver")
    [m] = messages(repo, base)                              # both files are gold
    assert "APPROVERS" in m and SIGNERS in m
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {LIB: CLASS}, "self-approve\n\nMeaning-Approved-By: mallory", "mallory")
    assert messages(repo, base) == []                       # the parent lists mallory
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"APPROVERS": "founder\n", SIGNERS: signer_line(repo, "founder"),
                  LIB: CLASS.replace("a > 0", "a > 1")},
           "drop mallory and approve\n\nMeaning-Approved-By: mallory\n"
           "Gold-Change-Approved-By: mallory", "mallory")
    assert messages(repo, base) == []                       # parent still lists mallory
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {LIB: CLASS}, "x\n\nMeaning-Approved-By: mallory", "mallory")
    assert len(messages(repo, base)) == 1                   # now only the founder


def test_meaning_gate_covers_package_files_anywhere_but_drafts(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"benchmarks/physics/c1/lib.ov": "package sneaky\n" + CLASS,
                  "drafts/packages/math/d.ov": "package math.d\n" + CLASS,
                  "benchmarks/physics/c9/case.ov": "package bench.c9\n" + CLASS,
                  "tests/v1/fixture.ov": "package probe\n" + CLASS}, "libraries")
    [m] = messages(repo, base)
    assert "benchmarks/physics/c1/lib.ov" in m
    assert "drafts/" not in m and "c9/case.ov" not in m and "fixture.ov" not in m


def test_the_approval_key_file_must_be_created_by_a_key_it_lists(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    base = commit(tmp_path, {"README": "x\n"}, "start")
    commit(tmp_path, {SIGNERS: signer_line(tmp_path, "founder")}, "unsigned setup")
    commit(tmp_path, {SIGNERS: signer_line(tmp_path, "founder") + "\n"}, "x", "founder")
    ms = [v.message for v in check_range(tmp_path, base, "HEAD")]
    assert len(ms) == 2 and "creates .approvers/allowed_signers" in ms[0]
    assert SIGNERS in ms[1]                                 # a later change is gold
    git(tmp_path, "reset", "-q", "--hard", base)
    commit(tmp_path, {SIGNERS: signer_line(tmp_path, "founder")}, "setup", "stranger")
    assert len(check_range(tmp_path, base, "HEAD")) == 1    # signed by a key it does not list
    git(tmp_path, "reset", "-q", "--hard", base)
    commit(tmp_path, {SIGNERS: signer_line(tmp_path, "founder")}, "setup", "founder")
    assert check_range(tmp_path, base, "HEAD") == []


def test_a_signed_approval_ratifies_earlier_commits_of_its_own_kind(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    bad = commit(repo, {"policy/p.ov": "package p\naxiom a: q -> r\n"},
                 f"agent-stamped\n\nMeaning-Approved-By: {OK}")
    gold = commit(repo, {PKG: "test a {\n  query PROVE p\n  expect REFUTED\n}\n"}, "flip")
    assert len(messages(repo, base)) == 2
    commit(repo, {"notes.md": "r\n"},
           f"ratify\n\nMeaning-Approved-By: {OK}\nRatifies: {bad[:7]} {gold[:7]} D-029")
    assert len(messages(repo, base)) == 3                   # unsigned: ratifies nothing, and
    #                                                         its own trailer is a violation
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, {"notes.md": "r\n"},
           f"ratify\n\nMeaning-Approved-By: {OK}\nRatifies: {bad[:7]} {gold[:7]} D-029",
           "founder")
    [m] = messages(repo, base)                              # a meaning approval only
    assert "Gold-Change-Approved-By" in m and gold[:10] in str(check_range(repo, base, "HEAD")[0])


def test_dry_run_reports_what_the_staged_change_needs(repo: Path, monkeypatch: pytest.MonkeyPatch,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "policy").mkdir()
    (repo / "policy/p.ov").write_text("package p\naxiom a: q -> r\n")
    (repo / PKG).write_text("test a {\n  query PROVE p\n  expect REFUTED\n}\n")
    git(repo, "add", "-A")
    lines = dry_run(repo)
    assert lines[-1] == "needs: meaning gold" and any("axiom a" in x for x in lines)
    monkeypatch.chdir(repo)
    assert main(["--staged"]) == 0 and "dry run" in capsys.readouterr().out
    git(repo, "reset", "-q", "--hard")
    assert dry_run(repo) == ["needs: nothing"]


def test_rules_apply_from_the_commit_that_introduced_them(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    gate = "src/openverifiers/bench/gold_gate.py"
    commit(repo, {gate: "# no rules yet\n", LIB: CLASS}, "before the meaning gate")
    commit(repo, {gate: "MEANING = 'Meaning-Approved-By'\n"}, "the meaning gate")
    after = commit(repo, {LIB: CLASS.replace("a > 0", "a > 1")}, "after it")
    [v] = check_range(repo, base, "HEAD")                    # the earlier commit is exempt
    assert v.commit == after and "+ invariant pos: a > 1" in v.message


def test_every_approval_trailer_must_be_signed(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"notes.md": "x\n"}, f"stamped\n\nMeaning-Approved-By: {OK}")
    commit(repo, {"notes.md": "y\n"}, "stamped by an agent\n\nGold-Change-Approved-By: Claude")
    ms = messages(repo, base)
    assert len(ms) == 2 and all("not signed" in m for m in ms)
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"notes.md": "z\n"}, f"signed\n\nMeaning-Approved-By: {OK}", "founder")
    assert messages(repo, base) == []
