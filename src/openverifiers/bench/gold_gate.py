"""The gold-diff gate (change order v1.1, anti-reward-hacking rules).

    python -m openverifiers.bench.gold_gate BASE HEAD

Gold is what verdicts are judged against:

- ``benchmarks/**/expected.json`` (benchmark gold) and ``review.json`` (the
  faithfulness reviewer's expected verdicts);
- ``laws/**``;
- in ``src/openverifiers/packages/**/*.ov``, every ``expect`` line (package tests
  are gold too) and every ``theorem`` line (the prover may not weaken targets).

For each commit in BASE..HEAD (the meaning gate, MP-DOL, is described at
MEANING_TRAILER below):

1. **Changing or deleting gold** needs the trailer
   ``Gold-Change-Approved-By: <approver> ...`` in the commit message, where the
   first word is a role listed in ``APPROVERS`` (``founder``; MP §9, D-024), e.g.
   ``Gold-Change-Approved-By: founder (reply to packet 1a2b3c4)``. Adding new
   gold (a new expected.json, a new ``expect`` line) does not need it.
   ``APPROVERS`` is read from the parent commit, so a commit cannot approve
   itself by editing it, and any change to the set of roles in ``APPROVERS``
   (creating or deleting the file included) needs the gold trailer.
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
GOLD_FILES = ("benchmarks/**/expected.json", "benchmarks/**/review.json", "laws/**")
GOLD_LINES = ("src/openverifiers/packages/**/*.ov",)
GOLD_LINE = re.compile(r"^\s*(expect|theorem)\b")
NOT_HUMAN = re.compile(r"claude|anthropic|\bbot\b|\[bot\]|gpt|copilot|codex", re.I)

#: The meaning gate (MP-DOL, decision D-023): AI drafts, OV decides, humans own
#: meaning. Adding, changing or removing a statement that carries meaning in
#: packages/ or laws/ (an axiom, law, definition, class invariant or main theorem;
#: continuation lines included) needs this trailer naming an approver role (the
#: founder; see APPROVERS). Lemmas, proofs,
#: tests and scenarios do not. One trailer covers every such line in its commit.
MEANING_TRAILER = "Meaning-Approved-By"
MEANING_FILES = ("src/openverifiers/packages/**/*.ov", "laws/**")
#: D-025: besides MEANING_FILES, every .ov file that declares a `package`, anywhere,
#: except unapproved drafts, benchmark problem statements (checked by the
#: faithfulness lint and reviewer) and test fixtures.
NOT_LIBRARY = ("drafts/**", "benchmarks/**/case.ov", "tests/**")
MEANING_HEAD = re.compile(r"^\s*(axiom|law|definition|invariant|theorem)\b")
STATEMENT_HEAD = re.compile(
    r"^\s*(axiom|law|definition|invariant|theorem|lemma|property|derived|fact|test|scenario|"
    r"query|expect|package|import|type|predicate|function|entity|generator|transformation|"
    r"controller|target|assume|tolerance|world|})\b|^\s*}")


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


#: The approver roles when no APPROVERS file exists at the parent commit.
DEFAULT_APPROVERS = frozenset({"founder"})


def read_approvers(text: str | None) -> frozenset[str]:
    """Roles in an APPROVERS file: one per line, ``#`` starts a comment."""
    if text is None:
        return DEFAULT_APPROVERS
    roles = {ln.split("#", 1)[0].strip() for ln in text.splitlines()}
    return frozenset(r for r in roles if r and not NOT_HUMAN.search(r))


def _trailer(message: str, name: str, roles: frozenset[str]) -> str | None:
    for line in message.splitlines():
        m = re.match(rf"^{name}:(.*)$", line)
        who = m.group(1).strip() if m else ""
        first = who.split()[0] if who else ""
        if first in roles and not NOT_HUMAN.search(who.split("(")[0]):
            return who
    return None


def approved_by(message: str, roles: frozenset[str] = DEFAULT_APPROVERS) -> str | None:
    """The approval in the gold trailer, or None (missing, not an approver, an AI agent)."""
    return _trailer(message, TRAILER, roles)


