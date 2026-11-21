"""The ``ov`` command (v1).

    ov run FILE.ov [FILE.ov ...] [--verbose] [--strict]
    ov check FILE.ov [FILE.ov ...] [--verbose] [--strict]

``run`` checks, lowers and evaluates each file, answers its queries, checks its
``expect`` lines and its classes' theorems, and exits 1 if any expectation
fails, any theorem is refuted, any class is empty, or the file has errors.
``check`` does the same work and prints one line per file (pass/fail counts);
use it in loops and hooks. ``--strict`` turns verdicts that rest on an unchecked solver unsat into
UNKNOWN(plugin_unknown) and undeclared types (W201) into errors.

The pre-v1 step verifier's CLI is ``ov-m1``. More subcommands arrive with
their milestones (``bench`` in step 2; M3: ``lower``, ``query``; ``gate``; ``explain``).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from . import runner

USAGE = "usage: ov run|check FILE.ov [FILE.ov ...] [--verbose] [--strict]"


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
    print(f"ov: unknown command '{cmd}'\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
