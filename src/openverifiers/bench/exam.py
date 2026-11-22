"""``ov exam``: the exam tier (W3). Runs the drawn exam problems and reports capability.

    ov exam [DIR] [--strict] [--drafts] [--json]

``DIR`` (default ``benchmarks/exams/jee2025``) holds ``list.json``: the drawn
problems with their official answers. That file is the gold; it was committed
before any formalization. Each problem has a directory ``DIR/<id>/`` with either

- ``case.ov`` (the formalization) and ``answer.json`` (how its answer is read):

      {"read": "numeric", "query": 2, "unit": "g/cm^3"}
      {"read": "options", "options": {"A": [1], "B": [2, 3], "C": [4], "D": [5]}}
      {"read": "choice", "query": 1, "options": {"A": "2", "C": "sqrt(5/2)"}}

  Queries are numbered from 1 in file order. ``numeric``: the query's single
  value (in ``unit``, if given) is compared with the official answer, an exact
  number or an accepted range ``[lo to hi]``. ``choice``: the query's single
  value is compared with each option's value (numbers, + - * /, sqrt; the
  option texts are transcribed from the paper); the answer is the matching option.
  ``options``: an option is true
  if all its queries are PROVEN, false if one is REFUTED, else undecided. The
  answer is the set of true options; it counts only if every option is decided.

- or ``status.json`` when the problem is not formalized:
  ``{"category": "...", "note": "..."}`` (``CATEGORIES`` below).

Outcomes: ``solved``, ``wrong`` (a definite answer other than the official
one), ``unknown`` (some needed verdict is UNKNOWN), ``error`` (the file does not
load), ``not_formalized``. Results that load draft packages are provisional.

Untrusted tooling: it reads verdicts, it never makes one.
"""

from __future__ import annotations

import ast
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..lang.errors import OVError
from ..lang.units import parse_unit
from ..objects.engine import Settings
from ..runner import run_file
from .run import outcome

USAGE = "usage: ov exam [DIR] [--strict] [--drafts] [--json]"

#: Why a problem is not formalized, or why a formalization cannot answer it.
CATEGORIES = {
    "figure": "the data needed exist only in a figure",
    "structures": "needs chemical structures and reaction knowledge (no organic library)",
    "language": "OV cannot state the problem (the construct is missing from the language)",
    "library": "OV can state it, but the needed library does not exist, even as a draft",
    "engine": "stated, but the engine cannot decide it (UNKNOWN: solver, budget, evaluator)",
    "faithfulness": "the reviewer found the formalization unfaithful",
    "not_attempted": "expressible in principle; not attempted in W3",
}

_NUM = re.compile(r"^\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?:/\d+)?)\s*([^(]*?)\s*"
                  r"(?:\(±\s*([0-9.eE+-]+)\))?\s*$")


@dataclass
class Result:
    id: str
    subject: str
    type: str
    official: str
    outcome: str
    got: str = ""
    category: str = ""
    note: str = ""
    provisional: list[str] = field(default_factory=list)
    trust: list[str] = field(default_factory=list)


def official_range(ans: str) -> tuple[Fraction, Fraction]:
    m = re.fullmatch(r"\[\s*(-?[\d.]+)\s+to\s+(-?[\d.]+)\s*\]", ans.strip())
    if m:
        return Fraction(m[1]), Fraction(m[2])
    v = Fraction(ans.strip())
    return v, v


def read_value(text: str, unit: str | None) -> tuple[Fraction, Fraction] | None:
    """A rendered value as an enclosure [lo, hi], in ``unit`` (None: dimensionless)."""
    m = _NUM.match(text)
    if not m:
        return None
    v = Fraction(m[1])
    half = Fraction(m[3]) if m[3] else Fraction(0)
    shown = m[2].strip()
    scale = Fraction(1)
    if shown:
        u = parse_unit(shown)
        if u is None:
            return None
        scale = u[0]
    if unit:
        target = parse_unit(unit)
        if target is None or (shown and parse_unit(shown)[1] != target[1]):  # type: ignore[index]
            return None
        scale = scale / target[0]
    return (v - half) * scale, (v + half) * scale


