"""Trusted-computing-base size gate.

Counts source lines in the trusted modules that are not blank, not comments
and not docstrings, and fails if the total exceeds the limit (1,500). Also
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
LIMIT = 1500


def trusted_files() -> list[Path]:
    out: list[Path] = []
    for t in TRUSTED:
        p = ROOT / t
        if p.is_dir():
            out += sorted(p.rglob("*.py"))
        elif p.exists():
            out.append(p)
    return out


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
    return 0 if total <= LIMIT else 1


if __name__ == "__main__":
    sys.exit(main())
