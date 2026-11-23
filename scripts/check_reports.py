"""Fail if a report holds an unfilled placeholder (packet 3 reply, work order 1).

    python scripts/check_reports.py [FILE ...]      (default: reports/**/*.md, approvals/*.md)

A placeholder is a line that is only an upper-case token (``NUMBERS``), a template
slot (``{{ name }}``), ``TODO``, ``TBD``, ``FIXME``, ``XXX``, ``PLACEHOLDER``, or
words such as "filled in below" / "fill in". Exit 1 with one line per hit.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"^\s*[A-Z][A-Z_]{3,}\s*$"              # a bare upper-case token on its own line
    r"|\{\{\s+[\w.]+\s+\}\}"                # a template slot {{ name }}
    r"|\b(TODO|TBD|FIXME|XXX|PLACEHOLDER)\b"
    r"|\bfilled in below\b|\bfill(ed)? in later\b|\bto be filled\b|<fill",
    re.M)


def hits(text: str) -> list[tuple[int, str]]:
    out = []
    in_code = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code          # quoted replies and commands are not report text
            continue
        if not in_code and PATTERN.search(line):
            out.append((n, line.strip()))
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    files = [Path(a) for a in args] or [*Path("reports").rglob("*.md"),
                                        *Path("approvals").glob("*.md")]
    bad = [(f, n, line) for f in sorted(files) for n, line in hits(f.read_text())]
    for f, n, line in bad:
        print(f"{f}:{n}: unfilled placeholder: {line[:100]}")
    print(f"reports: {len(files)} checked, {len(bad)} placeholder(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