_SURD = re.compile(r"^(-?)(\d+(?:/\d+)?)?√(\d+)$")


def _sqrt_bounds(x: Fraction) -> tuple[Fraction, Fraction]:
    """Rational bounds on sqrt(x), 2^-60 apart."""
    s = 1 << 60
    n = x.numerator * s * s // x.denominator
    r = math.isqrt(n)
    return Fraction(r, s), Fraction(r + 1, s)


def read_surd(text: str) -> tuple[Fraction, Fraction] | None:
    """An exact surd sum as OV shows it ('1/2√10', '3 - √2') as an enclosure."""
    lo = hi = Fraction(0)
    for part in re.split(r"\s+(?=[+-]\s)", text.strip()):
        part = part.replace(" ", "").lstrip("+")
        m = _SURD.match(part)
        if m:
            c = Fraction(m[2] or 1) * (-1 if m[1] else 1)
            a, b = _sqrt_bounds(Fraction(m[3]))
            lo, hi = lo + min(c * a, c * b), hi + max(c * a, c * b)
        elif re.fullmatch(r"-?\d+(?:/\d+)?", part):
            lo, hi = lo + Fraction(part), hi + Fraction(part)
        else:
            return None
    return lo, hi


def option_value(text: str) -> float:
    """An option's value: numbers, + - * /, unary minus and sqrt (nothing else)."""
    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int | float):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add | ast.Sub | ast.Mult | ast.Div):
            a, b = ev(n.left), ev(n.right)
            return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b}.get(type(n.op), a / b) \
                if not isinstance(n.op, ast.Div) else a / b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "sqrt" \
                and len(n.args) == 1:
            return math.sqrt(ev(n.args[0]))
        raise ValueError(f"option value not understood: {text!r}")
    return ev(ast.parse(text, mode="eval"))


def _options(official: str) -> set[str]:
    return {x.strip() for x in official.split(",") if x.strip()}


def judge(problem: dict[str, Any], spec: dict[str, Any], got: dict[str, Any]) -> tuple[str, str]:
    """(outcome, what OV answered) for one formalized problem."""
    qs = got["queries"]

    def q(i: int) -> dict[str, Any]:
        if not 1 <= i <= len(qs):
            raise ValueError(f"answer.json names query {i}; the file has {len(qs)}")
        row: dict[str, Any] = qs[i - 1]
        return row
    if spec["read"] == "numeric":
        a = q(spec["query"])
        vals = a.get("values") or []
        if a["verdict"] != "PROVEN" or len(vals) != 1:
            return "unknown", f"{a['verdict']} {vals}"
        enc = read_value(vals[0], spec.get("unit"))
        if enc is None:
            return "unknown", f"unreadable value {vals[0]!r}"
        lo, hi = official_range(problem["official_answer"])
        text = vals[0]
        return ("solved" if lo <= enc[0] and enc[1] <= hi else "wrong"), text
    if spec["read"] == "choice":
        a = q(spec["query"])
        vals = a.get("values") or []
        if a["verdict"] != "PROVEN" or len(vals) != 1:
            return "unknown", f"{a['verdict']} {vals}"
        enc = read_value(vals[0], spec.get("unit")) or read_surd(vals[0])
        if enc is None:
            return "unknown", f"unreadable value {vals[0]!r}"
        mid = float((enc[0] + enc[1]) / 2)
        hits = sorted(o for o, t in spec["options"].items()
                      if abs(option_value(t) - mid) <= 1e-9 * max(1.0, abs(mid)))
        text = f"{vals[0]} = option {', '.join(hits) or 'none'}"
        return ("solved" if set(hits) == _options(problem["official_answer"]) else "wrong"), text
    chosen, undecided = set(), []
    for opt, idx in spec["options"].items():
        vs = [q(i)["verdict"] for i in idx]
        if all(v == "PROVEN" for v in vs):
            chosen.add(opt)
        elif not any(v == "REFUTED" for v in vs):
            undecided.append(opt)
    text = ", ".join(sorted(chosen)) + (f" (undecided: {', '.join(undecided)})"
                                        if undecided else "")
    if undecided:
        # A definite error is still an error: a true option OV refuted, or a false one
        # it proved, is wrong even if other options are undecided.
        off = _options(problem["official_answer"])
        refuted = {o for o in spec["options"] if o not in chosen and o not in undecided}
        if chosen - off or refuted & off:
            return "wrong", text
        return "unknown", text
    return ("solved" if chosen == _options(problem["official_answer"]) else "wrong"), text


