"""OpenVerifiers v2 CLI demo — run a trace from a file and print the render.

Usage:
    python -m openverifiers trace DEMO.trace                        # grammar defaults
    python -m openverifiers trace DEMO.trace --fact 'p=1000.0'      # add background fact (name=value)
"""

import argparse
import sys

from .domains import standard_grammars
from .v2 import Registry, parse_dsl, run_trace
from .domains.math import make_number


def _facts_from_cli(pairs):
    out = {}
    for pair in pairs or []:
        name, _, value = pair.partition("=")
        out[name.strip()] = make_number(float(value), name.strip())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="openverifiers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    tp = sub.add_parser("trace", help="run a v2 trace file")
    tp.add_argument("trace_file")
    tp.add_argument("--fact", action="append", default=[],
                    help="background fact name=value (repeatable)")
    args = ap.parse_args(argv)

    if args.cmd == "trace":
        text = open(args.trace_file).read()
        reg = Registry(standard_grammars())
        env = dict(reg.facts) | _facts_from_cli(args.fact)
        result = run_trace(reg, env, parse_dsl(text))
        print(result.render())
        sys.exit(0 if result.verdict == "pass" else 1)
    ap.error("unknown command")


if __name__ == "__main__":
    main()