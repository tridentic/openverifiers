"""The gold-diff gate (change order v1.1, anti-reward-hacking rules).

    python -m openverifiers.bench.gold_gate BASE HEAD

Gold is what verdicts are judged against:

- ``benchmarks/**/expected.json`` (benchmark gold);
- ``laws/**``;
- in ``src/openverifiers/packages/**/*.ov``, every ``expect`` line (package tests
  are gold too) and every ``theorem`` line (the prover may not weaken targets).

For each commit in BASE..HEAD:

1. **Changing or deleting gold** needs the trailer
   ``Gold-Change-Approved-By: <human>`` in the commit message. Adding new gold
   (a new expected.json, a new ``expect`` line) does not. An approver that
   names an AI agent is rejected.
2. **Gold first.** A commit that adds a benchmark's ``expected.json`` may touch
   nothing outside ``benchmarks/``, so the gold is fixed in history before OV's
   results for that case exist.

Exit 0 when every commit passes, 1 otherwise, with one line per violation.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

TRAILER = "Gold-Change-Approved-By"
GOLD_FILES = ("benchmarks/**/expected.json", "laws/**")
GOLD_LINES = ("src/openverifiers/packages/**/*.ov",)
GOLD_LINE = re.compile(r"^\s*(expect|theorem)\b")
NOT_HUMAN = re.compile(r"claude|anthropic|\bbot\b|\[bot\]|gpt|copilot|codex", re.I)


def _match(path: str, patterns: Sequence[str]) -> bool:
    # fnmatch's * crosses "/", so "a/**/b" also needs the zero-directory form "a/b".
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path, p.replace("**/", ""))
               for p in patterns)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout


@dataclass
class Violation:
    commit: str
    message: str

    def __str__(self) -> str:
        return f"{self.commit[:10]}: {self.message}"


def approved_by(message: str) -> str | None:
    """The human named in the trailer, or None (missing, empty, or an AI agent)."""
    for line in message.splitlines():
        m = re.match(rf"^{TRAILER}:(.*)$", line)
        who = m.group(1).strip() if m else ""
        if who and not NOT_HUMAN.search(who):
            return who
    return None


def check_commit(repo: Path, sha: str) -> list[Violation]:
    message = _git(repo, "log", "-1", "--format=%B", sha)
    parents = _git(repo, "log", "-1", "--format=%P", sha).split()
    base = parents[0] if parents else _git(repo, "hash-object", "-t", "tree", "/dev/null").strip()
    status = [line.split("\t") for line in
              _git(repo, "diff", "--no-renames", "--name-status", base, sha).splitlines()]
    out: list[Violation] = []
    changed: list[str] = []
    for st, path in ((s[0], s[-1]) for s in status):
        if _match(path, GOLD_FILES) and st != "A":
            changed.append(f"{path} ({'deleted' if st == 'D' else 'modified'})")
        elif _match(path, GOLD_LINES) and st != "A":
            diff = _git(repo, "diff", "-U0", base, sha, "--", path)
            removed = [ln[1:].strip() for ln in diff.splitlines()
                       if ln.startswith("-") and not ln.startswith("---")
                       and GOLD_LINE.match(ln[1:])]
            changed += [f"{path}: {r!r}" for r in removed]
    if changed and approved_by(message) is None:
        out.append(Violation(sha, "changes gold without a human "
                             f"'{TRAILER}:' trailer: " + "; ".join(changed)))
    new_gold = [p for s, p in ((s[0], s[-1]) for s in status)
                if s == "A" and fnmatch.fnmatch(p, "benchmarks/**/expected.json")]
    if new_gold:
        others = [p for _, p in ((s[0], s[-1]) for s in status)
                  if not p.startswith("benchmarks/")]
        if others:
            out.append(Violation(sha, "adds benchmark gold together with files outside "
                                 "benchmarks/ (gold must be committed first, alone): "
                                 + ", ".join(others)))
    return out


def check_range(repo: Path, base: str, head: str) -> list[Violation]:
    shas = _git(repo, "rev-list", "--reverse", f"{base}..{head}").split()
    return [v for sha in shas for v in check_commit(repo, sha)]


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m openverifiers.bench.gold_gate BASE HEAD", file=sys.stderr)
        return 2
    found = check_range(Path.cwd(), args[0], args[1])
    for v in found:
        print(f"gold gate: {v}")
    if not found:
        print(f"gold gate: ok ({args[0][:10]}..{args[1][:10]})")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