def run_problem(root: Path, problem: dict[str, Any], st: Settings) -> Result:
    d = root / problem["id"]
    r = Result(problem["id"], problem["subject"], problem["type"], problem["official_answer"],
               "not_formalized")
    if (d / "status.json").is_file():
        s = json.loads((d / "status.json").read_text())
        r.category, r.note = s["category"], s.get("note", "")
        return r
    if not (d / "case.ov").is_file():
        r.category, r.note = "", "no formalization yet"
        return r
    spec = json.loads((d / "answer.json").read_text())
    try:
        res = run_file(d / "case.ov", files={str(d / "case.ov")}, settings=st)
    except OVError as e:
        r.outcome, r.got = "error", ", ".join(sorted({x.code for x in e.diagnostics}))
        r.category = "library" if any(x.code == "E203" for x in e.diagnostics) else ""
        return r
    r.provisional = res.draft_packages
    got = outcome(res)
    r.outcome, r.got = judge(problem, spec, got)
    used = [i for v in ([spec["query"]] if spec["read"] in ("numeric", "choice")
                        else spec["options"].values()) for i in (v if isinstance(v, list)
                                                                   else [v])]
    r.trust = sorted({t for i in used for t in got["queries"][i - 1].get("trust", [])})
    if r.outcome == "unknown":
        r.category = "engine"
    return r


def run(root: Path, st: Settings) -> list[Result]:
    listing = json.loads((root / "list.json").read_text())
    return [run_problem(root, p, st) for p in listing["problems"]]


def summary(results: list[Result]) -> dict[str, Any]:
    by_subject: dict[str, Counter[str]] = {}
    for r in results:
        by_subject.setdefault(r.subject, Counter())[r.outcome] += 1
    return {
        "problems": len(results),
        "outcomes": dict(Counter(r.outcome for r in results)),
        "by_subject": {k: dict(v) for k, v in sorted(by_subject.items())},
        "categories": dict(Counter(r.category for r in results if r.category)),
        "provisional": sum(bool(r.provisional) for r in results if r.outcome == "solved"),
        "wrong": [r.id for r in results if r.outcome == "wrong"],
    }


def render(results: list[Result]) -> str:
    lines = []
    for r in results:
        tag = " PROVISIONAL" if r.provisional else ""
        extra = f" [{r.category}]" if r.category else ""
        lines.append(f"{r.outcome:15} {r.id:22} official {r.official:14} got {r.got or '-'}"
                     f"{extra}{tag}")
    s = summary(results)
    lines.append(f"{s['outcomes']}; wrong: {s['wrong'] or 'none'}; "
                 f"solved on draft packages: {s['provisional']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0
    st = Settings(strict="--strict" in args, drafts="--drafts" in args)
    if st.strict and st.drafts:
        print("ov exam: --drafts cannot be combined with --strict", file=sys.stderr)
        return 2
    pos = [a for a in args if not a.startswith("--")]
    root = Path(pos[0]) if pos else Path("benchmarks/exams/jee2025")
    results = run(root, st)
    if "--json" in args:
        print(json.dumps({"results": [r.__dict__ for r in results],
                          "summary": summary(results)}, indent=2))
    else:
        print(render(results))
    return 1 if summary(results)["wrong"] else 0
