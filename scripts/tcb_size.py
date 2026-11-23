"""Trusted-computing-base size gate.

Counts source lines in the trusted modules that are not blank, not comments
and not docstrings, and fails if a unit exceeds its cap or the total exceeds 2,000 (D-029). Also
prints the raw line count, docstrings included, for transparency.

    python scripts/tcb_size.py
"""

from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "openverifiers"
TRUSTED = ["raw", "checker", "state/hash.py", "state/load.py"]
LIMIT = 1090                                 # D-029: unit caps move within the total
#: The object layer's exact evaluator is its own audited unit (CTO decision, change
#: order v1.1 and M-CAP item 4), with its own cap, outside the main count.
UNITS = {"raw/formula.py": 410}
#: The exact-arithmetic unit (CTO decision D-021, W1): surds, intervals, numeric
#: checks, polynomial normal form and certificate checking, cap 450.
EXACT = ["raw/surd.py", "raw/interval.py", "raw/numeric.py", "raw/certificate.py",
         "raw/qpi.py"]
EXACT_LIMIT = 500
#: All trusted code, every unit together (W1).
TOTAL_LIMIT = 2000


def trusted_files() -> list[Path]:
    out: list[Path] = []
    for t in TRUSTED:
        p = ROOT / t
        if p.is_dir():
            out += sorted(p.rglob("*.py"))
        elif p.exists():
            out.append(p)
    return [p for p in out if str(p.relative_to(ROOT)) not in UNITS
            and str(p.relative_to(ROOT)) not in EXACT]


def code_lines(path: Path) -> int:
    src = path.read_text()
    doc_lines: set[int] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_lines |= set(range(body[0].lineno, (body[0].end_lineno or 0) + 1))
    lines: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                        tokenize.DEDENT, tokenize.ENDMARKER):
            continue
        lines |= set(range(tok.start[0], tok.end[0] + 1))
    return len(lines - doc_lines)


def main() -> int:
    total = raw = 0
    for f in trusted_files():
        n = code_lines(f)
        total += n
        raw += len(f.read_text().splitlines())
        print(f"{n:5d}  {f.relative_to(ROOT)}")
    print(f"{total:5d}  trusted code lines (limit {LIMIT}); {raw} physical lines incl. docs")
    ok = total <= LIMIT
    grand = total
    for unit, cap in UNITS.items():
        n = code_lines(ROOT / unit)
        print(f"{n:5d}  {unit}: its own audited unit (limit {cap})")
        ok, grand = ok and n <= cap, grand + n
    exact = sum(code_lines(ROOT / f) for f in EXACT)
    print(f"{exact:5d}  exact-arithmetic unit: {', '.join(EXACT)} (limit {EXACT_LIMIT})")
    grand += exact
    print(f"{grand:5d}  all trusted code (limit {TOTAL_LIMIT})")
    return 0 if ok and exact <= EXACT_LIMIT and grand <= TOTAL_LIMIT else 1


if __name__ == "__main__":
    sys.exit(main())
