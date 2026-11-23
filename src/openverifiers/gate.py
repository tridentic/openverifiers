"""``ov gate``: the commit gate (MP §3 L8; directive C6).

    ov gate [--base REV] [--staged] [--drafts] [PATH ...]

Checks every changed OV file (the PATHs, or the ``.ov`` files changed since
``--base`` or staged with ``--staged``) the way ``ov check`` does: its
expectations, theorems and classes must hold, and it must load. With
``--base`` it also runs the gold and meaning gates (``bench/gold_gate.py``)
over ``REV..HEAD``. Exit 1 on any failure, with one line per file.

Used three ways:
- pre-commit: ``.pre-commit-hooks.yaml`` (hook ``ov-gate``, ``--staged``);
- GitHub Actions: ``action.yml`` (``ov gate --base <before>``);
- MCP: ``check_files`` in ``openverifiers.mcp_gate``.

Untrusted glue: the verdicts are the kernel's.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .bench.gold_gate import check_range
from .lang.errors import OVError
from .objects.engine import Settings
from .runner import run_file


def changed(base: str | None, staged: bool) -> list[Path]:
    args = ["git", "diff", "--name-only", "--diff-filter=ACMR"]
    args += ["--cached"] if staged else [f"{base}...HEAD"] if base else []
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    return [Path(p) for p in out.split() if p.endswith(".ov") and Path(p).is_file()]


def check_file(path: Path, drafts: bool = False) -> tuple[bool, str]:
    """(ok, one line) for one OV file."""
    try:
        res = run_file(path, files={str(path)}, settings=Settings(drafts=drafts))
    except OVError as e:
        return False, f"{path}: FAIL (does not load: " + ", ".join(
            sorted({d.code for d in e.diagnostics})) + ")"
    bad = [*res.failed, *res.class_errors]
    tag = " PROVISIONAL" if res.draft_packages else ""
    if bad:
        what = "; ".join(f"{getattr(a, 'title', '') or a.verdict}" for a in bad[:5])
        return False, f"{path}: FAIL ({len(bad)} failed: {what}){tag}"
    return True, f"{path}: ok{tag}"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    base, staged, drafts, paths = None, "--staged" in args, "--drafts" in args, []
    it = iter(args)
    for a in it:
        if a == "--base":
            base = next(it, None)
        elif not a.startswith("--"):
            paths.append(Path(a))
    files = paths or changed(base, staged)
    ok = True
    for f in files:
        good, line = check_file(f, drafts)
        ok = ok and good
        print(line)
    if base:
        for v in check_range(Path("."), base, "HEAD"):
            ok = False
            print(f"gold gate: {v}")
    print(f"ov gate: {'ok' if ok else 'FAIL'} ({len(files)} OV file(s)"
          + (f", gold and meaning gates over {base}..HEAD" if base else "") + ")")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
