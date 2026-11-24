"""The ``ov`` command (v1).

    ov FILE.ov [FILE.ov ...] [--verbose] ...          (the same as `ov run`)
    ov run FILE.ov [FILE.ov ...] [--verbose] [--strict] [--no-reductions] [--drafts]
    ov check FILE.ov [FILE.ov ...] [--verbose] [--strict] [--no-reductions]
    ov bench [DIR] [--suite NAME] [--case NAME] [--seeds N] [--out DIR] [--strict]
             [--no-reductions]
    ov audit PACKAGE|FILE [--dag THEOREM ...] [--json]
    ov exam [DIR] [--strict] [--drafts] [--json]
    ov state FILE.ov [--scenario NAME] [--out PATH]
    ov gate [--base REV] [--staged] [--drafts] [PATH ...]

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

``ov COMMAND --help`` prints that command's usage. The library side is
``openverifiers.sdk`` (docs/SDK.md). The pre-v1 step verifier's CLI is ``ov-m1``.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence

from . import runner

USAGE = ("usage: ov [run|check] FILE.ov [FILE.ov ...] [--verbose] [--strict] [--drafts]\n"
         "       ov bench|exam|audit|state|gate ...   (ov COMMAND --help; ov --help)")
#: Each command's module; its docstring is the command's --help text.
COMMANDS = {"run": ".runner", "check": ".runner", "audit": ".audit", "gate": ".gate",
            "state": ".state.export", "exam": ".bench.exam", "bench": ".bench.run"}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip() if args else USAGE, file=sys.stdout if args else sys.stderr)
        return 0 if args else 2
    cmd, rest = args[0], args[1:]
    if cmd.endswith(".ov"):                       # the brief's form: ov program.ov --verbose
        cmd, rest = "run", args
    if cmd in COMMANDS and any(a in ("-h", "--help") for a in rest):
        print((importlib.import_module(COMMANDS[cmd], __package__).__doc__ or USAGE).strip())
        return 0
    if cmd == "run":
        return runner.main(rest)
    if cmd == "check":
        return runner.main(rest, check=True)
    if cmd == "audit":
        from .audit import main as audit
        return audit(rest)
    if cmd == "gate":
        from .gate import main as gate
        return gate(rest)
    if cmd == "state":
        from .state.export import main as state
        return state(rest)
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