def _meaning_lines(text: str, numbers: set[int]) -> list[str]:
    """The lines (1-based numbers) that belong to a meaning-carrying statement: the
    statement's own line, or a continuation of one (indented, no keyword of its own)."""
    lines = text.splitlines()
    out = []
    for n in sorted(numbers):
        i = n - 1
        while i >= 0 and (not lines[i].strip() or not STATEMENT_HEAD.match(lines[i])) \
                and not lines[i].lstrip().startswith("#"):
            i -= 1
        if i >= 0 and MEANING_HEAD.match(lines[i]) and 0 < n <= len(lines) \
                and lines[n - 1].strip() and not lines[n - 1].lstrip().startswith("#"):
            out.append(lines[n - 1].strip())
    return out


def _changed_numbers(diff: str) -> tuple[set[int], set[int]]:
    """Old and new line numbers touched by a -U0 diff."""
    old, new = set(), set()
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        a, na, b, nb = int(m[1]), int(m[2] or 1), int(m[3]), int(m[4] or 1)
        old |= set(range(a, a + na))
        new |= set(range(b, b + nb))
    return old, new


def meaning_changes(repo: Path, base: str, sha: str, path: str) -> list[str]:
    diff = _git(repo, "diff", "-U0", base, sha, "--", path)
    old_n, new_n = _changed_numbers(diff)

    def show(rev: str) -> str:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"],
                           capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""
    return ([f"- {x}" for x in _meaning_lines(show(base), old_n)]
            + [f"+ {x}" for x in _meaning_lines(show(sha), new_n)])


def meaning_approved(message: str, roles: frozenset[str] = DEFAULT_APPROVERS) -> bool:
    return _trailer(message, MEANING_TRAILER, roles) is not None


def _show(repo: Path, rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def is_library(repo: Path, base: str, sha: str, path: str) -> bool:
    """A file whose meaning lines are gated: MEANING_FILES, or any package file (D-025)."""
    if _match(path, MEANING_FILES):
        return True
    if not path.endswith(".ov") or _match(path, NOT_LIBRARY):
        return False
    return any(t is not None and re.search(r"^\s*package\s", t, re.M)
               for t in (_show(repo, base, path), _show(repo, sha, path)))


def check_commit(repo: Path, sha: str) -> list[Violation]:
    message = _git(repo, "log", "-1", "--format=%B", sha)
    parents = _git(repo, "log", "-1", "--format=%P", sha).split()
    base = parents[0] if parents else _git(repo, "hash-object", "-t", "tree", "/dev/null").strip()
    status = [line.split("\t") for line in
              _git(repo, "diff", "--no-renames", "--name-status", base, sha).splitlines()]
    out: list[Violation] = []
    changed: list[str] = []
    for st, path in ((s[0], s[-1]) for s in status):
        if path == "APPROVERS":
            if read_approvers(_show(repo, base, path)) != read_approvers(_show(repo, sha, path)):
                changed.append("APPROVERS (who may approve)")
        elif _match(path, GOLD_FILES) and st != "A":
            changed.append(f"{path} ({'deleted' if st == 'D' else 'modified'})")
        elif _match(path, GOLD_LINES) and st != "A":
            diff = _git(repo, "diff", "-U0", base, sha, "--", path)
            removed = [ln[1:].strip() for ln in diff.splitlines()
                       if ln.startswith("-") and not ln.startswith("---")
                       and GOLD_LINE.match(ln[1:])]
            changed += [f"{path}: {r!r}" for r in removed]
    roles = read_approvers(_show(repo, base, "APPROVERS"))
    if changed and approved_by(message, roles) is None:
        out.append(Violation(sha, f"changes gold without a '{TRAILER}: <approver>' trailer "
                             f"(approvers: {', '.join(sorted(roles))}): " + "; ".join(changed)))
    meaning = [f"{path}: {x}" for _, path in ((s[0], s[-1]) for s in status)
               if is_library(repo, base, sha, path)
               for x in meaning_changes(repo, base, sha, path)]
    if meaning and not meaning_approved(message, roles):
        out.append(Violation(sha, f"changes meaning-carrying lines without "
                             f"'{MEANING_TRAILER}: <approver>' (approvers: "
                             f"{', '.join(sorted(roles))}): " + "; ".join(meaning)))
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
