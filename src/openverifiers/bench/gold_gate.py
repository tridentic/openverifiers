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
3. **Signed approvals (D-032).** A trailer counts only if its commit is signed
   (``git commit -S``, SSH) by a key listed in ``.approvers/allowed_signers``
   under an approver role (the principal ``founder``). The file is read from the
   parent commit, like ``APPROVERS``. Unsigned or wrongly signed approval
   commits fail. Agents never write approval trailers; the founder runs
   ``scripts/founder_approve.sh`` (docs/APPROVALS.md).
   - **Setup:** the commit that creates ``.approvers/allowed_signers`` must be
     signed by a key it lists; every later change to it is a gold change.
   - **Ratification:** history cannot be rewritten, so a signed approval commit
     may list earlier commits in a ``Ratifies:`` trailer. Their meaning (or
     gold) violations are cleared when the ratifying commit carries the meaning
     (or gold) trailer. Gold-first violations cannot be cleared.

**Rules apply from the commit that introduced them** (the first commit whose
``bench/gold_gate.py`` names the trailer): earlier history was never under the
rule. A repository without that file is under every rule from its first commit.
The signature rule covers every approval trailer, whenever it was written.

``--staged`` is the dry run: it reports what the staged change would need
(``needs: meaning gold``) without checking any message or signature.

Exit 0 when every commit passes, 1 otherwise, with one line per violation.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import tempfile
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
    kind: str = "order"             # "gold", "meaning" or "order" (gold first)

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


def _diff(repo: Path, base: str, sha: str, *args: str) -> str:
    """``git diff`` from base to sha; sha "" is the staged index (the dry run).
    Options come before ``--`` in args, paths after."""
    i = args.index("--") if "--" in args else len(args)
    revs = ["--cached", base] if sha == "" else [base, sha]
    return _git(repo, "diff", *args[:i], *revs, *args[i:])


def meaning_changes(repo: Path, base: str, sha: str, path: str) -> list[str]:
    old_n, new_n = _changed_numbers(_diff(repo, base, sha, "-U0", "--", path))
    return ([f"- {x}" for x in _meaning_lines(_show(repo, base, path) or "", old_n)]
            + [f"+ {x}" for x in _meaning_lines(_show(repo, sha, path) or "", new_n)])


def meaning_approved(message: str, roles: frozenset[str] = DEFAULT_APPROVERS) -> bool:
    return _trailer(message, MEANING_TRAILER, roles) is not None


SIGNERS = ".approvers/allowed_signers"
RATIFIES = "Ratifies"


def signed_role(repo: Path, sha: str, signers: str | None,
                roles: frozenset[str] = DEFAULT_APPROVERS) -> str | None:
    """The approver role whose key (in the ``signers`` file text) signed ``sha``, or None."""
    if not signers:
        return None
    fd, name = tempfile.mkstemp(suffix=".signers")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(signers)
        out = subprocess.run(["git", "-C", str(repo), "-c", f"gpg.ssh.allowedSignersFile={name}",
                              "log", "-1", "--format=%G?%x00%GS", sha],
                             capture_output=True, text=True).stdout.strip()
    finally:
        os.unlink(name)
    status, _, who = out.partition("\0")
    return who if status == "G" and who in roles and not NOT_HUMAN.search(who) else None


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


@dataclass
class Changes:
    gold: list[str]           # gold changed or deleted (needs the gold trailer)
    meaning: list[str]        # meaning-carrying lines changed (needs the meaning trailer)
    order: list[str]          # new gold committed together with other files
    setup: bool               # creates .approvers/allowed_signers


def changes(repo: Path, base: str, sha: str) -> Changes:
    """What a commit (or, for sha "", the staged index) changes, against base."""
    status = [line.split("\t") for line in
              _diff(repo, base, sha, "--no-renames", "--name-status").splitlines()]
    pairs = [(s[0], s[-1]) for s in status]
    gold: list[str] = []
    setup = False
    for st, path in pairs:
        if path == "APPROVERS":
            if read_approvers(_show(repo, base, path)) != read_approvers(_show(repo, sha, path)):
                gold.append("APPROVERS (who may approve)")
        elif path == SIGNERS:
            setup = _show(repo, base, path) is None
            if not setup:
                gold.append(f"{SIGNERS} (approval keys)")
        elif _match(path, GOLD_FILES) and st != "A":
            gold.append(f"{path} ({'deleted' if st == 'D' else 'modified'})")
        elif _match(path, GOLD_LINES) and st != "A":
            diff = _diff(repo, base, sha, "-U0", "--", path)
            gold += [f"{path}: {ln[1:].strip()!r}" for ln in diff.splitlines()
                     if ln.startswith("-") and not ln.startswith("---")
                     and GOLD_LINE.match(ln[1:])]
    meaning = [f"{path}: {x}" for _, path in pairs if is_library(repo, base, sha, path)
               for x in meaning_changes(repo, base, sha, path)]
    order = []
    if any(st == "A" and fnmatch.fnmatch(p, "benchmarks/**/expected.json") for st, p in pairs):
        order = [p for _, p in pairs if not p.startswith("benchmarks/")]
    return Changes(gold, meaning, order, setup)


GATE_FILE = "src/openverifiers/bench/gold_gate.py"


def rules_since(repo: Path, head: str = "HEAD") -> dict[str, str | None]:
    """For each rule kind, the commit that introduced it (None: in force from the start)."""
    out: dict[str, str | None] = {}
    for kind, word in (("gold", TRAILER), ("meaning", MEANING_TRAILER)):
        hits = _git(repo, "log", "--reverse", "--format=%H", f"-S{word}", head, "--",
                    GATE_FILE).split()
        out[kind] = hits[0] if hits else None
    out["order"] = out["gold"]
    return out


