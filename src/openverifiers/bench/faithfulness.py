"""Faithfulness lint for exam formalizations (W3), and the reviewer's packet.

    python -m openverifiers.bench.faithfulness [DIR]          # lint every case
    python -m openverifiers.bench.faithfulness packet ID [DIR] # the reviewer's packet

The lint is mechanical and conservative. Errors:

- ``F1 answer-leak``: the asked property is set to a number in the case (in a
  query pattern or an invariant), so OV would only echo it back.
- ``F2 general-law``: a case states a ``law``, ``axiom`` or ``definition``.
  General knowledge belongs in a package (where the meaning gate sees it); a
  case states only the problem: its entities, givens and the question.
- ``F3 stray-package``: a case directory holds another ``.ov`` file, which
  ``import`` would find next to the case: a library outside the gate.
- ``F4 answer-map``: ``answer.json`` names a query the file does not have, or the
  file has a query the answer does not use.
- ``F5 assumption``: a case uses ``assume``; an exam answer must not depend on
  an assumption the problem does not state.

Warnings (need a human or the reviewer):

- ``W1 given-missing``: a number in the question text (read from the gitignored
  originals, when present) does not occur in the case.
- ``W2 no-reading``: the case has invariants beyond the givens but no
  ``Reading:`` or ``Transcription`` comment saying how the text was read.

The packet is what the reviewer agent sees: the question text and the
formalization (with its answer map). It never contains the official answer,
the draw list, or OV's results: the reviewer is gold-blind.

Untrusted tooling.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / "benchmarks" / "exams" / "jee2025"
PRIVATE = ROOT / "private" / "sources" / "jee" / "questions_2025.json"
SUBJECT = {"phys": "physics", "chem": "chemistry", "math": "mathematics"}


@dataclass
class Finding:
    id: str
    code: str
    message: str

    @property
    def error(self) -> bool:
        return self.code.startswith("F")

    def __str__(self) -> str:
        return f"{self.id}: {self.code} {self.message}"


def _code(text: str) -> list[str]:
    """The case's lines without comments."""
    return [ln.split("#", 1)[0] for ln in text.splitlines()]


def question_text(pid: str) -> str | None:
    """The original question (gitignored); None when the originals are not here."""
    if not PRIVATE.is_file():
        return None
    m = re.fullmatch(r"jee2025-(phys|chem|math)-p(\d)q(\d+)", pid)
    if not m:
        return None
    data = json.loads(PRIVATE.read_text())
    q = data.get(f"{SUBJECT[m[1]]}|{m[2]}|{m[3]}")
    return None if q is None else str(q["text"])


_QUERY = re.compile(r"^\s*query\b(.*)$")
_ASKED = re.compile(r"(\w+)\s*=\s*\?\w+")
_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")


def lint_case(d: Path) -> list[Finding]:
    pid = d.name
    out: list[Finding] = []
    case = d / "case.ov"
    if not case.is_file():
        return out
    text = case.read_text()
    code = _code(text)
    queries = [m[1] for ln in code if (m := _QUERY.match(ln))]
    asked = {a for q in queries for a in _ASKED.findall(q)}
    joined = "\n".join(code)
    for a in sorted(asked):
        for m in re.finditer(rf"\b{re.escape(a)}\s*=\s*-?\d", joined):
            before = joined[:m.start()].rstrip()
            if not before or before[-1] not in "*/+-^(.":   # a whole side, not a factor
                out.append(Finding(pid, "F1", f"the asked property '{a}' is set to a number"))
                break
    for i, ln in enumerate(code, 1):
        if re.match(r"^\s*(law|axiom|definition)\b", ln):
            out.append(Finding(pid, "F2", f"line {i} states general knowledge; move it to a "
                                          "package"))
        if re.match(r"^\s*assume\b", ln):
            out.append(Finding(pid, "F5", f"line {i} assumes something"))
    for other in sorted(d.glob("*.ov")):
        if other.name != "case.ov":
            out.append(Finding(pid, "F3", f"{other.name} sits next to the case"))
    spec_file = d / "answer.json"
    if not spec_file.is_file():
        out.append(Finding(pid, "F4", "no answer.json"))
    else:
        spec: dict[str, Any] = json.loads(spec_file.read_text())
        used = ({spec["query"]} if spec["read"] in ("numeric", "choice")
                else {i for v in spec["options"].values() for i in v})
        n = len(queries)
        if not used <= set(range(1, n + 1)) or used != set(range(1, n + 1)):
            out.append(Finding(pid, "F4", f"answer.json uses queries {sorted(used)}; the file "
                                          f"has {n}"))
    if re.search(r"^\s*invariant\b", joined, re.M) and not re.search(
            r"#.*\b(Reading|Transcription)\b", text):
        out.append(Finding(pid, "W2", "invariants beyond the givens, but no 'Reading:' or "
                                      "'Transcription' comment"))
    q = question_text(pid)
    if q is not None:
        have = {_norm(x) for x in _NUMBER.findall(text)}
        stated = [x for x in _NUMBER.findall(q.split("Answer:")[0]) if _norm(x) not in have]
        if stated:
            out.append(Finding(pid, "W1", "numbers in the question not found in the case: "
                                          + ", ".join(dict.fromkeys(stated))))
    return out


def _norm(x: str) -> str:
    return str(float(x)).removesuffix(".0")


def lint(root: Path = DEFAULT) -> list[Finding]:
    return [f for d in sorted(p for p in root.iterdir() if p.is_dir()) for f in lint_case(d)]


def packet(pid: str, root: Path = DEFAULT) -> str:
    """The reviewer's packet: question and formalization only (gold-blind)."""
    d = root / pid
    q = question_text(pid)
    if q is None:
        raise SystemExit("the original question text is not available here")
    q = q.split("Answer:")[0].rstrip()          # the originals carry the key: cut it
    parts = [f"# Problem {pid}", "## Question (original text; formulas may be garbled by "
             "PDF extraction)", q, "## Formalization (case.ov)", (d / "case.ov").read_text()]
    if (d / "answer.json").is_file():
        parts += ["## How OV's answer is read (answer.json)", (d / "answer.json").read_text()]
    for f in sorted({ln.split()[1] for ln in (d / "case.ov").read_text().splitlines()
                     if ln.startswith("import ")}):
        lib = _library(f)
        if lib is not None:
            parts += [f"## Library {f} ({lib.relative_to(ROOT)})", lib.read_text()]
    return "\n\n".join(parts) + "\n"


def _library(name: str) -> Path | None:
    rel = Path(*name.split(".")).with_suffix(".ov")
    for base in (ROOT / "src" / "openverifiers" / "packages", ROOT / "drafts" / "packages"):
        if (base / rel).is_file():
            return base / rel
    return None


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "packet":
        print(packet(args[1], Path(args[2]) if len(args) > 2 else DEFAULT), end="")
        return 0
    found = lint(Path(args[0]) if args else DEFAULT)
    for f in found:
        print(f)
    errors = [f for f in found if f.error]
    print(f"{len(errors)} error(s), {len(found) - len(errors)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
