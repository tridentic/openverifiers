"""The ``ov`` command (v1).

    ov run FILE.ov [FILE.ov ...] [--verbose] [--strict] [--no-reductions] [--drafts]
    ov check FILE.ov [FILE.ov ...] [--verbose] [--strict] [--no-reductions]
    ov bench [DIR] [--suite NAME] [--case NAME] [--seeds N] [--out DIR] [--strict]
             [--no-reductions]
    ov audit PACKAGE|FILE [--dag THEOREM ...] [--json]
    ov exam [DIR] [--strict] [--drafts] [--json]

``run`` checks, lowers and evaluates each file, answers its queries, checks its
``expect`` lines and its classes' theorems, and exits 1 if any expectation
fails, any theorem is refuted, any class is empty, or the file has errors.
``check`` does the same work and prints one line per file (pass/fail counts);
use it in loops and hooks. ``--drafts`` also loads unapproved library drafts
from ``drafts/packages/`` (never with ``--strict``); results that use them are
marked PROVISIONAL. ``exam`` runs the drawn exam problems (W3).
``--strict`` turns verdicts that rest on an unchecked solver unsat into
UNKNOWN(plugin_unknown) and undeclared types (W201) into errors.
``--no-reductions`` turns off the theorem-proving reductions (docs/SEMANTICS.md
§7), so every unsat is computed on the full problem; slower, for ablation.

The pre-v1 step verifier's CLI is ``ov-m1``. More subcommands arrive with
their milestones (M3: ``lower``, ``query``; ``gate``; ``explain``).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from . import runner

USAGE = ("usage: ov run|check FILE.ov [FILE.ov ...] [--verbose] [--strict] [--no-reductions]\n"
         "       ov bench [DIR] [--suite NAME] [--seeds N] [--out DIR]")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip() if args else USAGE, file=sys.stdout if args else sys.stderr)
        return 0 if args else 2
    cmd, rest = args[0], args[1:]
    if cmd == "run":
        return runner.main(rest)
    if cmd == "check":
        return runner.main(rest, check=True)
    if cmd == "audit":
        from .audit import main as audit
        return audit(rest)
    if cmd == "exam":
        from .bench.exam import main as exam
        return exam(rest)
    if cmd == "bench":
        from .bench.run import main as bench
        return bench(rest)
    print(f"ov: unknown command '{cmd}'\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