def _in_force(repo: Path, since: str | None, sha: str) -> bool:
    if since is None:
        return True
    r = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", since, sha],
                       capture_output=True)
    return r.returncode == 0 and since != sha


def _base(repo: Path, sha: str) -> str:
    parents = _git(repo, "log", "-1", "--format=%P", sha).split()
    return parents[0] if parents else _git(repo, "hash-object", "-t", "tree", "/dev/null").strip()


def check_commit(repo: Path, sha: str,
                 since: dict[str, str | None] | None = None) -> list[Violation]:
    message = _git(repo, "log", "-1", "--format=%B", sha)
    base = _base(repo, sha)
    ch = changes(repo, base, sha)
    since = since if since is not None else rules_since(repo)
    if not _in_force(repo, since["gold"], sha):
        ch.gold, ch.order = [], []
    if not _in_force(repo, since["meaning"], sha):
        ch.meaning = []
    has_trailer = bool(re.search(rf"^({TRAILER}|{MEANING_TRAILER}):", message, re.M))
    roles = read_approvers(_show(repo, base, "APPROVERS"))
    out: list[Violation] = []
    gold_t, meaning_t = approved_by(message, roles), meaning_approved(message, roles)
    signer = (signed_role(repo, sha, _show(repo, base, SIGNERS), roles)
              if gold_t or meaning_t else None)
    if has_trailer and signer is None and not (ch.gold or ch.meaning):
        out.append(Violation(sha, "carries an approval trailer but is not signed by a key in "
                             f"{SIGNERS} listed as an approver", "meaning"))
    unsigned = (f" (the trailer is there, but the commit is not signed by a key in {SIGNERS} "
                f"listed as an approver)")
    if ch.setup and signed_role(repo, sha, _show(repo, sha, SIGNERS), roles) is None:
        out.append(Violation(sha, f"creates {SIGNERS} without being signed by a key it lists "
                             f"as an approver", "gold"))
    if ch.gold and not (gold_t and signer):
        out.append(Violation(sha, f"changes gold without a '{TRAILER}: <approver>' trailer "
                             f"(approvers: {', '.join(sorted(roles))})"
                             + (unsigned if gold_t else "") + ": " + "; ".join(ch.gold), "gold"))
    if ch.meaning and not (meaning_t and signer):
        out.append(Violation(sha, f"changes meaning-carrying lines without "
                             f"'{MEANING_TRAILER}: <approver>' (approvers: "
                             f"{', '.join(sorted(roles))})" + (unsigned if meaning_t else "")
                             + ": " + "; ".join(ch.meaning), "meaning"))
    if ch.order:
        out.append(Violation(sha, "adds benchmark gold together with files outside "
                             "benchmarks/ (gold must be committed first, alone): "
                             + ", ".join(ch.order)))
    return out


def ratified(repo: Path, head: str) -> set[tuple[str, str]]:
    """(commit prefix, kind) pairs ratified by signed approval commits reachable from head."""
    out: set[tuple[str, str]] = set()
    for sha in _git(repo, "log", "--format=%H", f"--grep=^{RATIFIES}:", head).split():
        message = _git(repo, "log", "-1", "--format=%B", sha)
        base = _base(repo, sha)
        roles = read_approvers(_show(repo, base, "APPROVERS"))
        if signed_role(repo, sha, _show(repo, base, SIGNERS), roles) is None:
            continue
        kinds = ({"gold"} if approved_by(message, roles) else set()) | (
            {"meaning"} if meaning_approved(message, roles) else set())
        for line in message.splitlines():
            if line.startswith(f"{RATIFIES}:"):
                out |= {(t, k) for t in line.split(":", 1)[1].split()
                        if re.fullmatch(r"[0-9a-f]{7,40}", t) for k in kinds}
    return out


def check_range(repo: Path, base: str, head: str) -> list[Violation]:
    """Every violation in base..head, less those a signed approval commit ratified."""
    shas = _git(repo, "rev-list", "--reverse", f"{base}..{head}").split()
    rat, since = ratified(repo, head), rules_since(repo, head)
    return [v for sha in shas for v in check_commit(repo, sha, since)
            if v.kind == "order" or not any(sha.startswith(p) and k == v.kind for p, k in rat)]


def dry_run(repo: Path) -> list[str]:
    """What the staged change would need, as report lines; the last is ``needs: ...``."""
    ch = changes(repo, "HEAD", "")
    lines = [f"gold: {x}" for x in ch.gold] + [f"meaning: {x}" for x in ch.meaning]
    lines += [f"gold first: new gold with {p}" for p in ch.order]
    needs = [*(["meaning"] if ch.meaning else []), *(["gold"] if ch.gold else [])]
    last = f"needs: {' '.join(needs) or 'nothing'}"
    return [*lines, last + (" (BLOCKED: gold must be committed first, alone)" if ch.order else "")]


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--staged"]:
        lines = dry_run(Path.cwd())
        print("\n".join(f"gold gate (dry run): {x}" for x in lines))
        return 1 if "BLOCKED" in lines[-1] else 0
    if len(args) != 2:
        print("usage: python -m openverifiers.bench.gold_gate BASE HEAD | --staged",
              file=sys.stderr)
        return 2
    found = check_range(Path.cwd(), args[0], args[1])
    for v in found:
        print(f"gold gate: {v}")
    if not found:
        print(f"gold gate: ok ({args[0][:10]}..{args[1][:10]})")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
